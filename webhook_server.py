"""Aiohttp webhook server for Bitrix24 Open Lines operator replies.

Bitrix sends application/x-www-form-urlencoded POST to /webhook/bitrix/
when an operator writes a message or closes a session.

Events handled:
- ONIMCONNECTORMESSAGEADD  — new message from operator → forward to Telegram
- IMOPENLINES.SESSION.FINISH — operator closed chat → notify client, reset escalated flag
"""
import logging
import re

from aiogram import Bot
from aiohttp import web

from services.supabase import SupabaseService

logger = logging.getLogger(__name__)


# ── BB-code cleaner ──────────────────────────────────────────────────────────

def _clean_bb_codes(text: str) -> str:
    """Strip Bitrix BB formatting codes from operator messages."""
    if not text:
        return ""
    text = text.replace("[br]", "\n").replace("[BR]", "\n")
    text = re.sub(r"\[/?b\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/?i\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/?u\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[/?s\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[url=[^\]]*\]([^\[]*)\[/url\]", r"\1", text, flags=re.IGNORECASE)
    return text.strip()


# ── Payload parsers ──────────────────────────────────────────────────────────

def _parse_message(post: dict) -> dict:
    """Extract fields from ONIMCONNECTORMESSAGEADD payload."""
    chat_id = post.get("data[MESSAGES][0][chat][id]")
    text = post.get("data[MESSAGES][0][message][text]", "")

    files = []
    i = 0
    while True:
        link = post.get(f"data[MESSAGES][0][message][files][{i}][link]")
        if not link:
            break
        files.append({
            "type": post.get(f"data[MESSAGES][0][message][files][{i}][type]", "file"),
            "link": link,
            "name": post.get(f"data[MESSAGES][0][message][files][{i}][name]", "file"),
        })
        i += 1

    return {"chat_id": chat_id, "text": text, "files": files}


def _parse_session_finish(post: dict) -> str | None:
    """Extract chat_id from IMOPENLINES.SESSION.FINISH payload.

    Bitrix sends the Telegram chat_id in CONNECTOR_MID for this event.
    """
    return (
        post.get("data[PARAMS][CONNECTOR_MID]")
        or post.get("data[MESSAGES][0][chat][id]")
    )


# ── Event handlers ───────────────────────────────────────────────────────────

async def _handle_message(post: dict, bot: Bot) -> None:
    """Forward operator message to Telegram client."""
    parsed = _parse_message(post)
    raw_chat_id = parsed["chat_id"]
    if not raw_chat_id:
        logger.warning("ONIMCONNECTORMESSAGEADD: no chat_id, skipping")
        return

    try:
        chat_id = int(raw_chat_id)
    except (ValueError, TypeError):
        logger.warning("ONIMCONNECTORMESSAGEADD: invalid chat_id=%s", raw_chat_id)
        return

    text = _clean_bb_codes(parsed["text"])
    files = parsed["files"]

    if text:
        await bot.send_message(chat_id, text)

    for file in files:
        file_url = file["link"]
        if not file_url:
            continue
        try:
            if file["type"] == "image":
                await bot.send_photo(chat_id, file_url)
            else:
                await bot.send_document(chat_id, file_url)
        except Exception:
            logger.warning(
                "Failed to send file to chat_id=%s url=%s", chat_id, file_url
            )

    logger.info("Operator message forwarded to chat_id=%s", chat_id)


async def _handle_session_finish(
    post: dict, bot: Bot, supabase: SupabaseService
) -> None:
    """Notify client and reset escalated flag when operator closes chat."""
    raw_chat_id = _parse_session_finish(post)
    if not raw_chat_id:
        logger.warning("IMOPENLINES.SESSION.FINISH: no chat_id, skipping")
        return

    try:
        chat_id = int(raw_chat_id)
    except (ValueError, TypeError):
        logger.warning("SESSION.FINISH: invalid chat_id=%s", raw_chat_id)
        return

    # Reset escalation flag (field added in T16; update_session is a no-op if absent)
    await supabase.update_session(chat_id, escalated=False)

    try:
        await bot.send_message(
            chat_id,
            "Оператор завершил сессию. ИИ-ассистент снова готов помочь — напишите ваш вопрос.",
        )
    except Exception:
        logger.warning("Failed to notify client chat_id=%s about session finish", chat_id)

    logger.info("Session finish handled for chat_id=%s", chat_id)


# ── Request handler ──────────────────────────────────────────────────────────

async def handle_bitrix_webhook(request: web.Request) -> web.Response:
    """Entry point for all Bitrix Open Lines events.

    Always returns 200 so Bitrix does not retry the request.
    """
    try:
        post = await request.post()
        post = dict(post)
    except Exception:
        logger.exception("Failed to parse webhook body")
        return web.Response(status=200, text="ok")

    connector = post.get("data[CONNECTOR]")
    event = post.get("event") or post.get("data[EVENT]", "")

    logger.info("Bitrix webhook: event=%s connector=%s", event, connector)

    try:
        if event == "ONIMCONNECTORMESSAGEADD":
            await _handle_message(post, request.app["bot"])
        elif event == "IMOPENLINES.SESSION.FINISH":
            await _handle_session_finish(
                post, request.app["bot"], request.app["supabase"]
            )
        else:
            logger.debug("Unhandled event=%s, ignoring", event)
    except Exception:
        logger.exception("Error handling webhook event=%s", event)

    return web.Response(status=200, text="ok")


# ── App factory ──────────────────────────────────────────────────────────────

def create_webhook_app(bot: Bot, supabase: SupabaseService) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app["supabase"] = supabase
    app.router.add_post("/webhook/bitrix/", handle_bitrix_webhook)
    return app
