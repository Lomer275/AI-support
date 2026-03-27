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
| [T11](docs/3.%20SUP-tasks/T11_s03_bitrix_deal_profile.md) | get_deal_profile() + client_context | 🟡 To Do |
| [T12](docs/3.%20SUP-tasks/T12_s03_history_and_escalation_message.md) | История чата в агентах, улучшение эскалации | 🟡 To Do |
| [T13](docs/3.%20SUP-tasks/T13_s03_evaluator_quality_run.md) | EvaluatorService + quality_run.py | 🔵 Planned |
| [T14](docs/3.%20SUP-tasks/T14_s03_imconnector_service.md) | ImConnectorService — Bitrix Open Lines | 🔵 Planned |
| [T15](docs/3.%20SUP-tasks/T15_s03_webhook_server.md) | Webhook-эндпоинт для ответов оператора | 🔵 Planned |
| [T16](docs/3.%20SUP-tasks/T16_s03_escalation_state_machine.md) | Стейт-машина эскалации | 🔵 Planned |

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
