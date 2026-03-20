# SUP-CHANGELOG

## [Не выпущено]

### Added
- 2026-03-20 — T06: автотесты авторизации через Telegram MCP + Supabase MCP — 6 авто-тестов (T1-T4, T7-T8), 2 ручных (phone contact); runbook в `docs/5. SUP-unsorted/T06_auth_tests_runbook.md`
- 2026-03-20 — прокси для Docker: `OPENAI_PROXY` в `.env` используется и для Telegram (aiogram AiohttpSession), и для OpenAI — бот работает без VPN
- 2026-03-20 — T01: `/start` для авторизованного клиента — не сбрасывает сессию, показывает меню
- 2026-03-20 — T02: счётчик ошибок ИНН — после 2-й попытки Алина предлагает @Lobster_21
- 2026-03-20 — T03: несовпадение телефона — Алина всегда упоминает @Lobster_21
- 2026-03-20 — T04: Bitrix недоступен — отдельное сообщение, error_count не растёт
- 2026-03-20 — T05: консультативный режим — отвечает на вопросы по авторизации, дефлектирует остальное
- Папка `docs/1. SUP-business requirements/` и документ `BR01_ai_manager_bfl.md` — бизнес-требования на замену МС AI-менеджером в воронке БФЛ (проблема, JTBD, флоу, метрики, формализованное описание, этапы раскатки)
- `docs/5. SUP-unsorted/questions.md` — 92 типовых вопроса клиентов по банкротству (источник для AI-промптов Алины)

### Changed
- `CLAUDE.md` — расширен: добавлены handler registration order, service wiring (shared aiohttp session), Bitrix custom field IDs, Supabase table name, extract_inn limitation, menu section stubs
- `SUP-architecture.md` — полностью переписан под проект «Алина» (убран контент предыдущего проекта)
- `SUP-HANDOFF.md` — полностью переписан: текущее состояние, OKR, roadmap по приоритетам
- `SUP-CHANGELOG.md` — переписан под проект «Алина»

---

## [0.1.0] — 2026-03-09

### Added
- Скелет проекта: `bot.py`, `config.py`, `states.py`, `keyboards.py`, `utils.py`
- Сервисы: `supabase.py`, `bitrix.py`, `openai_client.py`
- Middleware сессий с дедупликацией по `update_id`
- Handlers: `/start`, авторизация по ИНН + телефон, AI-чат (Алина), меню
- Docker Compose деплой на VPS (89.223.125.143)
- Документация: `CLAUDE.md`, `SUP-architecture.md`, `SUP-HANDOFF.md`
- Бизнес-требования: `BR01_ai_manager_bfl.md`
