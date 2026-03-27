"""Manual test for ImConnectorService.send_escalation().

Run from project root:
    python scripts/test_imconnector.py
"""
import asyncio
import logging

import aiohttp
from dotenv import load_dotenv

load_dotenv()

from config import settings
from services.imconnector import ImConnectorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


TEST_CHAT_ID = 123456789
TEST_USER_NAME = "Тест Тестов"
TEST_TRIGGER = "Хочу поговорить с менеджером"
TEST_HISTORY = [
    {"role": "user", "content": "Когда состоится следующее заседание суда?"},
    {"role": "assistant", "content": "По вашему делу заседание запланировано на апрель 2026 года."},
    {"role": "user", "content": "Хочу поговорить с менеджером"},
]


async def test_error_scenario(session: aiohttp.ClientSession) -> None:
    """KP4: broken URL — should log warning, return False, not crash."""
    print("\n--- Сценарий ошибки: неверный BITRIX_URL ---")
    svc = ImConnectorService(
        session=session,
        bitrix_url="https://invalid.nonexistent-host-xyz.ru/rest/",
        client_id=settings.bitrix_oauth_client_id,
        client_secret=settings.bitrix_oauth_client_secret,
        access_token="bad_token",
        refresh_token="bad_refresh",
        openline_id=settings.bitrix_openline_id,
        connector_id=settings.bitrix_connector_id,
    )
    ok = await svc.send_escalation(
        chat_id=TEST_CHAT_ID,
        user_name=TEST_USER_NAME,
        trigger_text=TEST_TRIGGER,
        history=TEST_HISTORY,
    )
    if not ok:
        print("OK: send_escalation() вернул False, бот не упал")
    else:
        print("UNEXPECTED: вернул True при сломанном URL")


async def test_happy_path(session: aiohttp.ClientSession) -> None:
    """Happy path: реальный вызов."""
    print("\n--- Happy path ---")
    svc = ImConnectorService(
        session=session,
        bitrix_url=settings.bitrix_url,
        client_id=settings.bitrix_oauth_client_id,
        client_secret=settings.bitrix_oauth_client_secret,
        access_token=settings.bitrix_oauth_access_token,
        refresh_token=settings.bitrix_oauth_refresh_token,
        openline_id=settings.bitrix_openline_id,
        connector_id=settings.bitrix_connector_id,
    )
    print(f"  connector_id : {settings.bitrix_connector_id}")
    print(f"  openline_id  : {settings.bitrix_openline_id}")
    ok = await svc.send_escalation(
        chat_id=TEST_CHAT_ID,
        user_name=TEST_USER_NAME,
        trigger_text=TEST_TRIGGER,
        history=TEST_HISTORY,
    )
    if ok:
        print("OK: send_escalation() вернул True")
    else:
        print("FAIL: send_escalation() вернул False")


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        await test_error_scenario(session)
        await test_happy_path(session)


asyncio.run(main())
