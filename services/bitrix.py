import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

# Bitrix custom field IDs
FIELD_INN = "UF_CRM_1751273997835"
FIELD_AUTH_STATUS = "UF_CRM_1768296374"
FIELD_AUTH_TIMESTAMP = "UF_CRM_1768547250879"


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

        # Extract phone
        phones = contact_detail.get("PHONE", [])
        bitrix_phone = phones[0]["VALUE"] if phones else ""

        contacts_list = result.get("contacts", [])
        contact_id = str(contacts_list[0]["CONTACT_ID"]) if contacts_list else ""

        return {
            "deal_id": str(deal["ID"]),
            "contact_id": contact_id,
            "contact_name": full_name or "Клиент",
            "bitrix_phone": bitrix_phone,
            "inn": inn,
        }

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
