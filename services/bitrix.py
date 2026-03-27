import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

# Bitrix custom field IDs
FIELD_INN = "UF_CRM_1751273997835"
FIELD_AUTH_STATUS = "UF_CRM_1768296374"
FIELD_AUTH_TIMESTAMP = "UF_CRM_1768547250879"

# Document checklist fields (enumeration: нет / ожидает получения / да)
DOCUMENT_FIELDS: list[tuple[str, str]] = [
    ("UF_CRM_1576013311213", "Паспорт (все страницы)"),
    ("UF_CRM_1576013441400", "СНИЛС"),
    ("UF_CRM_1576100885263", "ИНН"),
    ("UF_CRM_1576012442895", "Кредитный договор"),
    ("UF_CRM_1576012695632", "Справка из банка о задолженности"),
    ("UF_CRM_1576013203796", "Нотариальная доверенность"),
    ("UF_CRM_1576014979732", "Справка из ЕГРН о недвижимости"),
    ("UF_CRM_1576015047314", "Справка из ГИБДД о транспорте"),
    ("UF_CRM_1576015573599", "Справка из ФНС об отсутствии ИП/ЮЛ"),
    ("UF_CRM_1576015802748", "Справка из ПФР о начислениях"),
    ("UF_CRM_1576016214194", "2-НДФЛ за последние 3 года"),
    ("UF_CRM_1576015446573", "Справка о составе семьи"),
    ("UF_CRM_1576015504174", "Справка о состоянии инд. л/с"),
    ("UF_CRM_1576015862044", "Копия трудовой книжки"),
    ("UF_CRM_1576014861311", "Копии сделок за 3 года"),
    ("UF_CRM_1576014922624", "Документы на имущество"),
]

STAGE_LABELS: dict[str, str] = {
    "C4:NEW":                "Сбор документов",
    "C4:2":                  "Замороженная сделка",
    "C4:UC_07IZ0U":          "Исковое заявление подготовлено",
    "C4:PREPAYMENT_INVOICE": "Заявление подано в суд",
    "C4:11":                 "Заявление оставлено без движения",
    "C4:EXECUTING":          "Заявление принято судом, назначено заседание",
    "C4:12":                 "Реструктуризация (без имущества)",
    "C4:13":                 "Реструктуризация (с имуществом)",
    "C4:17":                 "Реструктуризация (с ипотекой)",
    "C4:14":                 "Реализация имущества (без имущества)",
    "C4:15":                 "Реализация имущества (с имуществом)",
    "C4:18":                 "Реализация имущества (с ипотекой)",
    "C4:UC_PQHMFA":          "Согласование расторжения",
    "C4:WON":                "Долги списаны",
    "C4:LOSE":               "Сделка закрыта",
}


