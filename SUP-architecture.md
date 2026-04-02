# SUP-architecture

**Статус:** актуально
**Дата:** 2026-03-31
**Версия:** 0.4

---

## System Overview

Telegram-бот «Алина» — AI-менеджер сопровождения клиентов по банкротству физических лиц (БФЛ). Заменяет менеджера сопровождения (МС) на всём протяжении воронки БФЛ: авторизация → сбор документов → ожидание суда → завершение процедуры.

Целевое покрытие: 95% задач МС.

---

## Components

### Telegram Bot (`bot.py`)
- **Технология:** Python 3.11, Aiogram 3.x, Long Polling
- **Точка входа:** `bot.py`
- **Структура:** handlers → middlewares → services → keyboards → states
- **Ответственность:** Основной канал коммуникации с клиентом

### Handlers (`handlers/`)
| Файл | Ответственность |
|------|----------------|
| `start.py` | `/start` — сброс сессии, приветствие |
| `text.py` | Роутинг текстовых сообщений по состоянию сессии |
| `contact.py` | Верификация телефона через Telegram contact |
| `callbacks.py` | Inline-кнопки главного меню |

> Порядок регистрации: start_router → contact_router → callbacks_router → text_router. Text router должен быть последним.

### Session Middleware (`middlewares/session.py`)
- Загружает/создаёт сессию через Supabase RPC на каждый update
- Дедуплицирует обновления по `update_id`
- Инжектирует `session` в handler context

### Services (`services/`)
| Файл | Ответственность |
|------|----------------|
| `supabase.py` | Сессии: RPC `get_or_create_session` + PATCH `bot_sessions` |
| `bitrix.py` | Batch-поиск по ИНН, обновление сделки, `get_deal_profile()` через чеклист задачи |
| `openai_client.py` | Промпты для состояний авторизации (персона «Алина») |
| `support_service.py` | Multi-agent pipeline: R1 → R2 → Coordinator |
| `support_supabase.py` | `chat_history`, судебные документы (второй Supabase) |
| `evaluator_service.py` | Автооценка ответов по 4 критериям (quality_run) |
| `im_connector_service.py` | Отправка сообщений/истории в Bitrix Open Lines; OAuth auto-refresh |
| `document_validator.py` | GPT-4o-mini Vision → классификация → 18 типов чеклиста → `checklist_completion` |
| `electronic_case.py` | `get_case_context()`, `get_checklist_status()` — контекст дела для агентов |
| `cases_mapper.py` | Маппинг полей Bitrix-сделки → строка `electronic_case` |

Все сервисы получают единый `aiohttp.ClientSession` (создаётся в `bot.py`) и инжектируются через `dp` (workflow_data).

---

## State Machine

Состояние хранится в Supabase (`bot_sessions.state`), не в Aiogram FSM.

```
/start ──────────────► waiting_inn
                            │
                      ИНН найден в Bitrix
                            │
                            ▼
                      waiting_phone
                            │
                      телефон совпал
                            │
                            ▼
                       authorized ◄──── /start (только сброс в non-auth)
```

### Escalation State Machine (`escalation_state`)
```
null → "pending" → "in_operator_chat" → "closed"
                        │
                  watchdog (5 мин)
                  60 мин без ответа → null (возврат ИИ)
```
- `switcher=true` от Coordinator → `pending` → ImConnector chat
- `IMOPENLINES.SESSION.FINISH` → `closed`
- Watchdog сбрасывает `operator_last_reply_at` при возврате

---

## Multi-Agent Pipeline (S02/S03)

```
Входящее сообщение клиента
        │
   SupportService
        │
   ┌────┴─────────────────┐
   │  R1 (параллельно)    │
   │  _r1_lawyer          │
   │  _r1_sales           │
   └────┬─────────────────┘
        │
   _r1_manager (синтез R1)
        │
   R2 (последовательно)
   _r2_lawyer → _r2_manager → _r2_sales
        │
   Coordinator
        │
   JSON: {"answer": "...", "switcher": "true"|"false"}
```

- Модели: `OPENAI_MODEL_SUPPORT` (gpt-4o-mini) — агенты; `OPENAI_MODEL_COORDINATOR` (gpt-4o) — координатор
- Контекст: последние 10 сообщений `chat_history` + `COMPANY_FACTS` (все 7 агентов) + профиль сделки из `get_deal_profile()`
- Fallback: исключение → `chat_as_alina()` → хардкод `FALLBACK_ALINA`
- `escalation_type`: `conflict` / `request` / `none` — дифференцированные ответы при эскалации

---

## Webhook Server (`webhook_server.py`)

- **Порт:** 8080 (для Bitrix, не для Telegram)
- **Технология:** aiohttp
- **Эндпоинты:**

