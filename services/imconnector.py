import logging
import time

import aiohttp

logger = logging.getLogger(__name__)

_OAUTH_URL = "https://oauth.bitrix24.tech/oauth/token/"


class ImConnectorService:
    """Send messages to Bitrix24 Open Lines via imconnector.send.messages.

    Uses OAuth2 (not webhook token). Automatically refreshes access_token
    on expiry before retrying the failed request once.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        bitrix_url: str,
        client_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        openline_id: str,
        connector_id: str,
    ) -> None:
        self._session = session
        # Ensure no trailing slash
        self._base = bitrix_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._refresh_tok = refresh_token
        self._openline_id = openline_id
        self._connector_id = connector_id

    # ── OAuth ────────────────────────────────────────────────────────────────

    async def _refresh_token(self) -> bool:
        """Refresh access_token via oauth.bitrix24.tech. Returns True on success."""
        params = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_tok,
        }
        try:
            async with self._session.post(_OAUTH_URL, data=params) as resp:
                data = await resp.json(content_type=None)
        except Exception:
            logger.exception("ImConnector: OAuth refresh request failed")
            return False

        new_access = data.get("access_token")
        new_refresh = data.get("refresh_token")
        if not new_access:
            logger.warning("ImConnector: OAuth refresh returned no access_token: %s", data)
            return False

        self._access_token = new_access
        if new_refresh:
            self._refresh_tok = new_refresh
        logger.info("ImConnector: access_token refreshed successfully")
        return True

    # ── Low-level call ───────────────────────────────────────────────────────

    async def _call(self, method: str, payload: dict) -> dict:
        """POST to Bitrix REST with Bearer token. On expired_token — refresh and retry once."""
        url = f"{self._base}/{method}.json"
        payload = {**payload, "auth": self._access_token}

        try:
            async with self._session.post(url, json=payload) as resp:
                data = await resp.json(content_type=None)
        except Exception:
            logger.exception("ImConnector: HTTP error calling %s", method)
            return {}

        error = data.get("error", "")
        if error == "expired_token":
            logger.info("ImConnector: token expired, refreshing...")
            if await self._refresh_token():
                payload["auth"] = self._access_token
                try:
                    async with self._session.post(url, json=payload) as resp:
                        data = await resp.json(content_type=None)
                except Exception:
                    logger.exception("ImConnector: HTTP error on retry after token refresh")
                    return {}
            else:
                logger.error("ImConnector: token refresh failed, cannot retry")
                return {}

        if "error" in data:
            logger.warning("ImConnector: API error for %s: %s", method, data)

        return data

    # ── Public API ───────────────────────────────────────────────────────────

    async def send_message(self, chat_id: int, user_name: str, text: str) -> bool:
        """Send a single message to Bitrix Open Lines.

        chat_id is used as chat.id — Bitrix stores it and echoes it back in
        operator-reply webhooks so we can route responses to the right Telegram user.
        Returns True on success.
        """
        payload = {
            "CONNECTOR": self._connector_id,
            "LINE": self._openline_id,
            "MESSAGES": [
                {
                    "user": {
                        "id": str(chat_id),
                        "name": user_name,
                        "phone": "",
                    },
                    "message": {
                        "id": "0",
                        "date": int(time.time()),
                        "text": text,
                    },
                    "chat": {
                        "id": str(chat_id),
                        "url": "",
                    },
                }
            ],
        }
        data = await self._call("imconnector.send.messages", payload)
        success = bool(data.get("result"))
        if not success:
            logger.warning(
                "ImConnector.send_message failed for chat_id=%s: %s", chat_id, data
            )
        return success

    async def send_escalation(
        self,
        chat_id: int,
        user_name: str,
        trigger_text: str,
        history: list[dict],
    ) -> bool:
        """Format dialog history + trigger question and send to Open Lines.

        history — list of dicts with keys 'role' ('user'|'assistant') and 'content'.
        Returns True on success.
        """
        logger.info(
            "ImConnectorService.send_escalation called for chat_id=%s", chat_id
        )

        history_lines: list[str] = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                history_lines.append(f"Пользователь: {content}")
            elif role == "assistant":
                history_lines.append(f"Бот: {content}")

        history_block = "\n".join(history_lines) if history_lines else "(история пуста)"

        text = (
            f"=== ИСТОРИЯ ДИАЛОГА С AI-БОТОМ ===\n"
            f"{history_block}\n"
            f"=== КОНЕЦ ИСТОРИИ ===\n"
            f"💬 Последний вопрос требует уточнения у специалиста: {trigger_text}"
        )

        return await self.send_message(chat_id, user_name, text)
