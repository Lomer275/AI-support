# SUP-architecture

**Статус:** актуально
**Дата:** 2026-04-02
**Версия:** 0.5

---

## System Overview

Telegram-бот «Алина» — AI-менеджер сопровождения клиентов по банкротству физических лиц (БФЛ). Заменяет менеджера сопровождения (МС) на всём протяжении воронки БФЛ: авторизация → сбор документов → ожидание суда → завершение процедуры.

Целевое покрытие: 95% задач МС.

---

## Components

### Точка входа (`bot.py`)
- **Технология:** Python 3.11, Aiogram 3.x, Long Polling
- **Инициализирует:** Bot, Dispatcher, единый `aiohttp.ClientSession`, все 9 сервисов
- **Запускает:** polling + `webhook_server.py` (порт 8080) + `escalation_watchdog` (каждые 5 мин)
- **`escalation_watchdog`:** ищет сессии с `escalated=true` и `operator_last_reply_at` > 60 мин → возвращает AI

### Конфигурация (`config.py`)
`Settings` dataclass — загружает все переменные окружения через `from_env()`.

### Handlers (`handlers/`)

| Файл | Состояние | Ответственность |
|------|-----------|----------------|
| `start.py` | любое | `/start` — если AUTHORIZED: показать приветствие без сброса; иначе: сбросить сессию, просить ИНН |
| `text.py` | все | Роутинг по `session.state` → `_handle_waiting_inn` / `_handle_waiting_phone` / `_handle_authorized` |
| `contact.py` | WAITING_PHONE | Верификация телефона: `normalize_phone()` → сравнение с Bitrix → переход в AUTHORIZED |
| `callbacks.py` | AUTHORIZED | Inline-кнопки главного меню (Chat, Payment, Tasks, Docs) |

> Порядок регистрации: `start_router → contact_router → callbacks_router → text_router`. Text router должен быть последним.

### Session Middleware (`middlewares/session.py`)
- Вызывает Supabase RPC `get_or_create_session(chat_id, update_id)` на каждый update
- Дедуплицирует по `update_id` (флаг `is_duplicate`)
- Инжектирует `session` в handler context

### Services (`services/`)

| Файл | Supabase / API | Ключевые методы |
|------|---------------|-----------------|
| `supabase.py` | bot_sessions (main) | `get_or_create_session`, `update_session`, `get_escalated_sessions` |
| `bitrix.py` | Bitrix24 REST batch | `search_by_inn`, `get_deal_profile`, `update_deal_authorized` |
| `openai_client.py` | OpenAI | `chat_as_alina`, `inn_not_found`, `phone_mismatch`, `no_inn_in_text`, `waiting_for_phone` |
| `support.py` | OpenAI | Двухраундовый pipeline: R1 → R2 → Coordinator, метод `answer()` |
| `supabase_support.py` | chat_history, documents (support) | `search_client_by_inn`, `get_chat_history`, `save_chat_message` |
| `im_connector.py` | Bitrix Open Lines OAuth | `send_message`, `send_escalation`, `_refresh_token` |
| `evaluator.py` | OpenAI | `evaluate` — 6 критериев качества (1–5 баллов) |
| `electronic_case.py` | cases (cases) | `get_case_context`, `get_checklist_status` |
| `document_validator.py` | Bitrix Disk + OpenAI Vision + cases | `process_deal_files`, `_validate_one`, `_update_checklist_completion` |
| `cases_mapper.py` | cases, communications (cases) | `build_case_row`, `upsert_case`, `insert_communication` |

Все сервисы получают единый `aiohttp.ClientSession` (создаётся в `bot.py`) и инжектируются через `dp` (workflow_data).

### Keyboards (`keyboards.py`)

| Функция | Тип |
|---------|-----|
| `phone_share_keyboard()` | ReplyKeyboard — кнопка «Поделиться номером» |
| `main_menu_keyboard()` | InlineKeyboard — 4 раздела (Чат, Оплата, Задачи, Документы) |
| `back_to_menu_keyboard()` | InlineKeyboard — кнопка «Главное меню» |
| `remove_keyboard` | ReplyKeyboardRemove |

