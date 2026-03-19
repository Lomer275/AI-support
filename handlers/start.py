import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards import main_menu_keyboard, remove_keyboard
from services.supabase import SupabaseService
from states import SessionState

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: dict, supabase: SupabaseService, **kwargs):
    first_name = message.from_user.first_name if message.from_user else None
    chat_id = message.chat.id

    if session.get("state") == SessionState.AUTHORIZED:
        name = session.get("contact_name") or first_name or "вы"
        await message.answer(
            f"✅ {name}, вы уже авторизованы. Чем могу помочь?",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Reset session to waiting_inn
    await supabase.update_session(
        chat_id,
        state="waiting_inn",
        inn=None,
        deal_id=None,
        contact_id=None,
        contact_name=None,
        bitrix_phone=None,
        error_count=0,
    )

    greeting = f"{first_name}, добро пожаловать!" if first_name else "Добро пожаловать!"

    text = (
        f"\U0001f44b {greeting}\n\n"
        "Я — Алина, ваш персональный менеджер по сопровождению "
        "процедуры банкротства в компании ArbitrA.\n\n"
        "Я буду рядом на каждом шаге:\n"
        "\U0001f4ac Отвечу на любые вопросы по вашему делу\n"
        "\U0001f4b0 Помогу с оплатой услуг и судебных расходов\n"
        "\U0001f4cb Буду следить за задачами и дедлайнами\n"
        "\U0001f4c4 Приму документы и передам в работу\n\n"
        "Для входа в личный кабинет мне нужно вас авторизовать.\n"
        "Введите, пожалуйста, ваш <b>ИНН</b> (12 цифр):"
    )

    await message.answer(text, reply_markup=remove_keyboard)
