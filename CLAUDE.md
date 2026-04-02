# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

"Alina" — AI-powered Telegram support bot for ArbitrA (Express-Bankrot). Auth via INN+phone → Bitrix24 CRM → multi-agent GPT chat with operator escalation.

## Dev Commands

```bash
python bot.py                                          # local run
python scripts/quality_run.py --output results.json   # quality eval (anon)
python scripts/quality_run.py --inn 123456789012 --output r.json  # with real client
python scripts/quality_run.py --limit 5 --output r.json           # smoke test
python scripts/sync_bitrix_to_cases.py                # full Bitrix→Supabase sync (~1000 deals)
python scripts/sync_bitrix_to_cases.py --limit 5      # smoke test sync
docker compose up -d --build && docker compose logs -f bot
```

## Architecture

### State Machine
Session state in Supabase `bot_sessions` (keyed by `chat_id`), not Aiogram FSM. States: `"waiting_inn"` → `"waiting_phone"` → `"authorized"`. `/start` in non-auth state resets session + `error_count`; in auth state shows menu without reset.

### Services
Single `aiohttp.ClientSession` shared by all services (created in `bot.py`):
`SupabaseService`, `BitrixService`, `OpenAIService`, `SupportSupabaseService`, `SupportService`, `EvaluatorService`, `ImConnectorService`, `ElectronicCaseService` — injected into `dp` (workflow_data), accessed via middleware as `data["service_name"]`.

`DocumentValidator` (S04/T20): three-level pipeline — format filter → GPT-4o-mini Vision (classify doc type + readability) → update `checklist_completion` in `electronic_case` Supabase. Triggered from `webhook_server.py` on new files in a Bitrix deal folder. Uses `CHECKLIST_ITEMS` (18 doc types, fixed denominator).

`ElectronicCaseService` (S04/T22–T23): reads `electronic_case` Supabase project, returns formatted context strings for AI agents. Replaces `BitrixService.get_deal_profile()` in the chat pipeline.

`cases_mapper.py`: shared mapping Bitrix deal dict → `electronic_case` Supabase rows. Used by both `sync_bitrix_to_cases.py` (bulk) and `webhook_server.py` (real-time).

### Handler Registration Order (important)
`handlers/__init__.py`: start_router → contact_router → callbacks_router → text_router. Text router must be last or it shadows other handlers.

### Bitrix24 Integration
`services/bitrix.py` uses `/batch` API. Hardcoded field IDs:
- `UF_CRM_1751273997835` — INN
- `UF_CRM_1768296374` — auth status
- `UF_CRM_1768547250879` — auth timestamp

Search: `CATEGORY_ID=4`, `STAGE_SEMANTIC_ID=P`, order by `DATE_CREATE DESC`.

### Multi-Agent Pipeline (S02)
```
R1: _r1_lawyer + _r1_sales (parallel) → _r1_manager
R2: _r2_lawyer → _r2_manager → _r2_sales
Coordinator → JSON {"answer": "...", "switcher": "true"|"false"}
```
- Support agents: `OPENAI_MODEL_SUPPORT` (default: `gpt-4o-mini`); Coordinator: `OPENAI_MODEL_COORDINATOR` (default: `gpt-4o`)
- Context: last 10 messages from `chat_history` + client docs from support Supabase
- `switcher=true` → `escalation_state="pending"` → ImConnector chat created
- Fallback: `SupportService` exception → `chat_as_alina()` → hardcoded `FALLBACK_ALINA`

### Escalation State Machine
`escalation_state`: null → `"pending"` → `"in_operator_chat"` → `"closed"`. Watchdog (every 5 min) auto-returns AI after 60 min no operator reply. Don't update `escalation_state` outside this flow.

Webhook server (`webhook_server.py`, port 8080):
- `POST /webhook/bitrix/` — `ONIMCONNECTORMESSAGEADD` (operator message → Telegram), `IMOPENLINES.SESSION.FINISH` (chat closed → reset escalation). Parses BB-code, downloads file attachments to `documents/`.
- `POST /bitrix/crm-deal-update` — `ONCRMDEALUPDATE`/`ONCRMDEALADD` → upsert in `electronic_case` Supabase (real-time deal sync) + trigger `DocumentValidator` on new files.

### INN Error Counter
`error_count` in `bot_sessions`: incremented on invalid format or INN not found. `error_count=1` → standard response; `≥2` → mandatory @Lobster_21 mention. Bitrix exception does NOT increment.

### Key Utilities
- `normalize_phone()` — last 10 digits (strips +7/8/country code)
- `extract_inn()` — exactly 12-digit sequences only; returns `max_digit_sequence_length` for AI context. 10-digit INN (legal entities) not supported.
- `moscow_now()` — UTC+3 ISO timestamp

## Environment Variables

Required: `BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SUPPORT_URL`, `SUPABASE_SUPPORT_ANON_KEY`, `SUPABASE_CASES_URL`, `SUPABASE_CASES_ANON_KEY`, `BITRIX_WEBHOOK_BASE`, `BITRIX_URL`, `BITRIX_OAUTH_CLIENT_ID`, `BITRIX_OAUTH_CLIENT_SECRET`, `BITRIX_OAUTH_ACCESS_TOKEN`, `BITRIX_OAUTH_REFRESH_TOKEN`, `OPENAI_API_KEY`

Optional (with defaults): `OPENAI_MODEL` (gpt-4o-mini), `OPENAI_MODEL_SUPPORT` (gpt-4o-mini), `OPENAI_MODEL_COORDINATOR` (gpt-4o), `OPENAI_MODEL_VALIDATOR` (gpt-4o-mini), `OPENAI_PROXY`, `BITRIX_OPENLINE_ID` (56), `BITRIX_CONNECTOR_ID` (tg_alina_support), `WEBHOOK_PORT` (8080)

## Critical Notes

- **HTML Parse Mode:** `ParseMode.HTML` — use `<b>/<i>/<code>` not Markdown. Escape `<`, `>`, `&` in dynamic content.
- **Transport:** Long-polling only. Port 8080 is for Bitrix webhooks, NOT Telegram.
- **Fallbacks:** Every external call (OpenAI/Bitrix/Supabase) has hardcoded fallback string — bot never crashes.
- **Deduplication:** Supabase RPC `get_or_create_session` returns `is_duplicate: true` for replayed `update_id` — middleware drops them.
- **Three Supabase projects:** main (`bot_sessions`), support (`chat_history`, judicial docs), electronic_case (`cases`, `communications`, checklist) — each has its own URL/key pair.
- **Bitrix batch:** `get_deal()` and `get_deal_profile()` use `/batch` — cache profile during session.

## Deployment

Before deploy: deactivate n8n workflow on `n8n.arbitra.online` to prevent duplicate handling. VPS: `89.223.125.143`.

## Docs

- Specs: `docs/2. SUP-specifications/` (S01–S04)
- Active tasks: `docs/3. SUP-tasks/` (T17–T23 = S04); done tasks in `Done/`
- Architecture: `SUP-architecture.md`; status: `SUP-HANDOFF.md`

## Implementation Status

- **Done:** S01 (auth), S02 (multi-agent chat), S03 (quality eval + operator escalation)
- **Next:** S04 — Electronic Case (T17–T23, `docs/2. SUP-specifications/S04_electronic_case.md`)
- **Planned:** S05 (proactive notifications), S06 (menu: tasks + payments)
