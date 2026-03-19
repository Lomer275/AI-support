import logging

from aiogram import F, Router
from aiogram.types import Message

from keyboards import main_menu_keyboard, remove_keyboard
from services.bitrix import BitrixService
from services.openai_client import OpenAIService
from services.supabase import SupabaseService
from states import SessionState
from utils import moscow_now, normalize_phone

logger = logging.getLogger(__name__)
router = Router()

FALLBACK_PHONE_MISMATCH = "Номер не совпадает. Обратитесь к менеджеру."


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

    # Normalize phones
    tg_phone = normalize_phone(message.contact.phone_number or "")
    bitrix_phone = normalize_phone(session.get("bitrix_phone") or "")

    if tg_phone and bitrix_phone and tg_phone == bitrix_phone:
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

        # Message 1: welcome to personal cabinet
        welcome = (
            f"\U0001f389 <b>{contact_name}</b>, добро пожаловать в личный кабинет!\n\n"
            "Я — Алина, ваш персональный менеджер, и теперь у нас с вами "
            "есть всё необходимое для работы по делу.\n\n"
            "Вот что я могу для вас сделать:\n"
            "\U0001f4ac <b>Чат со мной</b> — задавайте любые вопросы по делу, я отвечу\n"
            "\U0001f4b0 <b>Оплата</b> — внесите платёж по договору или судебные расходы\n"
            "\U0001f4cb <b>Мои задачи</b> — ваш список дел с дедлайнами от команды\n"
            "\U0001f4c4 <b>Документы</b> — загружайте файлы, я передам их в работу"
        )
        await message.answer(welcome, reply_markup=remove_keyboard)

        # Message 2: menu buttons
        await message.answer("Выберите раздел:", reply_markup=main_menu_keyboard())

    else:
        # ── Phone mismatch ──
        ai_text = await openai_svc.phone_mismatch()
        await message.answer(ai_text or FALLBACK_PHONE_MISMATCH)
