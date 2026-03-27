# SUP-CHANGELOG

## [Не выпущено]

### Added
- S03/T11: `get_deal_profile(deal_id)` в `BitrixService` переключён на чтение чеклиста из задачи «Собрать ЛИЧНЫЕ документы клиента» через 2 batch-запроса (deal+tasks.task.list → user+tasks.task.get с CHECKLIST); формат вывода: стадия, менеджер, чеклист со статусами (принято 2026-03-27)
- S03/T15: `webhook_server.py` — aiohttp-сервер на порту 8080 для приёма ответов оператора из Bitrix Open Lines; очистка BB-кодов; события `ONIMCONNECTORMESSAGEADD` и `IMOPENLINES.SESSION.FINISH`; доставка подтверждена через Telegram MCP за 0.18s (принято 2026-03-27)
- S03/T14: `ImConnectorService` — отправка сообщений и истории диалога в Bitrix Open Lines через OAuth (`imconnector.send.messages`); автообновление access_token через refresh_token при истечении; `connector_id=tg_alina_support`, `openline_id=56` (принято 2026-03-27)
- S03/T13: `EvaluatorService` + `scripts/quality_run.py` — автоматический прогон N вопросов через SupportService, оценка ответов по 4 критериям (specificity, accuracy, tone, completeness) с сохранением в JSON (принято 2026-03-27)
- S03/T12: история последних 10 сообщений передана в `_r1_lawyer` и `_r1_manager`; координатор возвращает `escalation_type` (conflict/request/none) с дифференцированными человечными ответами вместо нейтральной заглушки (принято 2026-03-27)
- S03/T10: `COMPANY_FACTS` — база знаний компании инжектирована во все 7 агентов и координатора; добавлены адреса и телефоны офисов (Барнаул, Воронеж, Краснодар), сайт, правило анти-галлюцинации (принято 2026-03-27)
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
