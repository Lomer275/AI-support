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

All services share a **single** `aiohttp.ClientSession` created in `bot.py` and closed on shutdown. Five services are initialized:
- `SupabaseService` → `dp["supabase"]` — session state
- `BitrixService` → `dp["bitrix"]` — CRM lookup
- `OpenAIService` → `dp["openai_svc"]` — pre-auth prompts
- `SupportSupabaseService` → `dp["support_supabase"]` — documents + chat history (separate Supabase project)
- `SupportService` → `dp["support_svc"]` — multi-agent pipeline for authorized chat

The middleware re-injects `supabase` directly into `data`.

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

`services/openai_client.py` handles pre-authorization states with 5 methods:
- `no_inn_in_text(user_text, digit_count, escalate)` — invalid INN format
- `inn_not_found(escalate)` — INN not in Bitrix
- `waiting_for_phone(user_text)` — phone verification guidance
- `phone_mismatch()` — always includes @Lobster_21
- `chat_as_alina(user_text, contact_name)` — fallback-only for authorized state

All prompts enforce first-person Russian speech as "Alina". Uses `OPENAI_MODEL` (default: `gpt-4o-mini`). Returns `str | None` — every handler has a hardcoded fallback string for `None`.

### Multi-Agent Support Pipeline (S02)

Authorized chat uses `SupportService` (`services/support.py`) instead of a single prompt. The pipeline:

```
R1 round: _r1_lawyer + _r1_sales (parallel) → _r1_manager (sequential)
R2 round: _r2_lawyer → _r2_manager → _r2_sales (sequential, uses R1 output)
Coordinator: combines full discussion → JSON {"answer": "...", "switcher": "true"|"false"}
```

- **Models:** support agents use `OPENAI_MODEL_SUPPORT` (default: `gpt-4o-mini`); coordinator uses `OPENAI_MODEL_COORDINATOR` (default: `gpt-4o`)
- **Context:** loads last 10 messages from `chat_history` + client documents from support Supabase
- **Entry point:** `support_svc.answer(chat_id, inn, question, contact_name)` — saves Q+A to `chat_history`, returns answer string
- **`switcher` field:** currently a stub (always ignored); future use for operator escalation
- **Fallback chain:** `SupportService` exception → `openai_svc.chat_as_alina()` → hardcoded `FALLBACK_ALINA`

`SupportSupabaseService` (`services/supabase_support.py`) connects to a **separate** Supabase project:
- `search_client_by_inn(inn)` — RPC to fetch judicial documents, returns formatted string
- `get_chat_history(chat_id, limit=10)` — fetches from `chat_history` table
- `save_chat_message(chat_id, role, content)` — persists messages (role: `"user"` | `"assistant"`)

### Menu Sections

The 4 main menu buttons (`menu_chat`, `menu_payment`, `menu_tasks`, `menu_docs`) are handled in `handlers/callbacks.py`. **Only `menu_chat` is functional** — payment, tasks, and documents sections are stubs showing "в разработке" messages.

### Key Utilities

- `normalize_phone()` — strips non-digits, returns last 10 digits for comparison
- `extract_inn()` — finds exactly 12-digit sequences; also returns `max_digit_sequence_length` for AI context. Note: 10-digit INN (legal entities) is not supported.
- `moscow_now()` — ISO timestamp in UTC+3 for Bitrix auth timestamp field

## Environment Variables (`.env`)

```
BOT_TOKEN=                  # Telegram bot token
SUPABASE_URL=               # Main Supabase project URL (bot_sessions table)
SUPABASE_ANON_KEY=          # Main Supabase anon key
SUPABASE_SUPPORT_URL=       # Support Supabase project URL (chat_history + documents)
SUPABASE_SUPPORT_ANON_KEY=  # Support Supabase anon key
BITRIX_WEBHOOK_BASE=        # Bitrix24 webhook base URL (no trailing slash)
OPENAI_API_KEY=             # OpenAI API key
OPENAI_MODEL=               # Pre-auth prompts model (default: gpt-4o-mini)
OPENAI_MODEL_SUPPORT=       # Support agents model (default: gpt-4o-mini)
OPENAI_MODEL_COORDINATOR=   # Coordinator agent model (default: gpt-4o)
OPENAI_PROXY=               # Optional: HTTP/SOCKS5 proxy URL for OpenAI calls
```

## Deployment Note

Before deploying, deactivate the corresponding n8n workflow on `n8n.arbitra.online` to prevent duplicate message handling. The VPS is at `89.223.125.143`.

## Docs Structure

```
docs/
├── 1. SUP-business requirements/   # BR01_ai_manager_bfl.md — product vision, JTBD, roadmap
├── 2. SUP-specifications/          # S01 (authorization), S02 (multi-agent chat)
├── 3. SUP-tasks/Done/              # Completed task files T01–T09 with acceptance criteria
├── 4. SUP-guides/                  # Internal conventions, templates, versioning guides
└── 5. SUP-unsorted/                # ТЗ.md (original TZ), questions.md (92 typical client questions), agent prompts
```

Root-level docs: `SUP-architecture.md` (system design), `SUP-HANDOFF.md` (current status + priorities), `CHANGELOG.md`, `SUP-CHANGELOG.md`.

## Planned Features (from BR01)

Implemented: authorization (S01) and multi-agent AI chat (S02). Upcoming:
- **Stage 3:** Document collection — read checklist from Bitrix, accept files → upload to Bitrix folder `UF_FOLDER_ID`
- **Stage 4:** Proactive notifications (scheduled outreach, court events from Bitrix)
- **Stage 5:** Operator escalation — `switcher=true` in coordinator output → queue with context handoff
- **Stage 6:** Tasks and payment sections (currently stubs in `menu_tasks`, `menu_payment`)