### Утилиты (`utils.py`)
- `normalize_phone(phone)` — последние 10 цифр (убирает +7/8/код страны)
- `extract_inn(text)` — строго 12-значные последовательности; возвращает `max_digit_sequence_length` для AI-контекста. 10-значные ИНН (юрлица) не поддерживаются.
- `moscow_now()` — UTC+3 ISO timestamp

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
                  60 мин без ответа → null (возврат AI)
```

- `switcher=true` от Coordinator → `pending` → ImConnector chat
- `IMOPENLINES.SESSION.FINISH` → `closed`
- Watchdog сбрасывает `operator_last_reply_at` при возврате AI

### INN Error Counter
`error_count` в `bot_sessions`: инкрементируется при неверном формате ИНН или ИНН не найден в Bitrix. `error_count=1` → стандартный ответ; `≥2` → обязательное упоминание @Lobster_21. Исключение Bitrix счётчик не инкрементирует.

---

## Multi-Agent Pipeline (S02/S03)

```
Входящее сообщение клиента
        │
   SupportService.answer()
        │
   ┌────┴──────────────────────┐
   │  R1 (параллельно)         │
   │  _r1_lawyer               │
   │  _r1_manager              │
   │  _r1_sales                │
   └────┬──────────────────────┘
        │
   _r1_manager (синтез R1)
        │
   R2 (последовательно)
   _r2_lawyer → _r2_manager → _r2_sales
        │
   _coordinator()
        │
   JSON: {"answer": "...", "switcher": "true"|"false", "escalation_type": "conflict|request|none"}
```

- **Модели:** `OPENAI_MODEL_SUPPORT` (gpt-4o-mini) — агенты; `OPENAI_MODEL_COORDINATOR` (gpt-4o) — координатор
- **Контекст:** последние 10 сообщений `chat_history` + `COMPANY_FACTS` (все 7 агентов) + контекст дела из `ElectronicCaseService.get_case_context()` (fallback: `BitrixService.get_deal_profile()`)
- **Retry:** если `accuracy` или `completeness` < 3.5 → повтор Coordinator (до `_RETRY_THRESHOLD`)
- **Fallback:** исключение SupportService → `chat_as_alina()` → хардкод `FALLBACK_ALINA`
- **`escalation_type`:** `conflict` / `request` / `none` — дифференцированные ответы при эскалации

---

## Webhook Server (`webhook_server.py`)

- **Порт:** 8080 (для Bitrix, не для Telegram)
- **Технология:** aiohttp

| Путь | Событие | Действие |
|------|---------|---------|
| `POST /webhook/bitrix/` | `ONIMCONNECTORMESSAGEADD` | Парсинг BB-кодов → `_clean_bb_codes()` → пересылка в Telegram; обновление `operator_last_reply_at` |
| `POST /webhook/bitrix/` | `IMOPENLINES.SESSION.FINISH` | `escalated=false` → уведомление клиенту «AI снова готов помочь» |
| `POST /bitrix/crm-deal-update` | `ONCRMDEALUPDATE` / `ONCRMDEALADD` | Batch-fetch deal+contact → `build_case_row()` → `upsert_case()` → async `process_deal_files()` |

Вложения от оператора скачиваются в `documents/`.

---

## Electronic Case (S04)

### Supabase `electronic_case` (третий проект)

| Таблица | Содержимое |
|---------|-----------|
| `cases` | ИНН, стадия, менеджер, реквизиты, суд, финансы, риск-флаги, `checklist_completion`, `folder_url` |
| `documents` | Загруженные документы: `doc_type`, `status`, `readable`, `reason` |
| `communications` | История комментариев из Bitrix deal'а |

Env: `SUPABASE_CASES_URL`, `SUPABASE_CASES_ANON_KEY`.

### Синхронизация
- **Начальная:** `scripts/sync_bitrix_to_cases.py` — 992/996 активных сделок (4 пропущено без ИНН)
- **Текущая:** webhook `ONCRMDEALUPDATE` → `/bitrix/crm-deal-update` → upsert по `inn`
- **Маппинг:** `services/cases_mapper.py` — общий модуль для bulk-sync и real-time webhook

### Document Validator (`services/document_validator.py`)
- Сканирует подпапку `Неразобранное` (1 уровень вглубь) в папке Bitrix-диска клиента
- Поддержка: PDF (PyMuPDF) и изображения (Pillow — ресайз перед отправкой)
- `OPENAI_MODEL_VALIDATOR` (gpt-4o-mini) Vision → 18 типов чеклиста (СНИЛС, паспорт, ИНН и др.)
- Пересчёт `checklist_completion` при каждом запуске (фиксированный знаменатель `CHECKLIST_ITEMS`)
- Запускается асинхронно (`asyncio.create_task`) — не блокирует webhook-ответ

### ElectronicCaseService (`services/electronic_case.py`)
- `get_case_context(inn)` — форматирует данные дела в читаемую строку для AI агентов (ФИО, стадия, суд, финансы, имущество, риск-флаги, чеклист)
- `get_checklist_status(inn)` — возвращает статус чеклиста документов
- Заменяет `BitrixService.get_deal_profile()` в chat pipeline (с fallback на него при отсутствии данных)

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
    ├── /start             → reset session → greeting
    ├── F.contact          → phone verification → Bitrix update → authorized
    ├── F.text (inn)       → Bitrix search → waiting_phone
    ├── F.text (authorized)→ ElectronicCaseService → SupportService multi-agent pipeline
    │       └── switcher=true → ImConnectorService → Bitrix Open Lines
    └── callbacks          → menu navigation
```

