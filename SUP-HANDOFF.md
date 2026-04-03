# SUP-HANDOFF — Текущее состояние

**Дата обновления:** 2026-03-20

---

## Текущее состояние

Telegram-бот «Алина» реализован и задеплоен на VPS. Реализован MVP: авторизация клиента по ИНН + телефон, AI-чат с Алиной (типовые вопросы), базовое меню с заглушками (Оплата, Задачи, Документы). Бот мигрирован с n8n на самостоятельный Python-сервис (Aiogram 3).

**Стек:** Python 3.11, Aiogram 3, Supabase, Bitrix24, OpenAI GPT-4o-mini, Docker, VPS.

---

## OKR

**Objective:** AI-менеджер «Алина» закрывает 95% задач МС в воронке БФЛ и снижает ФОТ отдела сопровождения.

| KR | Метрика | Цель |
|----|---------|------|
| KR1 | % задач МС, закрытых AI | 95% |
| KR2 | Расторжения по вине МС | Не выше текущего baseline |

---

## Реализовано

| Функция | Статус |
|---------|--------|
| Авторизация (ИНН + телефон) | ✅ |
| AI-чат (Алина отвечает на типовые вопросы) | ✅ |
| Меню: Чат с Алиной | ✅ |
| Меню: Оплата | 🔵 заглушка |
| Меню: Мои задачи | 🔵 заглушка |
| Меню: Документы | 🔵 заглушка |

---

## Следующие шаги

### Активный спринт: S03 — Улучшение качества ответов ИИ

| ID | Задача | Статус |
|----|--------|--------|
| [T10](docs/3.%20SUP-tasks/Done/S03_ai_chat_quality_done/T10_s03_company_facts_done.md) | COMPANY_FACTS — база знаний компании, анти-галлюцинация | ✅ 2026-03-27 |
| [T11](docs/3.%20SUP-tasks/Done/S03_ai_chat_quality_done/T11_s03_bitrix_deal_profile_done.md) | get_deal_profile() + client_context | ✅ 2026-03-27 |
| [T12](docs/3.%20SUP-tasks/Done/S03_ai_chat_quality_done/T12_s03_history_and_escalation_message_done.md) | История чата в агентах, улучшение эскалации | ✅ 2026-03-27 |
| [T13](docs/3.%20SUP-tasks/Done/S03_ai_chat_quality_done/T13_s03_evaluator_quality_run_done.md) | EvaluatorService + quality_run.py | ✅ 2026-03-27 |
| [T14](docs/3.%20SUP-tasks/Done/S03_ai_chat_quality_done/T14_s03_imconnector_service_done.md) | ImConnectorService — Bitrix Open Lines | ✅ 2026-03-27 |
| [T15](docs/3.%20SUP-tasks/Done/S03_ai_chat_quality_done/T15_s03_webhook_server_done.md) | Webhook-эндпоинт для ответов оператора | ✅ 2026-03-27 |
| [T16](docs/3.%20SUP-tasks/Done/S03_ai_chat_quality_done/T16_s03_escalation_state_machine_done.md) | Стейт-машина эскалации | ✅ 2026-03-27 |

---

### Приоритет 0: S01 — Завершение авторизации

T01–T05 независимы, T06 зависит от всех.

| ID | Задача | Статус |
|----|--------|--------|
| [T01](docs/3.%20SUP-tasks/Done/S01_authorization_done/T01_s01_start_already_authorized_done.md) | /start для уже авторизованного клиента | ✅ 2026-03-20 |
| [T02](docs/3.%20SUP-tasks/Done/S01_authorization_done/T02_s01_inn_error_counter_done.md) | Счётчик ошибок ИНН + двухэтапная эскалация | ✅ 2026-03-20 |
| [T03](docs/3.%20SUP-tasks/Done/S01_authorization_done/T03_s01_phone_mismatch_escalation_done.md) | Эскалация при несовпадении телефона | ✅ 2026-03-20 |
| [T04](docs/3.%20SUP-tasks/Done/S01_authorization_done/T04_s01_bitrix_unavailable_done.md) | Обработка недоступности Bitrix | ✅ 2026-03-20 |
| [T05](docs/3.%20SUP-tasks/Done/S01_authorization_done/T05_s01_auth_consultative_mode_done.md) | Консультативный режим во время авторизации | ✅ 2026-03-20 |
| [T06](docs/3.%20SUP-tasks/Done/S01_authorization_done/T06_s01_auth_autotests_done.md) | Автотесты авторизации через Telegram MCP | ✅ 2026-03-20 |

### Активный спринт: S04 — Электронное дело клиента

