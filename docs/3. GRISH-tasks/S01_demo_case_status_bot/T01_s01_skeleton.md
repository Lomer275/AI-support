Дата: 2026-04-03
Статус: draft
Спецификация: docs/2. GRISH-specifications/S01_demo_case_status_bot.md

# T01_s01_skeleton — Каркас демо-бота

## Customer-facing инкремент

Бот запускается, принимает сообщение и создаёт сессию в Supabase `demo_bot_sessions`. Инфраструктура готова для подключения авторизации и диалога.

## Цель

Создать полную инфраструктуру демо-бота: точку входа, конфиг, клавиатуру, константы сообщений, сервис работы с Supabase, middleware для сессий и SQL-таблицу.

## Контекст

Алевтина — отдельный бот (`demo_bot/`) в том же репозитории. Переиспользует `services/bitrix.py`, `services/electronic_case.py`, `utils.py` из корня через `PYTHONPATH=/app`. Основная Алина продолжает работать параллельно — сессии изолированы через отдельную таблицу `demo_bot_sessions`.

## Scope

- `demo_bot/bot.py` — инициализация `Bot`, `Dispatcher`, регистрация middleware и хэндлеров, запуск polling
- `demo_bot/config.py` — класс `DemoSettings` с методом `from_env()`, читает `BOT_TOKEN_DEMO` (плюс переиспользует `SUPABASE_URL`, `SUPABASE_ANON_KEY` из окружения)
- `demo_bot/keyboards.py` — функции `phone_share_keyboard()` и `remove_keyboard()`
- `demo_bot/messages.py` — все хардкод-константы:
  - `INN_NOT_FOUND_1`, `INN_NOT_FOUND_2`, `INN_BITRIX_ERROR`
  - `PHONE_MISMATCH`, `PHONE_USE_BUTTON`
  - `WELCOME_AUTHORIZED`
  - `FALLBACK_ALEVTINA`, `CASE_NOT_FOUND_MSG`
- `demo_bot/services/demo_supabase.py` — класс `DemoSupabaseService`, все три метода:
  - `get_or_create_session(chat_id, update_id, first_name)` → dict с дедупликацией по `update_id`
  - `update_session(chat_id, **fields)` — обновление любых полей строки
  - `update_context(chat_id, case_context=None, history=None)` — атомарное обновление `context_data` JSONB
- `demo_bot/middlewares/session.py` — `DemoSessionMiddleware(DemoSupabaseService)`:
  - Получает или создаёт сессию на каждый update
  - Инжектирует `data["demo_session"]` и `data["demo_supabase"]`
  - Дедупликация: если `is_duplicate=True` — пропускает update
- `demo_bot/handlers/__init__.py` — `register_all_handlers(dp)`: порядок start → contact → text
- SQL DDL таблицы `demo_bot_sessions` (выполнить в Supabase SQL Editor основного проекта):

```sql
CREATE TABLE demo_bot_sessions (
    chat_id      BIGINT PRIMARY KEY,
    update_id    BIGINT,
    state        TEXT DEFAULT 'waiting_inn',
    inn          TEXT,
    deal_id      TEXT,
    contact_id   TEXT,
    first_name   TEXT,
    bitrix_phone TEXT,
    error_count  INT DEFAULT 0,
    context_data JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);
```

## Out of scope

- Логика авторизации (ИНН, телефон) — T02
- GPT-вызов и AlevtinaService — T03
- Обработка диалоговых сообщений — T04–T07
- Docker и деплой — T09

## Технические детали

**bot.py** создаёт единый `aiohttp.ClientSession`, инициализирует `DemoSupabaseService`, регистрирует `DemoSessionMiddleware` как outer middleware на `dp.message`, регистрирует хэндлеры через `register_all_handlers(dp)`, запускает `dp.start_polling(bot)`.

**DemoSettings.from_env()** читает переменные окружения. `BOT_TOKEN_DEMO` — обязательная. Supabase URL/KEY берётся из тех же `SUPABASE_URL` / `SUPABASE_ANON_KEY`, что и основной бот (основной Supabase-проект, там будет `demo_bot_sessions`).

**DemoSessionMiddleware** реализует `BaseMiddleware`. Логика аналогична `middlewares/session.py` основного бота, но:
- Использует `DemoSupabaseService` вместо `SupabaseService`
- Инжектирует `data["demo_session"]` и `data["demo_supabase"]`
- Таблица `demo_bot_sessions` вместо `bot_sessions`

**update_context** обновляет поля в `context_data` JSONB атомарно — не перезатирает соседние ключи. Пример: если передан только `case_context`, ключ `history` в JSONB не трогается.

## Как протестировать

### 1. Базовый сценарий

1. Добавить `BOT_TOKEN_DEMO` в `.env`
2. Выполнить DDL в Supabase SQL Editor
3. Запустить `python demo_bot/bot.py` из корня репозитория
4. Написать боту любое сообщение
5. Проверить:
   - Строка появилась в `demo_bot_sessions` с `state='waiting_inn'`
   - В логах нет ошибок импорта
   - Повторная отправка того же `update_id` не создаёт дубль в БД

### 2. Изоляция от Алины

1. Запустить обоих ботов одновременно
2. Написать в Алевтину и в Алину с одного Telegram-аккаунта
3. Проверить: записи в `bot_sessions` и `demo_bot_sessions` независимы, состояния не пересекаются

## Критерии приёмки

1. `python demo_bot/bot.py` запускается без ошибок при наличии `BOT_TOKEN_DEMO` в `.env`
2. Первое сообщение создаёт строку в `demo_bot_sessions` с `state='waiting_inn'`
3. Повторный update с тем же `update_id` не дублируется
4. Запись в `demo_bot_sessions` не конфликтует с записью того же `chat_id` в `bot_sessions`
5. `keyboards.phone_share_keyboard()` возвращает `ReplyKeyboardMarkup` с кнопкой «Поделиться номером»
6. Все константы из `messages.py` доступны для импорта

## Правила завершения задачи

**После акцепта задачи AI выполняет автоматически:**

1. **Обновить файл задачи:**
   - Статус → `✅ accepted`
   - Добавить дату завершения

2. **Переместить файл:**
   - Из: `docs/3. GRISH-tasks/S01_demo_case_status_bot/T01_s01_skeleton.md`
   - В: `docs/3. GRISH-tasks/Done/S01_demo_case_status_bot_done/T01_s01_skeleton_done.md`

3. **Обновить спецификацию:**
   - Статус T01 → `✅ done`

4. **Обновить GRISH-HANDOFF.md:**
   - Отметить T01 как выполненную
