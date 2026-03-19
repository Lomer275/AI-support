# SUP-CHANGELOG

## [Не выпущено]

### Added
- 2026-03-20 — T01: `/start` для авторизованного клиента — не сбрасывает сессию, показывает меню
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
