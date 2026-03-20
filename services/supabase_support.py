import logging

import aiohttp

logger = logging.getLogger(__name__)


class SupportSupabaseService:
    def __init__(self, session: aiohttp.ClientSession, url: str, anon_key: str):
        self._session = session
        self._base = f"{url}/rest/v1"
        self._rpc = f"{url}/rest/v1/rpc"
        self._headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
        }

    async def search_client_by_inn(self, inn: str) -> str:
        """Load client judicial documents via RPC search_client_by_inn.
        Returns formatted string or '[Данные не найдены]' if nothing found.
        """
        url = f"{self._rpc}/search_client_by_inn"
        try:
            async with self._session.post(
                url, json={"p_inn": inn}, headers=self._headers
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.warning("search_client_by_inn HTTP %s: %s", resp.status, text)
                    return "[Данные не найдены]"
                data = await resp.json()
        except Exception:
            logger.exception("search_client_by_inn request failed")
            return "[Данные не найдены]"

        if not data:
            return "[Данные не найдены]"

        parts = []
        for item in data:
            doc = item.get("record_data") or item
            text = doc.get("full_document_text") or ""
            if len(text) <= 20:
                continue
            doc_type = doc.get("document_type") or "Документ"
            doc_date = (doc.get("document_date") or "")[:10]  # only date part
            doc_name = doc.get("document_name") or ""
            header = f"[{doc_type}] {doc_date} — {doc_name}".strip(" —")
            parts.append(f"{header}\n{text[:3000]}")

        if not parts:
            return "[Данные не найдены]"

        return "\n\n".join(parts)

    async def get_chat_history(self, chat_id: int, limit: int = 10) -> list[dict]:
        """Return last `limit` messages for chat_id, oldest first."""
        url = (
            f"{self._base}/chat_history"
            f"?chat_id=eq.{chat_id}&order=created_at.asc&limit={limit}"
        )
        try:
            async with self._session.get(url, headers=self._headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.warning("get_chat_history HTTP %s: %s", resp.status, text)
                    return []
                data = await resp.json()
                return [{"role": r["role"], "content": r["content"]} for r in data]
        except Exception:
            logger.exception("get_chat_history failed for chat_id=%s", chat_id)
            return []

    async def save_chat_message(self, chat_id: int, role: str, content: str) -> None:
        """Insert one message into chat_history. Errors are logged, not raised."""
        url = f"{self._base}/chat_history"
        headers = {**self._headers, "Prefer": "return=minimal"}
        payload = {"chat_id": chat_id, "role": role, "content": content}
        try:
            async with self._session.post(url, json=payload, headers=headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.warning(
                        "save_chat_message HTTP %s: %s", resp.status, text
                    )
        except Exception:
            logger.exception(
                "save_chat_message failed for chat_id=%s role=%s", chat_id, role
            )
