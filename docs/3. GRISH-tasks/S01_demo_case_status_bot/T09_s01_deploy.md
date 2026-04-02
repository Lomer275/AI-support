Дата: 2026-04-03
Статус: draft
Спецификация: docs/2. GRISH-specifications/S01_demo_case_status_bot.md

# T09_s01_deploy — Docker-сервис и деплой на 194.87.243.188

## Customer-facing инкремент

Алевтина работает на production-сервере. Тестировщик может открыть бота в Telegram и авторизоваться за реального клиента без локального запуска.

## Цель

Добавить `demo_bot` как сервис в `docker-compose.yml`, добавить переменную окружения `BOT_TOKEN_DEMO` в `.env` на сервере, выполнить SQL-миграцию в Supabase, запустить бота.

## Контекст

T08 завершён — бот проверен на реальных делах. Деплой выполняется на тот же сервер `194.87.243.188`, где работает основная Алина. Оба бота работают параллельно в отдельных Docker-контейнерах.

## Scope

**1. Обновить `docker-compose.yml`** — добавить сервис:
```yaml
demo_bot:
  build: .
  command: python demo_bot/bot.py
  env_file: .env
  working_dir: /app
  environment:
    - PYTHONPATH=/app
    - NO_PROXY=api.telegram.org,api.openai.com,supabase.co
  extra_hosts:
    - "bitrix.express-bankrot.ru:213.189.219.20"
  restart: always
```

**2. Добавить в `.env` на сервере:**
```
BOT_TOKEN_DEMO=<токен от @BotFather>
```
Все остальные переменные (Supabase, Bitrix, OpenAI) уже есть в `.env` — `demo_bot` их переиспользует.

**3. SQL-миграция в Supabase** (основной проект, `SUPABASE_URL`):
```sql
CREATE TABLE IF NOT EXISTS demo_bot_sessions (
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
Выполнить в Supabase SQL Editor основного проекта.

**4. Запуск:**
```bash
docker compose up -d --build demo_bot
docker compose logs -f demo_bot
```

**5. Проверить:**
- Бот отвечает на `/start` в Telegram
- Основная Алина продолжает работать (`docker compose ps`)
- Логи без ошибок импорта и подключения

## Out of scope

- Настройка webhook (бот работает на long polling)
- Изменение конфигурации Nginx или firewall
- Деактивация n8n workflow (оно относится только к Алине, не к Алевтине)

## Технические детали

`PYTHONPATH=/app` в environment обеспечивает импорт `services/`, `utils.py`, `config.py` из корня репозитория внутри контейнера `demo_bot`.

`NO_PROXY` — предотвращает проксирование запросов к Telegram API и Supabase через корпоративный прокси (если настроен в окружении).

`extra_hosts` — резолвит `bitrix.express-bankrot.ru` в IP напрямую (обходит DNS при необходимости).

`restart: always` — автоперезапуск при краше или перезагрузке сервера.

Токен `BOT_TOKEN_DEMO` получить у @BotFather: создать нового бота с именем «Алевтина».

## Как протестировать

### 1. Бот запускается

1. SSH на `194.87.243.188`
2. `docker compose up -d --build demo_bot`
3. `docker compose logs demo_bot` — нет ошибок, строка «Polling started»

### 2. End-to-end тест

1. Открыть бота в Telegram (по ссылке @...)
2. `/start` → запрос ИНН
3. Ввести ИНН клиента с заполненным делом
4. Поделиться телефоном
5. Написать «Что с моим делом?» → сводка по делу
6. Написать «Что делать дальше?» → конкретные шаги

### 3. Изоляция от Алины

1. Написать в обоих ботах с одного аккаунта
2. Проверить в Supabase: `bot_sessions` и `demo_bot_sessions` — отдельные записи

## Критерии приёмки

1. `docker compose ps` показывает `demo_bot` в статусе `Up`
2. `/start` в Telegram возвращает запрос ИНН
3. Полный авторизационный флоу проходит на production-сервере
4. Ответы на `case_status` и `next_steps` корректны
5. Алина (`bot`) продолжает работать без изменений
6. Таблица `demo_bot_sessions` создана в Supabase

## Правила завершения задачи

**После акцепта задачи AI выполняет автоматически:**

1. **Обновить файл задачи:**
   - Статус → `✅ accepted`
   - Добавить дату завершения

2. **Переместить файл:**
   - Из: `docs/3. GRISH-tasks/S01_demo_case_status_bot/T09_s01_deploy.md`
   - В: `docs/3. GRISH-tasks/Done/S01_demo_case_status_bot_done/T09_s01_deploy_done.md`

3. **Обновить спецификацию:**
   - Статус T09 → `✅ done`

4. **Обновить GRISH-HANDOFF.md:**
   - Отметить T09 как выполненную
