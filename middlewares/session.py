import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from services.supabase import SupabaseService

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseMiddleware):
    def __init__(self, supabase: SupabaseService):
        self._supabase = supabase

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Extract chat_id, update_id, username, first_name
        if isinstance(event, Message):
            chat_id = event.chat.id
            update_id = data.get("event_update", event).update_id if hasattr(data.get("event_update", event), "update_id") else 0
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id if event.message else 0
            update_id = data.get("event_update", event).update_id if hasattr(data.get("event_update", event), "update_id") else 0
            user = event.from_user
        else:
            return await handler(event, data)

        if not chat_id:
            return await handler(event, data)

        username = user.username if user else None
        first_name = user.first_name if user else None

        session = await self._supabase.get_or_create_session(
            chat_id=chat_id,
            update_id=update_id,
            username=username,
            first_name=first_name,
        )

        if not session:
            logger.warning("Empty session for chat_id=%s, proceeding with default", chat_id)
            session = {"state": "waiting_inn", "is_duplicate": False}

        # Duplicate check
        if session.get("is_duplicate"):
            logger.debug("Duplicate update_id=%s for chat_id=%s, dropping", update_id, chat_id)
            return

        data["session"] = session
        data["supabase"] = self._supabase
        return await handler(event, data)
