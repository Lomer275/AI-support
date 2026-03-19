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

No test suite exists. Manual testing follows the state machine flow described in `docs/ТЗ.md`.

## Architecture

### State Machine

Session state is persisted in **Supabase** (not Aiogram FSM). States are defined in `states.py`:

```
/start → WAITING_INN → WAITING_PHONE → AUTHORIZED
                 ↑ (INN not found)     ↑ (phone mismatch)
```

`/start` always resets session state regardless of current state.

### Request Flow

1. Telegram update → `middlewares/session.py` loads/creates Supabase session, deduplicates by `update_id`
2. Handler routing by update type and current session state
3. External calls: Supabase (state storage), Bitrix24 (CRM lookup), OpenAI (response generation)

### Key Files

| File | Purpose |
|------|---------|
| `bot.py` | Entry point: initializes Bot, Dispatcher, services; registers middleware + handlers |
| `config.py` | `Settings` dataclass loaded from `.env` |
| `handlers/text.py` | Core state-based routing logic for text messages |
| `handlers/callbacks.py` | Inline button menu navigation |
| `handlers/contact.py` | Phone verification against Bitrix24 |
| `services/supabase.py` | Session CRUD via RPC `get_or_create_session` + PATCH |
| `services/bitrix.py` | Batch INN search, deal update with auth status |
| `services/openai_client.py` | 5 distinct prompts for the "Alina" persona |
| `keyboards.py` | Phone share button, 4-button main menu, back button |
| `utils.py` | `normalize_phone()`, `extract_inn()`, `moscow_now()` |

### OpenAI Integration

`services/openai_client.py` contains 5 prompts for different bot states:
- INN validation errors
- INN not found in Bitrix
- Phone verification guidance
- Phone mismatch
- Authorized chat (main "Alina" persona)

All prompts enforce first-person Russian speech as "Alina". The model is configurable via `OPENAI_MODEL` env var (default: `gpt-4o-mini`).

## Environment Variables (`.env`)

```
BOT_TOKEN=           # Telegram bot token
SUPABASE_URL=        # Supabase project URL
SUPABASE_ANON_KEY=   # Supabase anon key
BITRIX_WEBHOOK_BASE= # Bitrix24 webhook base URL
OPENAI_API_KEY=      # OpenAI API key
OPENAI_MODEL=        # e.g. gpt-4o-mini
```

## Deployment Note

Before deploying, deactivate the corresponding n8n workflow on `n8n.arbitra.online` to prevent duplicate message handling. The VPS is at `89.223.125.143`.
