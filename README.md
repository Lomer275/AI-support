# Alina — AI-поддержка клиентов АрбитрА

**Текущая версия:** v2.0.0 (S01–S03 complete, S04 in progress)

> Документация проекта: [`docs/`](docs/)
> Конвенции: [`docs/4. GRISH-guides/doc_conventions.md`](docs/4.%20GRISH-guides/doc_conventions.md)

## Overview

Telegram-бот **Алина** — AI-менеджер сопровождения клиентов по банкротству физических лиц (БФЛ). Аутентифицирует клиентов по ИНН (12 цифр) и номеру телефона, связывает их со сделками в Bitrix24 CRM, ведёт диалог через многоагентный GPT-pipeline (образ «Алина») и при необходимости переключает на живого оператора через Bitrix Open Lines.

Основные технологии: Python 3.11, Aiogram 3.x, aiohttp, Supabase (3 проекта), Bitrix24 REST API, OpenAI API.

## Components

- **Bot** ([bot.py](bot.py)) — точка входа: инициализирует все сервисы, единый `aiohttp.ClientSession`, запускает polling + webhook-сервер + escalation watchdog.
- **Handlers** ([handlers/](handlers/)) — порядок регистрации важен: `start → contact → callbacks → text`
  - `start.py` — команда `/start`; сбрасывает сессию только если не авторизован
  - `contact.py` — верификация телефона через кнопку Telegram
  - `text.py` — роутинг текстовых сообщений по состоянию сессии
  - `callbacks.py` — inline-кнопки главного меню
- **Middlewares** ([middlewares/session.py](middlewares/session.py)) — создание/получение сессии в Supabase, дедупликация по `update_id`
- **Webhook Server** ([webhook_server.py](webhook_server.py), порт 8080) — aiohttp-сервер для событий Bitrix24:
  - `POST /webhook/bitrix/` — сообщение оператора → Telegram, закрытие чата → сброс эскалации
  - `POST /bitrix/crm-deal-update` — изменение сделки → upsert в `electronic_case` Supabase + запуск `DocumentValidator`
- **Services** ([services/](services/)):
  - `supabase.py` — состояние сессий (`bot_sessions`)
  - `bitrix.py` — поиск сделок по ИНН (batch API), обновление полей авторизации
  - `openai_client.py` — базовые AI-ответы (5 промптов под разные состояния)
  - `support.py` — многоагентный pipeline (R1→R2→Coordinator), метод `answer()`
  - `supabase_support.py` — история чатов и судебные документы клиента
  - `imconnector.py` — Bitrix Open Lines (OAuth, отправка в чат оператора)
  - `evaluator.py` — оценка ответов по 6 критериям (1–5 баллов)
  - `electronic_case.py` — чтение электронного дела клиента из Supabase
  - `document_validator.py` — валидация документов через GPT-4o-mini Vision, обновление чеклиста
  - `cases_mapper.py` — маппинг Bitrix-сделки в строки `electronic_case` Supabase

### State Machine

```
/start (не авторизован) → WAITING_INN → WAITING_PHONE → AUTHORIZED
/start (авторизован) → показывает меню, сессия не сбрасывается
```

Состояние хранится в Supabase `bot_sessions`, не в Aiogram FSM.

### Multi-Agent Pipeline (S02)

```
R1: _r1_lawyer + _r1_sales (параллельно) → _r1_manager
R2: _r2_lawyer → _r2_manager → _r2_sales
Coordinator → JSON {"answer": "...", "switcher": "true"|"false"}
```

`switcher=true` → escalation_state="pending" → создаётся чат в Bitrix Open Lines.

### Escalation State Machine

`escalation_state`: `null` → `"pending"` → `"in_operator_chat"` → `"closed"`. Watchdog каждые 5 мин возвращает AI после 60 мин без ответа оператора.

## Requirements

- Python 3.11+
- Три проекта Supabase: основной (`bot_sessions`), support (`chat_history`, документы), electronic_case (`cases`, `communications`)
- Telegram Bot Token (через @BotFather)
- Bitrix24 с настроенным webhook, OAuth и полями ИНН/авторизации на сделках
- OpenAI API Key

## Initial Setup

### 1. Установка зависимостей

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. Конфигурация

Создайте файл `.env` в корне проекта (см. **Environment Configuration**).

### 3. Запуск

```bash
python bot.py
```

## Environment Configuration

```text
# Telegram
BOT_TOKEN=

# Supabase — основной (bot_sessions)
SUPABASE_URL=
SUPABASE_ANON_KEY=

# Supabase — support (chat_history, документы)
SUPABASE_SUPPORT_URL=
SUPABASE_SUPPORT_ANON_KEY=

# Supabase — electronic_case (cases, communications)
SUPABASE_CASES_URL=
SUPABASE_CASES_ANON_KEY=

# Bitrix24
BITRIX_WEBHOOK_BASE=        # Base URL webhook (без слеша в конце)
BITRIX_URL=                 # URL портала Bitrix24
BITRIX_OAUTH_CLIENT_ID=
BITRIX_OAUTH_CLIENT_SECRET=
BITRIX_OAUTH_ACCESS_TOKEN=
BITRIX_OAUTH_REFRESH_TOKEN=
BITRIX_OPENLINE_ID=56       # ID очереди Open Lines
BITRIX_CONNECTOR_ID=tg_alina_support

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini           # Базовые ответы
OPENAI_MODEL_SUPPORT=gpt-4o-mini   # Support-агенты
OPENAI_MODEL_COORDINATOR=gpt-4o    # Coordinator + Evaluator
OPENAI_MODEL_VALIDATOR=gpt-4o-mini # DocumentValidator
OPENAI_PROXY=                      # Опционально: HTTP/SOCKS5

# Server
WEBHOOK_PORT=8080
```

## Running

### Локально

```bash
python bot.py
```

### Docker (production)

```bash
docker compose up -d --build
docker compose logs -f bot
docker compose down
```

> **Важно перед деплоем:** деактивируйте соответствующий workflow в n8n на `n8n.arbitra.online`. VPS: `89.223.125.143`.

## Troubleshooting

**Дублируются сообщения** — проверьте, что n8n workflow деактивирован.

**OpenAI не отвечает** — каждый хэндлер содержит хардкод-фоллбэк строку, бот продолжит работу.

**Supabase RPC ошибка** — убедитесь, что функция `get_or_create_session` создана в БД и `SUPABASE_ANON_KEY` верный.

**ИНН не распознаётся** — поддерживается только 12-значный ИНН (физические лица). 10-значный ИНН юрлиц не поддерживается.

**Токен Bitrix OAuth истёк** — `ImConnectorService` авторефрешит токен автоматически.