---

## Data Models

### Основное Supabase — `bot_sessions`
```
chat_id                 bigint (PK)
update_id               bigint
state                   text  (waiting_inn | waiting_phone | authorized)
inn                     text
deal_id                 text
contact_id              text
contact_name            text
bitrix_phone            text
error_count             int
context_data            jsonb
escalated               boolean
escalated_at            timestamp
operator_last_reply_at  timestamp
escalation_state        text  (null | pending | in_operator_chat | closed)
```

### Support Supabase — `chat_history`, `documents`
```
chat_history:  chat_id, role (user|assistant), content, created_at
documents:     inn, record_data jsonb (full_document_text, document_type, document_date, document_name)
```

### Cases Supabase — `cases`, `documents`, `communications`
```
cases:          inn (PK), deal_id, full_name, phone, stage, stage_updated_at,
                arbitration_manager, court_region, filing_planned_date, filing_actual_date,
                first_hearing_date, last_hearing_date, total_debt_amount, creditors_count,
                monthly_loan_payment, official_income, current_employer,
                contract_number, contract_date, contract_amount, monthly_payment_amount,
                has_property, property_count, payment_schedule jsonb, checklist_completion int,
                risk_flags jsonb, folder_url, synced_at

documents:      inn, deal_id, file_name, doc_type, status, readable, reason, validated_at

communications: inn, deal_id, comment_text, created_at
```

---

## External Integrations

| Сервис | Использование |
|--------|--------------|
| **Supabase (main)** | `bot_sessions` — сессии бота |
| **Supabase (support)** | `chat_history`, судебные документы клиентов |
| **Supabase (cases)** | `electronic_case` — данные дел, документы, коммуникации |
| **Bitrix24** | CRM: сделки, контакты, задачи, чеклисты, Open Lines, Диск |
| **OpenAI** | gpt-4o-mini (агенты, Vision, evaluator), gpt-4o (координатор) |

---

## Infrastructure

- **Деплой:** Docker Compose на VPS `89.223.125.143`
- **Режим:** Long Polling (не Webhook)
- **Сервисы:** `bot` container + `webhook_server.py` (port 8080), `restart: always`
- **Конфигурация:** `.env` файл
- **Docker:** `NO_PROXY=api.telegram.org,api.openai.com,supabase.co`; `extra_hosts: bitrix.express-bankrot.ru:213.189.219.20`

