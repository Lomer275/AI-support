"""One-time sync script: Bitrix24 active deals → Supabase electronic_case.

Populates: cases (core profile), communications (deal comments).

Usage:
    python scripts/sync_bitrix_to_cases.py            # full run (~1000 deals)
    python scripts/sync_bitrix_to_cases.py --limit 5  # smoke test (5 deals)
"""

import argparse
import asyncio
import logging
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import aiohttp
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sync_bitrix")

from services.cases_mapper import (
    DEAL_SELECT,
    build_case_row,
    upsert_case,
    insert_communication,
)

# ── Config ─────────────────────────────────────────────────────────────────────

BITRIX_BASE = os.environ["BITRIX_WEBHOOK_BASE"]
CASES_URL = os.environ["SUPABASE_CASES_URL"]
CASES_KEY = os.environ["SUPABASE_CASES_ANON_KEY"]

DEAL_PAGE_SIZE = 50
REQUEST_DELAY = 0.5  # seconds between Bitrix requests


# ── Bitrix API ─────────────────────────────────────────────────────────────────

async def fetch_deals_page(session: aiohttp.ClientSession, start: int) -> list[dict]:
    """Fetch one page of active deals (CATEGORY_ID=4, STAGE_SEMANTIC_ID=P)."""
    data = [
        ("filter[CATEGORY_ID]", "4"),
        ("filter[STAGE_SEMANTIC_ID]", "P"),
        ("order[DATE_CREATE]", "ASC"),
        ("start", str(start)),
    ]
    for field in DEAL_SELECT:
        data.append(("select[]", field))

    async with session.post(f"{BITRIX_BASE}/crm.deal.list", data=data) as resp:
        result = await resp.json(content_type=None)

    return result.get("result", [])


async def fetch_users_batch(
    session: aiohttp.ClientSession, user_ids: list[str]
) -> dict[str, str]:
    """Batch-fetch user full names by ID. Returns {user_id: full_name}."""
    if not user_ids:
        return {}

    data = [("halt", "0")]
    for uid in user_ids:
        data.append((
            f"cmd[u{uid}]",
            f"user.get?ID={uid}&select[]=ID&select[]=NAME&select[]=LAST_NAME&select[]=SECOND_NAME",
        ))

    async with session.post(f"{BITRIX_BASE}/batch", data=data) as resp:
        result = await resp.json(content_type=None)

    users = {}
    inner = result.get("result", {}).get("result", {})
    for uid in user_ids:
        raw = inner.get(f"u{uid}")
        if isinstance(raw, list) and raw:
            u = raw[0]
        elif isinstance(raw, dict) and raw.get("ID"):
            u = raw
        else:
            continue
        name = " ".join(p for p in [u.get("LAST_NAME", ""), u.get("NAME", ""), u.get("SECOND_NAME", "")] if p).strip()
        if name:
            users[str(uid)] = name
    return users


async def fetch_contacts_batch(
    session: aiohttp.ClientSession, contact_ids: list[str]
) -> dict[str, dict]:
    """Batch-fetch contact details. Returns {contact_id: contact_dict}."""
    if not contact_ids:
        return {}

    data = [("halt", "0")]
    for cid in contact_ids:
        data.append((
            f"cmd[c{cid}]",
            f"crm.contact.get?ID={cid}&select[]=ID&select[]=NAME&select[]=LAST_NAME&select[]=SECOND_NAME&select[]=PHONE",
        ))

    async with session.post(f"{BITRIX_BASE}/batch", data=data) as resp:
        result = await resp.json(content_type=None)

    contacts = {}
    inner = result.get("result", {}).get("result", {})
    for cid in contact_ids:
        c = inner.get(f"c{cid}")
        if c and c.get("ID"):
            contacts[str(cid)] = c
    return contacts


# ── Main ───────────────────────────────────────────────────────────────────────

