# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"Alina" — an AI-powered customer support Telegram bot for ArbitrA (Express-Bankrot legal/bankruptcy service). Authenticates clients via INN (Russian tax ID) + phone number, links them to Bitrix24 CRM deals, and provides GPT-powered chat support.

## Running the Bot

```bash
# Local development
pip install -r requirements.txt
python bot.py

# Docker (production)
docker compose up -d --build
docker compose logs -f bot
docker compose down
```

No test suite exists. Manual testing follows the state machine flow described in `docs/5. SUP-unsorted/ТЗ.md`.

## Architecture

### State Machine

Session state is persisted in **Supabase** table `bot_sessions` (keyed by `chat_id`), not Aiogram FSM. States are defined in `states.py` as string constants (`"waiting_inn"`, `"waiting_phone"`, `"authorized"`):

```
/start (not AUTHORIZED) → WAITING_INN → WAITING_PHONE → AUTHORIZED
                                  ↑ (INN not found)     ↑ (phone mismatch)
/start (AUTHORIZED) → shows menu, no reset
```

`/start` in non-authorized states resets the session to `waiting_inn`, clearing all CRM fields and `error_count`. If already `AUTHORIZED`, `/start` shows the menu without resetting.

### Request Flow

1. Telegram update → `middlewares/session.py` calls Supabase RPC `get_or_create_session`, deduplicates by `update_id` (returns `is_duplicate: true` for replays → middleware drops them)
2. Middleware injects `data["session"]` and `data["supabase"]` into handler context
3. Handler routing by update type and `session["state"]`
4. External calls: Supabase (state storage), Bitrix24 (CRM lookup), OpenAI (response generation)

### Service Wiring

All three services (`SupabaseService`, `BitrixService`, `OpenAIService`) share a **single** `aiohttp.ClientSession` created in `bot.py` and closed on shutdown. They are injected into handlers via `dp["supabase"]`, `dp["bitrix"]`, `dp["openai_svc"]`. The middleware also re-injects `supabase` directly into `data`.

### Contact Handler (phone verification)

`handlers/contact.py` handles the `F.contact` update (Telegram share-phone button). Only acts in `WAITING_PHONE` state:
1. Normalizes both phones to last 10 digits
2. **Match:** calls `bitrix.update_deal_authorized()`, updates session to `AUTHORIZED`, sends 2-message welcome (welcome text + menu)
3. **Mismatch:** calls `openai_svc.phone_mismatch()` — response always includes @Lobster_21 escalation contact

### INN Error Counter

`error_count` is stored in `bot_sessions` and incremented on every failed attempt in `WAITING_INN` (invalid INN format or INN not found in Bitrix — both count). Escalation tiers:
- `error_count = 1`: standard AI response
- `error_count >= 2`: AI response + mandatory mention of @Lobster_21

`error_count` resets to 0 on `/start`. Bitrix unavailability (exception) does **not** increment the counter.

### Handler Registration Order (important)

Handlers are registered in `handlers/__init__.py` in this order:

1. `start_router` — `/start` command
2. `contact_router` — `F.contact` (phone share button)
3. `callbacks_router` — inline button callbacks (`back_menu`, `menu_*`)
4. `text_router` — `F.text` catch-all, routes by state

The text router must remain last to avoid shadowing more specific handlers.

### Bitrix24 Integration

`services/bitrix.py` uses a **batch API call** (`/batch`) to fetch deal → contacts → contact detail in one request. Hardcoded custom field IDs:

- `UF_CRM_1751273997835` — INN field on deal
- `UF_CRM_1768296374` — auth status field
- `UF_CRM_1768547250879` — auth timestamp field

Search filters: `CATEGORY_ID=4`, `STAGE_SEMANTIC_ID=P` (active/in-progress deals only), ordered by `DATE_CREATE DESC`.

### OpenAI Integration

`services/openai_client.py` contains 5 prompts for different bot states:
- `no_inn_in_text` — INN validation errors (includes digit count context)
- `inn_not_found` — INN not in Bitrix
- `waiting_for_phone` — phone verification guidance
- `phone_mismatch` — phone mismatch
- `chat_as_alina` — authorized chat (main "Alina" persona)

All prompts enforce first-person Russian speech as "Alina". The model is configurable via `OPENAI_MODEL` env var (default: `gpt-4o-mini`). Every handler has a hardcoded fallback string used when the OpenAI call returns `None`.

### Menu Sections

The 4 main menu buttons (`menu_chat`, `menu_payment`, `menu_tasks`, `menu_docs`) are handled in `handlers/callbacks.py`. **Only `menu_chat` is functional** — payment, tasks, and documents sections are stubs showing "в разработке" messages.

### Key Utilities

- `normalize_phone()` — strips non-digits, returns last 10 digits for comparison
- `extract_inn()` — finds exactly 12-digit sequences; also returns `max_digit_sequence_length` for AI context. Note: 10-digit INN (legal entities) is not supported.
- `moscow_now()` — ISO timestamp in UTC+3 for Bitrix auth timestamp field

## Environment Variables (`.env`)

```
BOT_TOKEN=           # Telegram bot token
SUPABASE_URL=        # Supabase project URL
SUPABASE_ANON_KEY=   # Supabase anon key
BITRIX_WEBHOOK_BASE= # Bitrix24 webhook base URL (no trailing slash)
OPENAI_API_KEY=      # OpenAI API key
OPENAI_MODEL=        # e.g. gpt-4o-mini
OPENAI_PROXY=        # Optional: HTTP/SOCKS5 proxy URL for OpenAI calls
```

## Deployment Note

Before deploying, deactivate the corresponding n8n workflow on `n8n.arbitra.online` to prevent duplicate message handling. The VPS is at `89.223.125.143`.

## Docs Structure

```
docs/
├── 1. SUP-business requirements/   # BR01_ai_manager_bfl.md — product vision, JTBD, roadmap
├── 2. SUP-specifications/          # Technical specs (S01 usability test cycle)
├── 3. SUP-tasks/                   # Task files (T01, T02…) with acceptance criteria
├── 4. SUP-guides/                  # Internal conventions, templates, versioning guides
└── 5. SUP-unsorted/                # ТЗ.md (original technical spec), questions.md (92 typical client questions), PDFs
```

## Planned Features (from BR01)

Current MVP covers: authorization (INN + phone) and AI chat. Upcoming stages:
- **Stage 2:** Client profiling survey + document collection (read checklist from Bitrix, accept files → upload to Bitrix folder `UF_FOLDER_ID`)
- **Stage 3:** Proactive notifications (scheduled outreach, court events from Bitrix)
- **Stage 4:** Operator escalation (conflict/attrition signals → queue with context handoff)
- **Stage 5:** Tasks and payment sections (currently stubs)