> ⚠️ Перед деплоем деактивировать n8n-воркфлоу `AI-support-main` на `n8n.arbitra.online` — конфликт по токену.

---

## Environment Variables

| Переменная | Обязательная | Default | Назначение |
|-----------|:---:|---------|-----------|
| `BOT_TOKEN` | ✓ | — | Telegram bot token |
| `SUPABASE_URL` | ✓ | — | Основной Supabase |
| `SUPABASE_ANON_KEY` | ✓ | — | Ключ основного Supabase |
| `SUPABASE_SUPPORT_URL` | ✓ | — | Support Supabase |
| `SUPABASE_SUPPORT_ANON_KEY` | ✓ | — | Ключ support Supabase |
| `SUPABASE_CASES_URL` | ✓ | — | Cases Supabase |
| `SUPABASE_CASES_ANON_KEY` | ✓ | — | Ключ cases Supabase |
| `BITRIX_WEBHOOK_BASE` | ✓ | — | Bitrix REST API base (webhook) |
| `BITRIX_URL` | ✓ | — | Bitrix base URL (для OAuth) |
| `BITRIX_OAUTH_CLIENT_ID` | ✓ | — | OAuth client ID |
| `BITRIX_OAUTH_CLIENT_SECRET` | ✓ | — | OAuth secret |
| `BITRIX_OAUTH_ACCESS_TOKEN` | ✓ | — | OAuth access token |
| `BITRIX_OAUTH_REFRESH_TOKEN` | ✓ | — | OAuth refresh token |
| `OPENAI_API_KEY` | ✓ | — | OpenAI API key |
| `OPENAI_MODEL` | — | gpt-4o-mini | Модель по умолчанию |
| `OPENAI_MODEL_SUPPORT` | — | gpt-4o-mini | Модель агентов R1/R2 |
| `OPENAI_MODEL_COORDINATOR` | — | gpt-4o | Модель координатора |
| `OPENAI_MODEL_VALIDATOR` | — | gpt-4o-mini | Модель Vision-валидатора |
| `OPENAI_PROXY` | — | — | SOCKS5 proxy |
| `BITRIX_OPENLINE_ID` | — | 56 | ID открытой линии |
| `BITRIX_CONNECTOR_ID` | — | tg_alina_support | ID коннектора |
| `WEBHOOK_PORT` | — | 8080 | Порт webhook сервера |

---

## Bitrix24 Custom Fields

| Поле | ID | Назначение |
|------|----|-----------|
| ИНН на сделке | `UF_CRM_1751273997835` | Поиск клиента по ИНН |
| Статус авторизации | `UF_CRM_1768296374` | Проставляется «Авторизирован» после верификации |
| Timestamp авторизации | `UF_CRM_1768547250879` | Дата/время авторизации (МСК) |
| ID папки документов | `UF_FOLDER_ID` | Папка клиента в Bitrix Диске |

Воронка БФЛ: `CATEGORY_ID=4`, активные сделки: `STAGE_SEMANTIC_ID=P`, сортировка: `DATE_CREATE DESC`.
Open Lines: `connector_id=tg_alina_support`, `openline_id=56`.

---

## Scripts

| Скрипт | Назначение | Команда |
|--------|-----------|---------|
| `scripts/quality_run.py` | Оценка качества AI-ответов (6 критериев, 92 вопроса) | `python scripts/quality_run.py [--inn INN] [--limit N] [--output FILE]` |
| `scripts/sync_bitrix_to_cases.py` | One-time bulk синхронизация deals → electronic_case | `python scripts/sync_bitrix_to_cases.py [--limit 5]` |
| `scripts/test_imconnector.py` | Тест отправки в Bitrix Open Lines | `python scripts/test_imconnector.py` |

---

## Связанные документы

- [CLAUDE.md](CLAUDE.md) — инструкции для разработки
- [docs/4. SUP-guides/](docs/4.%20SUP-guides/) — гайды по архитектуре, спекам, задачам, версионированию
