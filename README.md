# Alina — AI-поддержка клиентов АрбитрА

**Текущая версия:** v1.0.0 (первичный запуск)

> Документация проекта: [`docs/`](docs/)
> Конвенции: [`docs/4. SUP-guides/doc_conventions.md`](docs/4.%20SUP-guides/doc_conventions.md)

## Overview

Telegram-бот **Алина** — AI-ассистент клиентской поддержки сервиса [Экспресс-Банкрот](https://express-bankrot.ru). Аутентифицирует клиентов по ИНН (12 цифр) и номеру телефона, связывает их со сделками в Bitrix24 CRM, и ведёт диалог через GPT (образ «Алина»).

Основные технологии: Python 3.11, Aiogram 3.x, Supabase (состояние сессий), Bitrix24 REST API, OpenAI API.

## Components

- **Bot** ([bot.py](bot.py)) — точка входа, инициализация сервисов и диспетчера.
- **Handlers** ([handlers/](handlers/)) — обработчики событий по типам:
  - `start.py` — команда `/start`, сброс сессии
  - `contact.py` — получение номера телефона через кнопку
  - `text.py` — текстовые сообщения, роутинг по состоянию сессии
  - `callbacks.py` — inline-кнопки главного меню
- **Middlewares** ([middlewares/session.py](middlewares/session.py)) — получение/создание сессии в Supabase, дедупликация по `update_id`
- **Services** ([services/](services/)):
  - `supabase.py` — хранение состояния сессий (таблица `bot_sessions`)
  - `bitrix.py` — поиск сделок по ИНН через batch API
  - `openai_client.py` — генерация ответов (5 промптов под разные состояния)
- **State Machine** ([states.py](states.py)) — три состояния: `waiting_inn`, `waiting_phone`, `authorized`
- **Keyboards** ([keyboards.py](keyboards.py)) — ReplyKeyboard и InlineKeyboard
- **Utils** ([utils.py](utils.py)) — `normalize_phone()`, `extract_inn()`, `moscow_now()`

### State Machine

```
/start → WAITING_INN → WAITING_PHONE → AUTHORIZED
               ↑ (ИНН не найден)     ↑ (телефон не совпал)
```

`/start` всегда сбрасывает сессию в `waiting_inn`.

## Requirements

- Python 3.11+
- Аккаунт Supabase с таблицей `bot_sessions` и RPC `get_or_create_session`
- Telegram Bot Token (через @BotFather)
- Bitrix24 с настроенным webhook и полями ИНН на сделках
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

Создайте файл `.env` в корне проекта (см. раздел **Environment Configuration**).

### 3. Запуск

```bash
python bot.py
```

## Environment Configuration

Переменные загружаются из `.env`. Не коммитьте секреты.

```text
BOT_TOKEN=           # Telegram bot token от @BotFather
SUPABASE_URL=        # URL Supabase проекта
SUPABASE_ANON_KEY=   # Anon key Supabase
BITRIX_WEBHOOK_BASE= # Base URL Bitrix24 webhook (без слеша в конце)
OPENAI_API_KEY=      # OpenAI API key
OPENAI_MODEL=        # Модель OpenAI, например: gpt-4o-mini
```

## Running

### Локально

```bash
python bot.py
```

### Docker (production)

```bash
# Запуск
docker compose up -d --build

# Логи
docker compose logs -f bot

# Остановка
docker compose down
```

> **Важно перед деплоем:** деактивируйте соответствующий workflow в n8n на `n8n.arbitra.online`, чтобы избежать дублирования обработки сообщений. VPS: `89.223.125.143`.

## Project Structure

```text
/
├── handlers/
│   ├── __init__.py          # Регистрация роутеров (порядок важен)
│   ├── start.py             # /start — сброс сессии
│   ├── contact.py           # Получение телефона через кнопку
│   ├── text.py              # Текстовые сообщения (catch-all)
│   └── callbacks.py         # Inline-кнопки меню
├── middlewares/
│   ├── __init__.py
│   └── session.py           # Supabase сессия + дедупликация
├── services/
│   ├── __init__.py
│   ├── supabase.py          # Хранение состояния сессий
│   ├── bitrix.py            # CRM: поиск сделок по ИНН (batch API)
│   └── openai_client.py     # GPT-ответы (5 промптов)
├── docs/                    # Документация проекта
│   ├── 3. SUP-tasks/        # Задачи
│   ├── 4. SUP-guides/       # Гайды по разработке
│   └── 5. SUP-unsorted/     # ТЗ и прочие материалы
├── bot.py                   # Точка входа
├── config.py                # Настройки из .env
├── states.py                # Состояния сессии
├── keyboards.py             # Клавиатуры
├── utils.py                 # normalize_phone, extract_inn, moscow_now
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                     # Секреты (НЕ КОММИТИТЬ)
```

## Bitrix24 Integration Notes

Batch-запрос к Bitrix24 ищет сделки с фильтрами: `CATEGORY_ID=4`, `STAGE_SEMANTIC_ID=P` (активные).
Кастомные поля сделок:

| Поле | Назначение |
|------|-----------|
| `UF_CRM_1751273997835` | ИНН клиента |
| `UF_CRM_1768296374` | Статус авторизации |
| `UF_CRM_1768547250879` | Временная метка авторизации (UTC+3) |

## Troubleshooting

**Дублируются сообщения** — проверьте, что n8n workflow деактивирован.

**OpenAI не отвечает** — каждый хэндлер содержит хардкод-фоллбэк строку, бот продолжит работу.

**Supabase RPC ошибка** — убедитесь, что функция `get_or_create_session` создана в БД и `SUPABASE_ANON_KEY` верный.

**ИНН не распознаётся** — бот поддерживает только 12-значный ИНН (физические лица). 10-значный ИНН (юридические лица) не поддерживается.
