# SUP-architecture

**Статус:** draft
**Дата:** 2026-03-20
**Версия:** 0.1

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

### Session Middleware (`middlewares/session.py`)
- Загружает/создаёт сессию через Supabase RPC на каждый update
- Дедуплицирует обновления по `update_id`
- Инжектирует `session` в handler context

### Services (`services/`)
| Файл | Ответственность |
|------|----------------|
| `supabase.py` | Сессии: RPC `get_or_create_session` + PATCH `bot_sessions` |
| `bitrix.py` | Batch-поиск по ИНН, обновление сделки при авторизации |
| `openai_client.py` | 5 промптов для разных состояний бота (персона «Алина») |

### External Integrations
- **Supabase** — хранение сессий (`bot_sessions`), PostgreSQL + REST API
- **Bitrix24** — CRM: сделки (воронка БФЛ), контакты, документы, задачи, чек-листы
- **OpenAI** — GPT-4o-mini, прямые HTTP-запросы через aiohttp

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
                       authorized ◄──── /start (сброс)
```

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
    ├── F.text (auth)   → OpenAI chat as Alina
    └── callbacks       → menu navigation
```

---

## Infrastructure

- **Деплой:** Docker Compose на VPS (89.223.125.143)
- **Режим:** Long Polling (не Webhook)
- **Сервисы:** `bot` container, `restart: always`
- **Конфигурация:** `.env` файл (BOT_TOKEN, SUPABASE_*, BITRIX_*, OPENAI_*)

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

---

## Связанные документы

- [CLAUDE.md](CLAUDE.md) — инструкции для разработки
- [SUP-HANDOFF.md](SUP-HANDOFF.md) — текущее состояние и задачи
- [docs/1. SUP-business requirements/BR01_ai_manager_bfl.md](docs/1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md) — бизнес-требования