class BitrixService:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session
        self._base = settings.bitrix_webhook_base

    async def search_by_inn(self, inn: str) -> dict[str, Any] | None:
        """Batch search: deal by INN -> contacts -> contact detail. Returns parsed result or None."""
        url = f"{self._base}/batch"
        params = {
            "halt": "0",
            "cmd[deal]": (
                f"crm.deal.list?"
                f"filter[{FIELD_INN}]={inn}&"
                f"filter[CATEGORY_ID]=4&"
                f"filter[STAGE_SEMANTIC_ID]=P&"
                f"select[]=ID&select[]=TITLE&select[]=STAGE_ID&select[]={FIELD_INN}&"
                f"order[DATE_CREATE]=DESC"
            ),
            "cmd[contacts]": "crm.deal.contact.items.get?ID=$result[deal][0][ID]",
            "cmd[contact_detail]": (
                "crm.contact.get?"
                "ID=$result[contacts][0][CONTACT_ID]&"
                "select[]=ID&select[]=NAME&select[]=LAST_NAME&select[]=SECOND_NAME&select[]=PHONE"
            ),
        }
        async with self._session.post(url, data=params) as resp:
            data = await resp.json(content_type=None)

        result = data.get("result", {}).get("result", {})
        deals = result.get("deal", [])
        if not deals:
            return None

        deal = deals[0]
        contact_detail = result.get("contact_detail", {})
        if not contact_detail or not contact_detail.get("ID"):
            return None

        # Build full name
        parts = [
            contact_detail.get("LAST_NAME", ""),
            contact_detail.get("NAME", ""),
            contact_detail.get("SECOND_NAME", ""),
        ]
        full_name = " ".join(p for p in parts if p).strip()

        # Extract all phones
        phones = contact_detail.get("PHONE", [])
        bitrix_phones = [p["VALUE"] for p in phones if p.get("VALUE")]

        contacts_list = result.get("contacts", [])
        contact_id = str(contacts_list[0]["CONTACT_ID"]) if contacts_list else ""

        return {
            "deal_id": str(deal["ID"]),
            "contact_id": contact_id,
            "contact_name": full_name or "Клиент",
            "bitrix_phone": bitrix_phones[0] if bitrix_phones else "",
            "bitrix_phones": bitrix_phones,
            "inn": inn,
        }

    async def get_deal_profile(self, deal_id: str) -> str:
        """Fetch deal stage, responsible manager, and document checklist from Bitrix.
        Returns a formatted string for injection into client_context.
        Returns empty string on failure (non-fatal).
        """
        doc_selects = "".join(
            f"&select[]={field_id}" for field_id, _ in DOCUMENT_FIELDS
        )
        url = f"{self._base}/batch"
        params = {
            "halt": "0",
            "cmd[deal]": (
                f"crm.deal.get?ID={deal_id}"
                f"&select[]=ID&select[]=STAGE_ID&select[]=ASSIGNED_BY_ID"
                f"{doc_selects}"
            ),
            "cmd[manager]": "user.get?ID=$result[deal][ASSIGNED_BY_ID]",
        }
        try:
            async with self._session.post(url, data=params) as resp:
                data = await resp.json(content_type=None)
        except Exception:
            logger.exception("get_deal_profile request failed for deal_id=%s", deal_id)
            return ""

        result = data.get("result", {}).get("result", {})
        deal = result.get("deal") or {}
        manager_list = result.get("manager") or []
        if not deal:
            return ""

        stage_id = deal.get("STAGE_ID", "")
        stage_label = STAGE_LABELS.get(stage_id, stage_id)

        manager_name = ""
        if isinstance(manager_list, list) and manager_list:
            m = manager_list[0]
            parts = [m.get("LAST_NAME", ""), m.get("NAME", ""), m.get("SECOND_NAME", "")]
            manager_name = " ".join(p for p in parts if p).strip()
        elif isinstance(manager_list, dict):
            parts = [
                manager_list.get("LAST_NAME", ""),
                manager_list.get("NAME", ""),
                manager_list.get("SECOND_NAME", ""),
            ]
            manager_name = " ".join(p for p in parts if p).strip()

        # Build document checklist
        doc_lines: list[str] = []
        for field_id, doc_name in DOCUMENT_FIELDS:
            value = (deal.get(field_id) or "").strip().lower()
            if value == "да":
                icon = "✅"
                status = "предоставлен"
            elif "ожидает" in value:
                icon = "⏳"
                status = "ожидает получения"
            else:
                continue  # skip "нет" to keep context concise

            doc_lines.append(f"{icon} {doc_name} — {status}")

        lines = [
            "=== ПРОФИЛЬ КЛИЕНТА (Bitrix) ===",
            f"Стадия дела: {stage_label}",
        ]
        if manager_name:
            lines.append(f"Ответственный менеджер: {manager_name}")
        if doc_lines:
            lines.append("\nСтатус документов:")
            lines.extend(doc_lines)
        else:
            lines.append("Статус документов: нет данных")

        return "\n".join(lines)

    async def update_deal_authorized(self, deal_id: str, timestamp: str) -> bool:
        """Mark deal as authorized with timestamp."""
        url = f"{self._base}/crm.deal.update"
        params = {
            "id": deal_id,
            f"fields[{FIELD_AUTH_STATUS}]": "Авторизирован",
            f"fields[{FIELD_AUTH_TIMESTAMP}]": timestamp,
        }
        try:
            async with self._session.post(url, data=params) as resp:
                data = await resp.json(content_type=None)
                return bool(data.get("result"))
        except Exception:
            logger.exception("Bitrix update_deal_authorized failed")
            return False
