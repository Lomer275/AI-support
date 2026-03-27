import json
import logging

from aiogram import F, Router
from aiogram.types import Message

from keyboards import remove_keyboard
from services.bitrix import BitrixService
from services.openai_client import OpenAIService
from services.supabase import SupabaseService
from states import SessionState
from utils import moscow_now, normalize_phone

logger = logging.getLogger(__name__)
router = Router()

FALLBACK_PHONE_MISMATCH = "Номер не совпадает. Напишите нам в поддержку @Lobster_21, и мы разберёмся с вашей проблемой."


@router.message(F.contact)
async def handle_contact(
    message: Message,
    session: dict,
    supabase: SupabaseService,
    bitrix: BitrixService,
    openai_svc: OpenAIService,
    **kwargs,
):
    state = session.get("state")

    if state != SessionState.WAITING_PHONE:
        return

    # Normalize phones — all bitrix phones stored in context_data JSON
    tg_phone = normalize_phone(message.contact.phone_number or "")
    context = json.loads(session.get("context_data") or "{}")
    bitrix_phones = [normalize_phone(p) for p in context.get("bitrix_phones", []) if p]

    if tg_phone and bitrix_phones and tg_phone in bitrix_phones:
        # ── Phone matched: authorize ──
        deal_id = session.get("deal_id", "")
        contact_name = session.get("contact_name", "Клиент")
        timestamp = moscow_now()

        await bitrix.update_deal_authorized(deal_id, timestamp)

        await supabase.update_session(
            message.chat.id,
            state=SessionState.AUTHORIZED,
            contact_name=contact_name,
        )

        welcome = (
            f"\U0001f389 <b>{contact_name}</b>, добро пожаловать в личный кабинет!\n\n"
            "Я — Алина, ваш персональный менеджер по сопровождению "
            "процедуры банкротства в компании ArbitrA.\n\n"
            "Здесь вы можете задавать любые вопросы по вашему делу — я отвечу."
        )
        await message.answer(welcome, reply_markup=remove_keyboard)

    else:
        # ── Phone mismatch ──
        ai_text = await openai_svc.phone_mismatch()
        await message.answer(ai_text or FALLBACK_PHONE_MISMATCH)
