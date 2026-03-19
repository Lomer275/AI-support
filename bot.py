import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from handlers import register_all_handlers
from middlewares.session import SessionMiddleware
from services.supabase import SupabaseService
from services.bitrix import BitrixService
from services.openai_client import OpenAIService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Shared HTTP session
    http_session = aiohttp.ClientSession()

    # Init services
    supabase = SupabaseService(http_session)
    bitrix = BitrixService(http_session)
    openai_svc = OpenAIService(http_session)

    # Pass services to handlers via workflow_data
    dp["supabase"] = supabase
    dp["bitrix"] = bitrix
    dp["openai_svc"] = openai_svc

    # Register middleware
    dp.message.outer_middleware(SessionMiddleware(supabase))
    dp.callback_query.outer_middleware(SessionMiddleware(supabase))

    # Register handlers
    register_all_handlers(dp)

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        await http_session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
