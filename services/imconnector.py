import asyncio
import logging
import time

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=15)

logger = logging.getLogger(__name__)

_OAUTH_URL = "https://bitrix.express-bankrot.ru/oauth/token/"


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
        self._refresh_lock = asyncio.Lock()

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
            async with self._session.post(_OAUTH_URL, data=params, timeout=_TIMEOUT) as resp:
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
            async with self._session.post(url, json=payload, timeout=_TIMEOUT) as resp:
                data = await resp.json(content_type=None)
        except Exception:
            logger.exception("ImConnector: HTTP error calling %s", method)
            return {}

        error = data.get("error", "")
        if error == "expired_token":
            logger.info("ImConnector: token expired, refreshing...")
            async with self._refresh_lock:
                # Re-check after acquiring lock — another coroutine may have already refreshed
                if payload.get("auth") == self._access_token:
                    await self._refresh_token()
            payload["auth"] = self._access_token
            try:
                async with self._session.post(url, json=payload, timeout=_TIMEOUT) as resp:
                    data = await resp.json(content_type=None)
            except Exception:
                logger.exception("ImConnector: HTTP error on retry after token refresh")
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
        msg_id = f"{chat_id}_{int(time.time() * 1000)}"
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
                        "id": msg_id,
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
        logger.debug(
            "ImConnector.send_message payload for chat_id=%s: CONNECTOR=%s LINE=%s msg_id=%s text_preview=%r",
            chat_id,
            self._connector_id,
            self._openline_id,
            msg_id,
            text[:120] if text else "",
        )
        data = await self._call("imconnector.send.messages", payload)
        logger.debug("ImConnector.send_message response for chat_id=%s: %s", chat_id, data)
        success = bool(data.get("result"))
        if not success:
            logger.warning(
                "ImConnector.send_message failed for chat_id=%s: %s", chat_id, data
            )
        return success

    async def get_or_find_bitrix_chat_id(self, telegram_chat_id: int) -> str | None:
        """Return Bitrix Open Lines chat_id for the given Telegram chat_id.

        Queries imopenlines.chat.list filtered by USER_ID (connector MID).
        Returns str(chat_id) or None on error/empty.
        """
        try:
            data = await self._call("imopenlines.chat.list", {
                "filter": {"USER_ID": str(telegram_chat_id)},
                "limit": 1,
            })
            logger.info("T25: chat.list raw response for telegram_chat_id=%s: %s", telegram_chat_id, data)
            result = data.get("result") or []
            if result:
                chat_id = str(result[0].get("ID") or result[0].get("id") or "")
                if chat_id:
                    logger.info(
                        "T25: found bitrix_chat_id=%s for telegram_chat_id=%s",
                        chat_id, telegram_chat_id,
                    )
                    return chat_id
            logger.warning(
                "T25: imopenlines.chat.list returned no chats for telegram_chat_id=%s: %s",
                telegram_chat_id, data,
            )
            return None
        except Exception:
            logger.exception(
                "T25: get_or_find_bitrix_chat_id failed for telegram_chat_id=%s", telegram_chat_id
            )
            return None

    async def transfer_to_responsible(self, bitrix_chat_id: str, assigned_user_id: str) -> None:
        """Transfer Open Lines chat to the deal's responsible manager."""
        try:
            data = await self._call("imopenlines.chat.transfer", {
                "CHAT_ID": bitrix_chat_id,
                "USER_ID": assigned_user_id,
            })
            if data.get("result"):
                logger.info(
                    "T25: chat transferred — bitrix_chat_id=%s assigned_user_id=%s",
                    bitrix_chat_id, assigned_user_id,
                )
            else:
                logger.warning(
                    "T25: transfer_to_responsible unexpected response — bitrix_chat_id=%s user=%s resp=%s",
                    bitrix_chat_id, assigned_user_id, data,
                )
        except Exception:
            logger.warning(
                "T25: transfer_to_responsible failed — bitrix_chat_id=%s user=%s",
                bitrix_chat_id, assigned_user_id,
            )

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