| ID | Задача | Статус |
|----|--------|--------|
| [T17](docs/3.%20SUP-tasks/Done/S04_electronic_case_done/T17_s04_create_database_done.md) | Создать Supabase-проект `electronic_case` + схему БД (6 таблиц) | ✅ 2026-03-30 |
| [T18](docs/3.%20SUP-tasks/Done/S04_electronic_case_done/T18_s04_initial_sync_done.md) | Начальная синхронизация ~1000 сделок из Bitrix | ✅ 2026-03-30 |
| [T19](docs/3.%20SUP-tasks/Done/S04_electronic_case_done/T19_s04_webhooks_sync_done.md) | Webhook-синхронизация `onCrmDealUpdate` → `electronic_case` | ✅ 2026-03-31 |
| [T20](docs/3.%20SUP-tasks/Done/S04_electronic_case_done/T20_s04_document_validator_done.md) | `document_validator.py`: фильтр → GPT Vision → чеклист | ✅ 2026-03-31 |
| [T21](docs/3.%20SUP-tasks/T21_s04_document_rejection_notification.md) | Уведомление клиенту при отклонении документа | ⏸ отложено |
| [T22](docs/3.%20SUP-tasks/Done/S04_electronic_case_done/T22_s04_electronic_case_service_done.md) | `electronic_case.py`: `get_case_context()`, `get_checklist_status()` | ✅ 2026-03-31 |
| [T23](docs/3.%20SUP-tasks/Done/S04_electronic_case_done/T23_s04_agents_integration_done.md) | Инжект контекста в R1/R2/Coordinator; заменить `get_deal_profile()` | ✅ 2026-04-01 |

---

### Приоритет 1: Сбор документов

| ID | Задача | Статус |
|----|--------|--------|
| — | Профилирующий опрос клиента (брак, дети, имущество, ИП) | pending |
| — | Чтение чек-листа задачи «Сбор документов» из Bitrix | pending |
| — | Адаптация чек-листа под профиль клиента | pending |
| — | Приём файлов в Telegram → загрузка в папку Bitrix (UF_FOLDER_ID) | pending |

### Приоритет 2: Проактивные уведомления

| ID | Задача | Статус |
|----|--------|--------|
| — | Плановые контакты по расписанию (исходящие сообщения от бота) | pending |
| — | Информирование о событиях суда из данных Bitrix | pending |

### Активный спринт: S05 — Эскалация и качество ответов

Источник: анализ реального диалога (dialog2, клиент Дмитрий Валерьевич).
Параллелизм: T24, T26, T27, T29, T30 независимы. T25 после T24. T28 после T26. T31 после всех.

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| [T24](docs/3.%20SUP-tasks/S05_escalation_and_quality/T24_s05_bidirectional_chat.md) | Диагностика и фикс двусторонней переписки Bitrix ↔ Telegram | — | ✅ 2026-04-03 |
| [T25](docs/3.%20SUP-tasks/S05_escalation_and_quality/T25_s05_transfer_to_responsible.md) | Перевод на ответственного сделки (`chat.transfer` + Bitrix chat ID) | T24 | 🔵 planned |
| [T26](docs/3.%20SUP-tasks/S05_escalation_and_quality/T26_s05_au_in_context.md) | АУ в `cases_mapper.py` и `get_case_context()` | — | ✅ 2026-04-03 |
| [T27](docs/3.%20SUP-tasks/S05_escalation_and_quality/T27_s05_smart_escalation.md) | Умная эскалация — промпт Coordinator (первый сигнал) | — | 🔵 planned |
| [T28](docs/3.%20SUP-tasks/S05_escalation_and_quality/T28_s05_no_data_response.md) | Ответ при отсутствии данных — промпт R1/R2 | T26 | 🔵 planned |
| [T29](docs/3.%20SUP-tasks/S05_escalation_and_quality/T29_s05_no_repetition.md) | Устранение повторений — last_3_answers + промпт R1 | — | 🔵 planned |
| [T30](docs/3.%20SUP-tasks/S05_escalation_and_quality/T30_s05_parallel_pipeline_fix.md) | Фикс параллельных pipeline (per-chat asyncio.Lock) | — | ✅ 2026-04-03 |
| [T31](docs/3.%20SUP-tasks/S05_escalation_and_quality/T31_s05_regression.md) | Регрессия — quality_run.py + dialog2-сценарий | T24–T30 | 🔵 planned |

---

### Приоритет 3: Эскалация на оператора

| ID | Задача | Статус |
|----|--------|--------|
| — | Очередь операторов | pending |
| — | Передача контекста диалога оператору | pending |
| — | Возврат управления боту после закрытия вопроса | pending |

### Приоритет 4: Трекинг задач и оплата

| ID | Задача | Статус |
|----|--------|--------|
| — | Задачи из Bitrix в боте (раздел «Мои задачи») | pending |
| — | Оплата по реквизитам и СБП (раздел «Оплата») | pending |

---

## Связанные документы

- [CLAUDE.md](CLAUDE.md) — инструкции для разработки
- [SUP-architecture.md](SUP-architecture.md) — архитектура
- [SUP-CHANGELOG.md](SUP-CHANGELOG.md) — история изменений
- [BR01_ai_manager_bfl.md](docs/1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md) — бизнес-требования
