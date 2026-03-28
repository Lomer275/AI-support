import logging
from typing import Any

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session
        self._base = f"{settings.supabase_url}/rest/v1"
        self._headers = {
            "apikey": settings.supabase_anon_key,
            "Authorization": f"Bearer {settings.supabase_anon_key}",
            "Content-Type": "application/json",
        }

    async def get_or_create_session(
        self,
        chat_id: int,
        update_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> dict[str, Any]:
        """Call RPC get_or_create_session. Returns session dict with is_duplicate flag."""
        url = f"{self._base}/rpc/get_or_create_session"
        payload = {
            "p_chat_id": str(chat_id),
            "p_update_id": str(update_id),
            "p_username": username or "",
            "p_first_name": first_name or "",
        }
        try:
            async with self._session.post(url, json=payload, headers=self._headers) as resp:
                data = await resp.json()
                # RPC may return array or object
                if isinstance(data, list):
                    return data[0] if data else {}
                return data
        except Exception:
            logger.exception("Supabase get_or_create_session failed")
            return {}

    async def update_session(self, chat_id: int, **fields: Any) -> bool:
        """PATCH bot_sessions by chat_id."""
        url = f"{self._base}/bot_sessions?chat_id=eq.{chat_id}"
        headers = {**self._headers, "Prefer": "return=minimal"}
        try:
            async with self._session.patch(url, json=fields, headers=headers) as resp:
                return resp.status < 300
        except Exception:
            logger.exception("Supabase update_session failed")
            return False

    async def get_escalated_sessions(self, timeout_minutes: int = 60) -> list[dict]:
        """Return sessions where escalated=true and escalated_at older than timeout_minutes.

        Used by the watchdog to auto-return clients to AI after operator inactivity.
        """
        from datetime import datetime, timezone, timedelta
        # moscow_now() stores timestamps as Moscow-time strings without TZ offset.
        # Compute cutoff in the same "naive Moscow" format so the comparison is consistent.
        now_msk = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
        cutoff = (now_msk - timedelta(minutes=timeout_minutes)).strftime("%Y-%m-%dT%H:%M:%S")
        # Return sessions timed out relative to last operator activity.
        # Use COALESCE logic via PostgREST OR:
        #   operator replied and last reply is old  →  operator_last_reply_at < cutoff
        #   operator never replied  →  operator_last_reply_at IS NULL AND escalated_at < cutoff
        or_filter = (
            f"or=(operator_last_reply_at.lt.{cutoff},"
            f"and(operator_last_reply_at.is.null,escalated_at.lt.{cutoff}))"
        )
        url = (
            f"{self._base}/bot_sessions"
            f"?escalated=eq.true"
            f"&{or_filter}"
            f"&select=chat_id,contact_name"
        )
        try:
            async with self._session.get(url, headers=self._headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.warning("get_escalated_sessions HTTP %s: %s", resp.status, text[:200])
                    return []
                return await resp.json()
        except Exception:
            logger.exception("get_escalated_sessions failed")
            return []
