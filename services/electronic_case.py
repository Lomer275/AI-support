"""ElectronicCaseService (S04/T22).

Reads client data from Supabase `electronic_case` project and returns
formatted context strings for AI agents.

Replaces BitrixService.get_deal_profile() in the chat pipeline (T23).
"""
import logging

import aiohttp

from services.bitrix import STAGE_LABELS
from services.document_validator import CHECKLIST_ITEMS

logger = logging.getLogger(__name__)

_NULL = "[не заполнено в CRM]"


def _fmt(value, suffix: str = "") -> str:
    """Format a value: return value+suffix or _NULL placeholder."""
    if value is None or value == "" or value == []:
        return _NULL
    return f"{value}{suffix}"


def _fmt_money(value) -> str:
    if value is None:
        return _NULL
    try:
        amount = int(float(value))
        return f"{amount:,} ₽".replace(",", " ")
    except (ValueError, TypeError):
        return _NULL


def _fmt_stage(stage_code: str | None) -> str:
    if not stage_code:
        return _NULL
    label = STAGE_LABELS.get(stage_code, stage_code)
    return label


class ElectronicCaseService:
    """Read-only service: electronic_case Supabase → formatted context for agents."""

    def __init__(
        self,
        http_session: aiohttp.ClientSession,
        cases_url: str,
        cases_key: str,
    ) -> None:
        self._session = http_session
        self._url = cases_url
        self._headers = {
            "apikey": cases_key,
            "Authorization": f"Bearer {cases_key}",
            "Content-Type": "application/json",
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _fetch_case(self, inn: str) -> dict | None:
        """Fetch cases row by INN. Returns None if not found or error."""
        try:
            async with self._session.get(
                f"{self._url}/rest/v1/cases",
                headers=self._headers,
                params={"inn": f"eq.{inn}", "limit": "1"},
            ) as resp:
                rows = await resp.json(content_type=None)
            return rows[0] if rows else None
        except Exception:
            logger.exception("[ELECTRONIC_CASE] fetch_case failed for inn=%s", inn)
            return None

    async def _fetch_documents(self, inn: str) -> list[dict]:
        """Fetch all document rows for this INN."""
        try:
            async with self._session.get(
                f"{self._url}/rest/v1/documents",
                headers=self._headers,
                params={"inn": f"eq.{inn}", "select": "doc_type,file_name,status"},
            ) as resp:
                return await resp.json(content_type=None)
        except Exception:
            logger.warning("[ELECTRONIC_CASE] fetch_documents failed for inn=%s", inn)
            return []

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_case_context(self, inn: str) -> str | None:
        """Return formatted case context string for agent prompts.

        Returns None if client not found in electronic_case DB.
        NULL fields shown as '[не заполнено в CRM]'.
        """
        case = await self._fetch_case(inn)
        if not case:
            logger.info("[ELECTRONIC_CASE] inn=%s not found", inn)
            return None

        docs = await self._fetch_documents(inn)
        checklist_str = self._build_checklist_summary(docs, case.get("checklist_completion"))

        # Stage with label
        stage_code = case.get("stage")
        stage_label = _fmt_stage(stage_code)
        stage_updated = case.get("stage_updated_at") or case.get("synced_at")
        stage_date = str(stage_updated)[:10] if stage_updated else None
        stage_str = f"{stage_label} (с {stage_date})" if stage_date else stage_label

        # Property summary
        has_prop = case.get("has_property")
        if has_prop is None:
            property_str = _NULL
        elif has_prop:
            count = case.get("property_count")
            property_str = f"есть ({count} объект(ов))" if count else "есть"
        else:
            property_str = "нет"

        # Payment schedule summary
        schedule = case.get("payment_schedule") or []
        if schedule:
            total_paid = sum(
                float(p["amount"]) for p in schedule if p.get("amount")
            )
            schedule_str = f"график на {len(schedule)} платежей, итого {int(total_paid):,} ₽".replace(",", " ")
        else:
            schedule_str = _NULL

        # Risk flags
        risk = case.get("risk_flags") or {}
        risk_items = []
        if risk.get("was_ip"):
            risk_items.append("был ИП")
        if risk.get("has_llc_shares"):
            risk_items.append("доля в ООО")
        if risk.get("has_guarantor"):
            risk_items.append("поручитель")
        if risk.get("alimony_debt"):
            risk_items.append("алименты")
        if risk.get("has_court_orders"):
            risk_items.append("судебные приказы")
        if risk.get("transactions_3y"):
            risk_items.append(f"сделки за 3 года: {risk['transactions_3y']}")
        risk_str = ", ".join(risk_items) if risk_items else "нет"

        # Null fields tracker
        null_fields = []
        def tracked(key: str, label: str, value) -> str:
            if value is None or value == "":
                null_fields.append(label)
                return _NULL
            return str(value)

        lines = [
            "[ЭЛЕКТРОННОЕ ДЕЛО КЛИЕНТА]",
            f"Клиент: {_fmt(case.get('full_name'))}",
            f"ИНН: {inn}",
            f"Телефон: {_fmt(case.get('phone'))}",
            f"Стадия: {stage_str}",
            "",
            f"Менеджер сопровождения (МС): {_fmt(case.get('assigned_user_name'))}",
            f"Арбитражный управляющий: {tracked('arbitration_manager', 'АУ', case.get('arbitration_manager'))}",
            f"Регион суда: {_fmt(case.get('court_region'))}",
            f"Дата подачи заявления: {_fmt(case.get('filing_actual_date') or case.get('filing_planned_date'))}",
            f"Первое заседание: {_fmt(case.get('first_hearing_date'))}",
            f"Последнее заседание: {_fmt(case.get('last_hearing_date'))}",
            "",
            f"Общий долг: {_fmt_money(case.get('total_debt_amount'))}",
            f"Кредиторов: {_fmt(case.get('creditors_count'))}",
            f"Ежемесячный платёж по кредитам: {_fmt_money(case.get('monthly_loan_payment'))}",
            f"Официальный доход: {_fmt_money(case.get('official_income'))}",
            f"Работодатель: {_fmt(case.get('current_employer'))}",
            "",
            f"Договор № {_fmt(case.get('contract_number'))} от {_fmt(case.get('contract_date'))}",
            f"Стоимость договора: {_fmt_money(case.get('contract_amount'))}",
            f"Ежемесячный платёж по договору: {_fmt_money(case.get('monthly_payment_amount'))}",
            f"График платежей: {schedule_str}",
            "",
            f"Имущество: {property_str}",
            f"Семейное положение: {_fmt(case.get('marital_status'))}",
            f"Иждивенцев: {_fmt(case.get('dependents_count'))}",
            f"Риски: {risk_str}",
            "",
            checklist_str,
        ]

        if null_fields:
            lines.append(f"\n[Не заполнено в CRM: {', '.join(null_fields)}]")

        return "\n".join(lines)

    async def get_assigned_user_id(self, inn: str) -> str | None:
        """Return Bitrix assigned_user_id for this INN, or None if not found."""
        case = await self._fetch_case(inn)
        if not case:
            return None
        value = case.get("assigned_user_id")
        return str(value) if value else None

    async def get_checklist_status(self, inn: str) -> str:
        """Return ✅/❌ document checklist for this client."""
        docs = await self._fetch_documents(inn)
        case = await self._fetch_case(inn)
        completion = case.get("checklist_completion") if case else None
        return self._build_checklist_detail(docs, completion)

    # ── Formatting helpers ────────────────────────────────────────────────────

    def _build_checklist_summary(self, docs: list[dict], completion) -> str:
        """One-line checklist summary for get_case_context."""
        verified = {
            d["doc_type"]
            for d in docs
            if d.get("status") == "verified" and d.get("doc_type") in CHECKLIST_ITEMS
        }
        total = len(CHECKLIST_ITEMS)
        done = len(verified)
        pct = f"{completion * 100:.0f}%" if completion is not None else f"{done / total * 100:.0f}%"
        return f"Документы: {done}/{total} сданы ({pct})"

    def _build_checklist_detail(self, docs: list[dict], completion) -> str:
        """Full ✅/❌ checklist for get_checklist_status."""
        verified = {
            d["doc_type"]
            for d in docs
            if d.get("status") == "verified" and d.get("doc_type") in CHECKLIST_ITEMS
        }
        rejected = {
            d["doc_type"]
            for d in docs
            if d.get("status") == "rejected" and d.get("doc_type") in CHECKLIST_ITEMS
        }

        lines = ["[ЧЕКЛИСТ ДОКУМЕНТОВ]"]
        for key, label in CHECKLIST_ITEMS.items():
            if key in verified:
                lines.append(f"✅ {label}")
            elif key in rejected:
                lines.append(f"❌ {label} (отклонён)")
            else:
                lines.append(f"⬜ {label}")

        total = len(CHECKLIST_ITEMS)
        done = len(verified)
        pct = f"{completion * 100:.0f}%" if completion is not None else f"{done / total * 100:.0f}%"
        lines.append(f"\nВыполнено: {done}/{total} ({pct})")
        return "\n".join(lines)
