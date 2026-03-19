import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from keyboards import back_to_menu_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

SECTION_TEXTS = {
    "menu_chat": "\U0001f4ac <b>Чат с Алиной</b>\n\nЗадайте любой вопрос по вашему делу и я отвечу.",
    "menu_payment": "\U0001f4b0 <b>Оплата</b>\n\nРаздел в разработке. Обратитесь к менеджеру за реквизитами.",
    "menu_tasks": "\U0001f4cb <b>Мои задачи</b>\n\nРаздел в разработке. Скоро здесь появятся ваши задачи из Bitrix.",
    "menu_docs": "\U0001f4c4 <b>Документы</b>\n\nРаздел в разработке. Скоро здесь можно будет загружать документы.",
}


@router.callback_query(F.data == "back_menu")
async def handle_back_menu(callback: CallbackQuery, **kwargs):
    await callback.answer()
    await callback.message.edit_text(
        "\U0001f44b Выберите раздел:",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.in_(SECTION_TEXTS))
async def handle_section(callback: CallbackQuery, **kwargs):
    await callback.answer()
    text = SECTION_TEXTS[callback.data]
    await callback.message.edit_text(
        text,
        reply_markup=back_to_menu_keyboard(),
    )
