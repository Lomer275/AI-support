from aiogram import Dispatcher

from .start import router as start_router
from .contact import router as contact_router
from .callbacks import router as callbacks_router
from .text import router as text_router


def register_all_handlers(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(contact_router)
    dp.include_router(callbacks_router)
    dp.include_router(text_router)
