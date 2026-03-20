import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message

from keyboards import back_to_menu_keyboard, main_menu_keyboard, phone_share_keyboard
from services.bitrix import BitrixService
from services.openai_client import OpenAIService
from services.supabase import SupabaseService
from services.support import SupportService
from states import SessionState
from utils import extract_inn

logger = logging.getLogger(__name__)
router = Router()

# Fallback texts when AI fails
FALLBACK_INN_NOT_FOUND = "ИНН не найден. Проверьте правильность и повторите."
FALLBACK_INN_NOT_FOUND_ESCALATE = "ИНН не найден. Если у вас возникли трудности — напишите нам в поддержку @Lobster_21, и мы разберёмся."
FALLBACK_NO_INN = "Пожалуйста, введите ваш ИНН — 12 цифр (например: 123456789012)."
FALLBACK_NO_INN_ESCALATE = "Пожалуйста, введите ваш ИНН — 12 цифр. Если у вас возникли трудности — напишите нам в поддержку @Lobster_21, и мы разберёмся."
FALLBACK_WAITING_PHONE = (
    "Нажмите кнопку \U0001f4f1 Поделиться номером телефона ниже, "
    "чтобы я могла подтвердить вашу личность."
)
FALLBACK_ALINA = "Извините, не могу ответить сейчас. Обратитесь к менеджеру."
FALLBACK_BITRIX_UNAVAILABLE = "Возникли временные технические проблемы. Попробуйте ещё раз через несколько минут."


@router.message(F.text)
async def handle_text(
    message: Message,
    bot: Bot,
    session: dict,
    supabase: SupabaseService,
    bitrix: BitrixService,
    openai_svc: OpenAIService,
    support_svc: SupportService,
    **kwargs,
):
    state = session.get("state", "waiting_inn")
    text = message.text or ""

    if state == SessionState.WAITING_INN:
        await _handle_waiting_inn(message, text, session, supabase, bitrix, openai_svc)
    elif state == SessionState.WAITING_PHONE:
        await _handle_waiting_phone(message, text, openai_svc)
    elif state == SessionState.AUTHORIZED:
        await _handle_authorized(message, bot, text, session, openai_svc, support_svc)
    else:
        # Unknown state — treat as waiting_inn
        await _handle_waiting_inn(message, text, session, supabase, bitrix, openai_svc)


async def _handle_waiting_inn(
    message: Message,
    text: str,
    session: dict,
    supabase: SupabaseService,
    bitrix: BitrixService,
    openai_svc: OpenAIService,
):
    inn, digit_count = extract_inn(text)

    if inn:
        # INN found — search in Bitrix
        try:
            result = await bitrix.search_by_inn(inn)
        except Exception:
            logger.exception("Bitrix unavailable during INN search")
            await message.answer(FALLBACK_BITRIX_UNAVAILABLE)
            return

        if result:
            # Deal found — move to waiting_phone
            await supabase.update_session(
                message.chat.id,
                state=SessionState.WAITING_PHONE,
                inn=result["inn"],
                deal_id=result["deal_id"],
                contact_id=result["contact_id"],
                contact_name=result["contact_name"],
                bitrix_phone=result["bitrix_phone"],
            )

            await message.answer(
                "\u2705 ИНН найден!\n\n"
                "Для подтверждения личности нажмите кнопку ниже, "
                "чтобы поделиться вашим номером телефона:",
                reply_markup=phone_share_keyboard(),
            )
        else:
            # INN not in Bitrix — increment error counter
            error_count = session.get("error_count", 0) + 1
            await supabase.update_session(message.chat.id, error_count=error_count)
            escalate = error_count >= 2
            ai_text = await openai_svc.inn_not_found(escalate=escalate)
            await message.answer(ai_text or (FALLBACK_INN_NOT_FOUND_ESCALATE if escalate else FALLBACK_INN_NOT_FOUND))
    else:
        # No valid INN in message — increment error counter
        error_count = session.get("error_count", 0) + 1
        await supabase.update_session(message.chat.id, error_count=error_count)
        escalate = error_count >= 2
        ai_text = await openai_svc.no_inn_in_text(text, digit_count, escalate=escalate)
        await message.answer(ai_text or (FALLBACK_NO_INN_ESCALATE if escalate else FALLBACK_NO_INN))


async def _handle_waiting_phone(
    message: Message,
    text: str,
    openai_svc: OpenAIService,
):
    ai_text = await openai_svc.waiting_for_phone(text)
    await message.answer(
        ai_text or FALLBACK_WAITING_PHONE,
        reply_markup=phone_share_keyboard(),
    )


async def _handle_authorized(
    message: Message,
    bot: Bot,
    text: str,
    session: dict,
    openai_svc: OpenAIService,
    support_svc: SupportService,
):
    if not text.strip():
        # Empty text — show menu
        name = session.get("contact_name") or session.get("first_name") or "Клиент"
        await message.answer(
            f"\U0001f44b {name}! Выберите раздел:",
            reply_markup=main_menu_keyboard(),
        )
        return

    chat_id = message.chat.id
    contact_name = session.get("contact_name") or session.get("first_name") or "Клиент"
    inn = session.get("inn") or ""

    # Send initial typing indicator and start background loop
    await bot.send_chat_action(chat_id, ChatAction.TYPING)

    stop_typing = asyncio.Event()

    async def _typing_loop():
        while not stop_typing.is_set():
            await asyncio.sleep(4)
            if not stop_typing.is_set():
                await bot.send_chat_action(chat_id, ChatAction.TYPING)

    typing_task = asyncio.create_task(_typing_loop())

    try:
        ai_text = await support_svc.answer(chat_id, inn, text, contact_name)
    except Exception:
        logger.exception("SupportService.answer failed, falling back to chat_as_alina")
        try:
            ai_text = await openai_svc.chat_as_alina(text, contact_name)
        except Exception:
            logger.exception("chat_as_alina fallback also failed")
            ai_text = None
    finally:
        stop_typing.set()
        typing_task.cancel()

    await message.answer(
        ai_text or FALLBACK_ALINA,
        reply_markup=back_to_menu_keyboard(),
    )
