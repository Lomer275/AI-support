from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def phone_share_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="\U0001f4f1 Поделиться номером телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f4ac Чат с Алиной", callback_data="menu_chat")],
            [
                InlineKeyboardButton(text="\U0001f4b0 Оплата", callback_data="menu_payment"),
                InlineKeyboardButton(text="\U0001f4cb Мои задачи", callback_data="menu_tasks"),
            ],
            [InlineKeyboardButton(text="\U0001f4c4 Документы", callback_data="menu_docs")],
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="\u2b05\ufe0f Главное меню", callback_data="back_menu")],
        ]
    )


remove_keyboard = ReplyKeyboardRemove()