| Путь | Событие | Действие |
|------|---------|---------|
| `/bitrix/operator-message` | `ONIMCONNECTORMESSAGEADD` | Парсинг BB-кодов → пересылка в Telegram |
| `/bitrix/session-finish` | `IMOPENLINES.SESSION.FINISH` | Закрытие эскалации → `escalation_state="closed"` |
| `/bitrix/crm-deal-update` | `ONCRMDEALUPDATE` | Upsert полей сделки в `electronic_case` |

- Вложения скачиваются в `documents/`
- Доставка подтверждена через Telegram MCP за ~0.18s

---

## Electronic Case (S04)

### Supabase `electronic_case` (третий проект)
6 таблиц, 6 индексов:

| Таблица | Содержимое |
|---------|-----------|
| `cases` | Основные данные дела: ИНН, стадия, менеджер, реквизиты |
| `property` | Имущество клиента |
| `debts` | Долги |
| `payments` | Платежи |
| `documents` | Документы (чеклист, статусы) |
| `communications` | История взаимодействий |

Env: `SUPABASE_CASES_URL`, `SUPABASE_CASES_ANON_KEY`.

### Синхронизация
- **Начальная:** `scripts/sync_bitrix_to_cases.py` — 992/996 активных сделок (2 пропущено, нет ИНН)
- **Текущая:** webhook `ONCRMDEALUPDATE` → `/bitrix/crm-deal-update` → upsert по `inn`
- **Маппинг:** `services/cases_mapper.py` — общий модуль; enum-декодирование `city`/`court_region`

### Document Validator (`services/document_validator.py`)
- Сканирует подпапку `Неразобранное` (1 уровень вглубь) в папке Bitrix-диска клиента
- Поддержка: PDF (PyMuPDF) и изображения (Pillow)
- GPT-4o-mini Vision → 18 типов чеклиста (СНИЛС, паспорт, ИНН и др.)
- Пересчёт `checklist_completion` при каждом запуске

---

## Request Flow

```
Telegram update
    │
    ▼
SessionMiddleware
    │  get_or_create_session(chat_id, update_id)
    │  дедупликация по update_id
    ▼
Handler routing (по типу update + session.state)
    │
    ├── /start          → reset session → greeting
    ├── F.contact       → phone verification → Bitrix update → authorized
    ├── F.text (inn)    → Bitrix search → waiting_phone
    ├── F.text (auth)   → SupportService multi-agent pipeline
    │       └── escalated=true → ImConnectorService → Bitrix Open Lines
    └── callbacks       → menu navigation
```

---

## External Integrations

| Сервис | Использование |
|--------|--------------|
| **Supabase (main)** | `bot_sessions` — сессии бота |
| **Supabase (support)** | `chat_history`, судебные документы |
| **Supabase (cases)** | `electronic_case` — данные дел клиентов |
| **Bitrix24** | CRM: сделки, контакты, задачи, чеклисты, Open Lines, Диск |
| **OpenAI** | GPT-4o-mini (агенты, Vision), GPT-4o (координатор) |

---

## Infrastructure

- **Деплой:** Docker Compose на VPS (89.223.125.143)
- **Режим:** Long Polling (не Webhook)
- **Сервисы:** `bot` container + `webhook_server.py` (port 8080), `restart: always`
- **Конфигурация:** `.env` файл

> ⚠️ Перед деплоем деактивировать n8n-воркфлоу `AI-support-main` на `n8n.arbitra.online` — конфликт по токену.

---

## Bitrix24 Custom Fields

| Поле | ID | Назначение |
|------|----|-----------|
| ИНН на сделке | `UF_CRM_1751273997835` | Поиск клиента по ИНН |
| Статус авторизации | `UF_CRM_1768296374` | Проставляется «Авторизирован» после верификации |
| Timestamp авторизации | `UF_CRM_1768547250879` | Дата/время авторизации (МСК) |
| ID папки документов | `UF_FOLDER_ID` | Папка клиента в Bitrix Диске для загрузки файлов |

Воронка БФЛ: `CATEGORY_ID=4`, активные сделки: `STAGE_SEMANTIC_ID=P`.
Open Lines: `connector_id=tg_alina_support`, `openline_id=56`.

---

## Связанные документы

- [CLAUDE.md](CLAUDE.md) — инструкции для разработки
- [SUP-HANDOFF.md](SUP-HANDOFF.md) — текущее состояние и задачи
- [docs/1. SUP-business requirements/BR01_ai_manager_bfl.md](docs/1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md) — бизнес-требования
- [docs/2. SUP-specifications/S04_electronic_case.md](docs/2.%20SUP-specifications/S04_electronic_case.md) — спецификация электронного дела
