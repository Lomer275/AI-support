import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher
from aiohttp import web
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import settings
from handlers import register_all_handlers
from middlewares.session import SessionMiddleware
from services.supabase import SupabaseService
from services.bitrix import BitrixService
from services.openai_client import OpenAIService
from services.supabase_support import SupportSupabaseService
from services.support import SupportService
from services.evaluator import EvaluatorService
from services.imconnector import ImConnectorService
from webhook_server import create_webhook_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    bot_session = AiohttpSession(proxy=settings.openai_proxy) if settings.openai_proxy else None
    bot = Bot(
        token=settings.bot_token,
        session=bot_session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Shared HTTP session
    http_session = aiohttp.ClientSession()

    # Init services
    supabase = SupabaseService(http_session)
    bitrix = BitrixService(http_session)
    openai_svc = OpenAIService(http_session)
    supabase_support = SupportSupabaseService(
        http_session,
        settings.supabase_support_url,
        settings.supabase_support_anon_key,
    )
    evaluator = EvaluatorService(
        http_session=http_session,
        openai_api_key=settings.openai_api_key,
        model=settings.openai_model_coordinator,
        openai_proxy=settings.openai_proxy,
    )
    imconnector_svc = ImConnectorService(
        session=http_session,
        bitrix_url=settings.bitrix_url,
        client_id=settings.bitrix_oauth_client_id,
        client_secret=settings.bitrix_oauth_client_secret,
        access_token=settings.bitrix_oauth_access_token,
        refresh_token=settings.bitrix_oauth_refresh_token,
        openline_id=settings.bitrix_openline_id,
        connector_id=settings.bitrix_connector_id,
    )
    support_svc = SupportService(
        http_session=http_session,
        supabase_support=supabase_support,
        openai_api_key=settings.openai_api_key,
        model_support=settings.openai_model_support,
        model_coordinator=settings.openai_model_coordinator,
        openai_proxy=settings.openai_proxy,
        evaluator=evaluator,
    )

    # Pass services to handlers via workflow_data
    dp["supabase"] = supabase
    dp["bitrix"] = bitrix
    dp["openai_svc"] = openai_svc
    dp["support_svc"] = support_svc
    dp["imconnector_svc"] = imconnector_svc

    # Register middleware
    dp.message.outer_middleware(SessionMiddleware(supabase))
    dp.callback_query.outer_middleware(SessionMiddleware(supabase))

    # Register handlers
    register_all_handlers(dp)

    # Webhook server (Bitrix operator replies + CRM deal updates)
    webhook_app = create_webhook_app(
        bot=bot,
        supabase=supabase,
        http_session=http_session,
        bitrix_base=settings.bitrix_webhook_base,
        cases_url=settings.supabase_cases_url,
        cases_key=settings.supabase_cases_anon_key,
    )
    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.webhook_port)
    await site.start()
    logger.info("Webhook server started on port %s", settings.webhook_port)

    # ── Escalation watchdog ───────────────────────────────────────────────────
    async def escalation_watchdog():
        """Check every 5 min for escalated sessions with no operator reply > 1 hour.

        Resets escalated=false and notifies the client that AI is back.
        """
        while True:
            await asyncio.sleep(5 * 60)
            try:
                timed_out = await supabase.get_escalated_sessions(timeout_minutes=60)
                for row in timed_out:
                    chat_id = int(row["chat_id"])
                    await supabase.update_session(chat_id, escalated=False, operator_last_reply_at=None)
                    try:
                        await bot.send_message(
                            chat_id,
                            "Похоже, специалист пока не ответил. Я снова здесь — чем могу помочь?",
                        )
                    except Exception:
                        logger.warning("Watchdog: failed to notify chat_id=%s", chat_id)
                    logger.info("Watchdog: auto-returned AI for chat_id=%s", chat_id)
            except Exception:
                logger.exception("Escalation watchdog iteration failed")

    wd_task = asyncio.create_task(escalation_watchdog())

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        wd_task.cancel()
        await runner.cleanup()
        await http_session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
