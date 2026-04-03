"""Aiohttp webhook server for Bitrix24 events.

Events handled on /webhook/bitrix/:
- ONIMCONNECTORMESSAGEADD       — operator message → forward to Telegram
- IMOPENLINES.SESSION.FINISH    — operator closed chat → notify client, reset escalation

Events handled on /bitrix/crm-deal-update:
- ONCRMDEALUPDATE / ONCRMDEALADD — deal changed → upsert in electronic_case Supabase
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
    """Extract chat_id from IMOPENLINES.SESSION.FINISH payload."""
    return (
        post.get("data[PARAMS][CONNECTOR_MID]")
        or post.get("data[MESSAGES][0][chat][id]")
    )


# ── Open Lines event handlers ────────────────────────────────────────────────

async def _handle_message(post: dict, bot: Bot, supabase: SupabaseService) -> None:
    """Forward operator message to Telegram client and update operator_last_reply_at."""
    logger.debug("ONIMCONNECTORMESSAGEADD raw payload: %s", post)
    parsed = _parse_message(post)
    raw_chat_id = parsed["chat_id"]
    # Fallback: в некоторых событиях Bitrix chat_id лежит только в CONNECTOR_MID.
    # CONNECTOR_MID в нашем коннекторе tg_alina_support соответствует Telegram chat_id —
    # это подтверждается симметрией с _parse_session_finish(), где CONNECTOR_MID — основной ключ.
    # Если после деплоя fallback сработает и сообщение уйдёт не туда — убрать эту ветку.
    if not raw_chat_id:
        raw_chat_id = post.get("data[PARAMS][CONNECTOR_MID]")
        if raw_chat_id:
            logger.info("ONIMCONNECTORMESSAGEADD: used CONNECTOR_MID fallback chat_id=%s", raw_chat_id)
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

    if not text and not files:
        logger.warning(
            "ONIMCONNECTORMESSAGEADD: chat_id=%s has empty text and no files, skipping send",
            chat_id,
        )
        return

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
            logger.warning("Failed to send file to chat_id=%s url=%s", chat_id, file_url)

    from utils import moscow_now
    await supabase.update_session(chat_id, operator_last_reply_at=moscow_now())
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

    await supabase.update_session(chat_id, escalated=False, operator_last_reply_at=None)

    try:
        await bot.send_message(
            chat_id,
            "Оператор завершил сессию. ИИ-ассистент снова готов помочь — напишите ваш вопрос.",
        )
    except Exception:
        logger.warning("Failed to notify client chat_id=%s about session finish", chat_id)

    logger.info("Session finish handled for chat_id=%s", chat_id)


# ── CRM Deal Update handler ──────────────────────────────────────────────────

async def _fetch_deal_with_contact(
    http_session, bitrix_base: str, deal_id: str
) -> tuple[dict | None, dict | None]:
    """Fetch deal + contact in one batch using Bitrix result chaining.

    Returns (deal, contact). contact may be None if CONTACT_ID is missing.
    """
    from services.cases_mapper import DEAL_SELECT

    select_qs = "&".join(f"select[]={f}" for f in DEAL_SELECT)
    contact_select = "select[]=ID&select[]=NAME&select[]=LAST_NAME&select[]=SECOND_NAME&select[]=PHONE"

    batch_data = [
        ("halt", "0"),
        ("cmd[deal]", f"crm.deal.get?ID={deal_id}&{select_qs}"),
        ("cmd[contact]", f"crm.contact.get?ID=$result[deal][CONTACT_ID]&{contact_select}"),
    ]

    try:
        async with http_session.post(f"{bitrix_base}/batch", data=batch_data) as resp:
            result = await resp.json(content_type=None)
    except Exception:
        logger.exception("[WEBHOOK] Bitrix batch request failed for deal_id=%s", deal_id)
        return None, None

    inner = result.get("result", {}).get("result", {})
    deal = inner.get("deal")
    contact = inner.get("contact")

    if not deal or not deal.get("ID"):
        logger.warning("[WEBHOOK] deal_id=%s not found in Bitrix response", deal_id)
        return None, None

    # contact may be {} or have an error if CONTACT_ID was missing — treat as None
    if not contact or not contact.get("ID"):
        contact = None

    return deal, contact


async def _handle_crm_deal_update(request: web.Request) -> web.Response:
    """Handle ONCRMDEALUPDATE / ONCRMDEALADD from Bitrix.

    Bitrix sends form-encoded body with:
        event=ONCRMDEALUPDATE
        data[FIELDS][ID]=<deal_id>
    """
    try:
        post = dict(await request.post())
    except Exception:
        logger.exception("[WEBHOOK] Failed to parse CRM deal update body")
        return web.Response(status=200, text="ok")

    event = post.get("event", "")
    deal_id = post.get("data[FIELDS][ID]")

    if not deal_id:
        logger.warning("[WEBHOOK] %s: no deal ID in payload", event)
        return web.Response(status=200, text="ok")

    logger.info("[WEBHOOK] %s deal_id=%s", event, deal_id)

    http_session = request.app["http_session"]
    bitrix_base = request.app["bitrix_base"]
    cases_url = request.app["cases_url"]
    cases_key = request.app["cases_key"]

    try:
        from services.cases_mapper import build_case_row, upsert_case, insert_communication

        deal, contact = await _fetch_deal_with_contact(http_session, bitrix_base, deal_id)
        if deal is None:
            return web.Response(status=200, text="ok")

        inn = (deal.get("UF_CRM_1751273997835") or "").strip()
        if not inn:
            logger.info("[WEBHOOK] deal_id=%s has no INN, skipping upsert", deal_id)
            return web.Response(status=200, text="ok")

        row = build_case_row(deal, contact)
        ok, err = await upsert_case(http_session, row, cases_url, cases_key)
        if ok:
            logger.info("[WEBHOOK] deal_id=%s upserted (stage=%s)", deal_id, deal.get("STAGE_ID"))
            comment = (deal.get("COMMENTS") or "").strip()
            if comment:
                await insert_communication(http_session, inn, deal_id, comment, cases_url, cases_key)
            # Check for new documents in deal folder (async, non-blocking)
            validator = request.app.get("document_validator")
            folder_url = deal.get("UF_CRM_1601916846")
            logger.info("[WEBHOOK] deal_id=%s validator=%s folder_url=%s",
                        deal_id, "set" if validator else "None", repr(folder_url))
            if validator and folder_url:
                import asyncio

                async def _run_validator():
                    try:
                        await validator.process_deal_files(inn, deal_id)
                    except Exception:
                        logger.exception("[VALIDATOR] task failed for deal_id=%s", deal_id)

                asyncio.create_task(_run_validator())
        else:
            logger.error("[WEBHOOK] Supabase upsert failed for deal_id=%s: %s", deal_id, err)

    except Exception:
        logger.exception("[WEBHOOK] Error processing deal_id=%s", deal_id)

    return web.Response(status=200, text="ok")


# ── Open Lines request handler ───────────────────────────────────────────────

async def handle_bitrix_webhook(request: web.Request) -> web.Response:
    """Entry point for Bitrix Open Lines events. Always returns 200."""
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
            await _handle_message(post, request.app["bot"], request.app["supabase"])
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

def create_webhook_app(
    bot: Bot,
    supabase: SupabaseService,
    http_session,
    bitrix_base: str,
    cases_url: str,
    cases_key: str,
    document_validator=None,
) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app["supabase"] = supabase
    app["http_session"] = http_session
    app["bitrix_base"] = bitrix_base
    app["cases_url"] = cases_url
    app["cases_key"] = cases_key
    app["document_validator"] = document_validator
    app.router.add_post("/webhook/bitrix/", handle_bitrix_webhook)
    app.router.add_post("/bitrix/crm-deal-update", _handle_crm_deal_update)
    return app
