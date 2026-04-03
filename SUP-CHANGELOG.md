# SUP-CHANGELOG

## [Не выпущено]

### Added
- S05/T29: `services/support.py` — `answer()` извлекает последние 3 ответа AI (`last_answers`) и формирует `already_said_block`; промпт `_r1_lawyer()` получает параметр `already_said` с запретом дословного повторения; промпт `_coordinator()` — убраны фразы «вам ничего делать не нужно» и «не предпринимайте никаких действий» из КАТАЛОГА ДЕЙСТВИЙ; добавлена САМОПРОВЕРКА на шаблоны; `_build_client_card()` — парсинг «Менеджер сопровождения (МС):» для нового формата electronic_case (принято 2026-04-03)
- S05/T28: `services/support.py` — промпт `_r1_lawyer()`: явное ПРАВИЛО ПРИ ОТСУТСТВИИ ДАННЫХ — запрет шаблонных фраз («наша команда контролирует», «мы занимаемся»), обязательное «Этой информации у меня нет» с предложением эскалации; промпт `_r1_manager()`: аналогичное правило + заменена фраза «мы контролируем сроки» на «если в контексте есть конкретные даты — опирайся на них»; промпт `_coordinator()`: ответ при отсутствии данных изменён с вопроса «Хотите, я переключу?» на утверждение «переключаю вас на вашего менеджера» (принято 2026-04-03)
- S05/T27: `services/support.py` — промпт `_coordinator()` расширен: добавлен тип `escalation_type="irritation"` с явным списком триггеров (риторические вопросы о качестве, прямое недовольство, повторный вопрос без ответа); ответ при раздражении — короткая человечная фраза без данных о деле; антитриггеры для обычных вопросов добавлены (принято 2026-04-03)
- S05/T25: `services/imconnector.py` — методы `get_or_find_bitrix_chat_id()` и `transfer_to_responsible()`; `services/cases_mapper.py` — `ASSIGNED_BY_ID` в `DEAL_SELECT` и `assigned_user_id` в `build_case_row()`; `services/electronic_case.py` — `get_assigned_user_id()`; `handlers/text.py` — перевод чата на ответственного менеджера сразу после эскалации; требуется `ALTER TABLE cases ADD COLUMN IF NOT EXISTS assigned_user_id text` в Supabase (принято 2026-04-03)
- S05/T30: `handlers/text.py` — per-chat `asyncio.Lock` в `_handle_authorized()` устраняет тройной ответ AI при быстрой отправке нескольких сообщений; второй и третий вызовы ждут в очереди без блокировки event loop (принято 2026-04-03)
- S05/T26: `arbitration_manager` (ФИО арбитражного управляющего) верифицирован — поле присутствует в `cases_mapper.py` (UF_CRM_1607524042544) и в `get_case_context()` через `tracked()`; реализовано в S04/T22-T23 (принято 2026-04-03)
- S05/T24: `services/imconnector.py` — уникальный `msg_id = f"{chat_id}_{timestamp_ms}"` вместо хардкода `"0"`; `asyncio.Lock` для `_refresh_token` предотвращает двойной refresh; таймаут 15s на все HTTP вызовы. `webhook_server.py` — `html.escape()` для текста оператора; логирование raw payload (DEBUG); fallback chat_id через CONNECTOR_MID (принято 2026-04-03)
- S04/T23: `handlers/text.py` — `ElectronicCaseService` инжектирован в `_handle_authorized()`; `get_case_context(inn)` заменяет `get_deal_profile()` как основной источник контекста; fallback на Bitrix при `None`; `_build_client_card()` в `support.py` обновлён для парсинга формата `[ЭЛЕКТРОННОЕ ДЕЛО КЛИЕНТА]`; логи `source=electronic_case` / `source=bitrix_fallback` (принято 2026-04-01)
- S04/T22: `services/electronic_case.py` — `ElectronicCaseService` с `get_case_context()` и `get_checklist_status()`; форматированный контекст клиента из Supabase `electronic_case`; декодирование стадий через `STAGE_LABELS`; ✅/❌/⬜ чеклист документов; инициализирован в `bot.py`, доступен через `dp["electronic_case_svc"]` (принято 2026-03-31)
- S04/T20: `services/document_validator.py` — GPT-4o-mini Vision классификация документов из папки `Неразобранное`; 18 типов чеклиста; `checklist_completion` пересчёт; поддержка PDF (PyMuPDF) и изображений (Pillow) (принято 2026-03-31)
- S04/T19: webhook `ONCRMDEALUPDATE` → `/bitrix/crm-deal-update` → upsert в `electronic_case`; `services/cases_mapper.py` вынесен как общий модуль; вебхук зарегистрирован в Bitrix и протестирован (принято 2026-03-31)
- S04/T18: `scripts/sync_bitrix_to_cases.py` — разовая выгрузка 996/998 активных сделок из Bitrix → Supabase `electronic_case`; 992 строки в `cases`, enum-декодирование city/court_region, upsert по `inn`, 2 сделки пропущено (нет ИНН) (принято 2026-03-30)
- S04/T17: Supabase-проект `electronic_case` — 6 таблиц (`cases`, `property`, `debts`, `payments`, `documents`, `communications`), 6 индексов, переменные `SUPABASE_CASES_URL` и `SUPABASE_CASES_ANON_KEY` добавлены в `.env` (принято 2026-03-30)
- S03/T16: стейт-машина эскалации — маршрутизация сообщений клиента оператору при `escalated=true`, watchdog каждые 5 минут возвращает ИИ через 1 час без ответа оператора, `operator_last_reply_at` сбрасывается при SESSION.FINISH и watchdog-сбросе (принято 2026-03-27)
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