async def run(limit: int | None) -> None:
    stats = {"processed": 0, "skipped_no_inn": 0, "skipped_no_contact": 0, "errors": 0}
    skipped_ids: list[str] = []

    async with aiohttp.ClientSession() as session:
        start = 0
        total_fetched = 0

        while True:
            logger.info("Fetching deals start=%d...", start)
            deals = await fetch_deals_page(session, start)
            await asyncio.sleep(REQUEST_DELAY)

            if not deals:
                break

            total_fetched += len(deals)

            # Apply --limit
            if limit is not None:
                remaining = limit - stats["processed"] - stats["skipped_no_inn"] - stats["skipped_no_contact"]
                deals = deals[:remaining]

            # Filter deals without INN immediately
            valid_deals = []
            for d in deals:
                inn = (d.get("UF_CRM_1751273997835") or "").strip()
                if not inn:
                    stats["skipped_no_inn"] += 1
                    skipped_ids.append(f"deal_{d['ID']}_no_inn")
                    continue
                valid_deals.append(d)

            # Batch-fetch contacts and managers for this page
            contact_ids = list({
                str(d["CONTACT_ID"])
                for d in valid_deals
                if d.get("CONTACT_ID")
            })
            contacts: dict[str, dict] = {}
            if contact_ids:
                contacts = await fetch_contacts_batch(session, contact_ids)
                await asyncio.sleep(REQUEST_DELAY)

            user_ids = list({
                str(d["ASSIGNED_BY_ID"])
                for d in valid_deals
                if d.get("ASSIGNED_BY_ID")
            })
            users: dict[str, str] = {}
            if user_ids:
                users = await fetch_users_batch(session, user_ids)
                await asyncio.sleep(REQUEST_DELAY)

            # Process each deal
            for deal in valid_deals:
                deal_id = str(deal["ID"])
                inn = (deal.get("UF_CRM_1751273997835") or "").strip()
                contact_id = str(deal.get("CONTACT_ID") or "")
                contact = contacts.get(contact_id)

                if not contact:
                    stats["skipped_no_contact"] += 1
                    skipped_ids.append(f"deal_{deal_id}_no_contact")
                    logger.debug("No contact for deal %s", deal_id)

                try:
                    manager_name = users.get(str(deal.get("ASSIGNED_BY_ID") or ""))
                    row = build_case_row(deal, contact, assigned_user_name=manager_name)
                    ok, err = await upsert_case(session, row, CASES_URL, CASES_KEY)
                    if ok:
                        stats["processed"] += 1
                        comment = (deal.get("COMMENTS") or "").strip()
                        if comment:
                            await insert_communication(session, inn, deal_id, comment, CASES_URL, CASES_KEY)
                    else:
                        logger.error("Upsert failed deal %s: %s", deal_id, err)
                        stats["errors"] += 1
                except Exception:
                    logger.exception("Error processing deal %s", deal_id)
                    stats["errors"] += 1

                total_done = stats["processed"] + stats["errors"]
                if total_done % 50 == 0 and total_done > 0:
                    logger.info(
                        "Прогресс: обработано %d, пропущено %d+%d, ошибок %d",
                        stats["processed"],
                        stats["skipped_no_inn"],
                        stats["skipped_no_contact"],
                        stats["errors"],
                    )

            # Check limit
            if limit is not None:
                total_handled = (
                    stats["processed"] + stats["skipped_no_inn"]
                    + stats["skipped_no_contact"] + stats["errors"]
                )
                if total_handled >= limit:
                    break

            if len(deals) < DEAL_PAGE_SIZE:
                break  # last page

            start += DEAL_PAGE_SIZE

    logger.info("=" * 60)
    logger.info("Готово. Всего из Bitrix: ~%d", total_fetched)
    logger.info("  ✅ Записано в cases:  %d", stats["processed"])
    logger.info("  ⏭  Нет ИНН:           %d", stats["skipped_no_inn"])
    logger.info("  ⚠️  Нет контакта:      %d", stats["skipped_no_contact"])
    logger.info("  ❌ Ошибок:            %d", stats["errors"])
    if skipped_ids:
        logger.info("Пропущенные: %s", ", ".join(skipped_ids[:20]))
        if len(skipped_ids) > 20:
            logger.info("  ... и ещё %d", len(skipped_ids) - 20)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Bitrix deals → electronic_case Supabase")
    parser.add_argument("--limit", type=int, default=None, help="Process only N deals (smoke test)")
    args = parser.parse_args()
    asyncio.run(run(args.limit))


if __name__ == "__main__":
    main()
