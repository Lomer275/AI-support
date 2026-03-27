import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

# Bitrix custom field IDs
FIELD_INN = "UF_CRM_1751273997835"
FIELD_AUTH_STATUS = "UF_CRM_1768296374"
FIELD_AUTH_TIMESTAMP = "UF_CRM_1768547250879"

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

        Uses 2 batch requests:
          Batch 1: crm.deal.get + tasks.task.list (find "Собрать ЛИЧНЫЕ" task)
          Batch 2: user.get + tasks.task.get with CHECKLIST

        Returns formatted string for injection into client_context.
        Returns empty string on any failure (non-fatal).
        """
        url = f"{self._base}/batch"

        # ── Batch 1: deal info + find document task ──────────────────────
        params1 = {
            "halt": "0",
            "cmd[deal]": (
                f"crm.deal.get?ID={deal_id}"
                f"&select[]=STAGE_ID&select[]=ASSIGNED_BY_ID"
            ),
            "cmd[tasks]": (
                f"tasks.task.list"
                f"?filter[UF_CRM_TASK][]=D_{deal_id}"
                f"&select[]=ID&select[]=TITLE"
                f"&start=0"
            ),
        }
        try:
            async with self._session.post(url, data=params1) as resp:
                data1 = await resp.json(content_type=None)
        except Exception:
            logger.exception("get_deal_profile batch1 failed for deal_id=%s", deal_id)
            return ""

        result1 = data1.get("result", {}).get("result", {})
        deal = result1.get("deal") or {}
        if not deal:
            return ""

        stage_id = deal.get("STAGE_ID", "")
        stage_label = STAGE_LABELS.get(stage_id, stage_id)
        assigned_by_id = deal.get("ASSIGNED_BY_ID", "")

        tasks_raw = result1.get("tasks") or {}
        task_list = tasks_raw.get("tasks", []) if isinstance(tasks_raw, dict) else []
        doc_task = next(
            (t for t in task_list if "Собрать ЛИЧНЫЕ" in (t.get("title") or "")),
            None,
        )
        task_id = doc_task["id"] if doc_task else None

        # ── Batch 2: manager name + task checklist ────────────────────────
        params2: dict[str, str] = {"halt": "0"}
        if assigned_by_id:
            params2["cmd[manager]"] = f"user.get?ID={assigned_by_id}"
        if task_id:
            params2["cmd[checklist]"] = (
                f"tasks.task.get?taskId={task_id}&select[]=CHECKLIST"
            )

        manager_name = ""
        checklist_lines: list[str] = []

        if len(params2) > 1:
            try:
                async with self._session.post(url, data=params2) as resp:
                    data2 = await resp.json(content_type=None)
            except Exception:
                logger.exception("get_deal_profile batch2 failed for deal_id=%s", deal_id)
                data2 = {}

            result2 = data2.get("result", {}).get("result", {})

            # Manager name
            manager_raw = result2.get("manager") or []
            if isinstance(manager_raw, list) and manager_raw:
                m = manager_raw[0]
            elif isinstance(manager_raw, dict):
                m = manager_raw
            else:
                m = {}
            if m:
                parts = [m.get("LAST_NAME", ""), m.get("NAME", ""), m.get("SECOND_NAME", "")]
                manager_name = " ".join(p for p in parts if p).strip()

            # Checklist from task
            checklist_resp = result2.get("checklist") or {}
            raw_checklist = (checklist_resp.get("task") or {}).get("checklist") or {}
            for item in raw_checklist.values():
                if str(item.get("parentId", "0")) == "0":
                    continue  # skip root BX_CHECKLIST_1
                title = (item.get("title") or "")[:80]
                icon = "✅" if item.get("isComplete") == "Y" else "⏳"
                checklist_lines.append(f"  {icon} {title}")

        # ── Format output ─────────────────────────────────────────────────
        lines = [
            "=== ПРОФИЛЬ КЛИЕНТА (Bitrix) ===",
            f"Стадия дела: {stage_label}",
        ]
        if manager_name:
            lines.append(f"Ответственный менеджер: {manager_name}")
        if checklist_lines:
            lines.append("\nЧеклист документов:")
            lines.extend(checklist_lines)

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
