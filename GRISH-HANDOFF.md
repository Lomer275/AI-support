# GRISH-HANDOFF

**Обновлено:** 2026-04-03  
**Ветка:** Demo_Grishin

---

## Текущий статус

| Спека | Название | Статус |
|-------|----------|--------|
| S01–S03 | Алина (auth, multi-agent chat, quality eval) | ✅ done |
| S04 | Electronic Case | 🔄 in progress |
| S05 | Proactive notifications | 📋 backlog |
| S06 | Menu: tasks + payments | 📋 backlog |

---

## S01 Demo: Демо-бот «Алевтина»

Отдельный Telegram-бот для демонстрации инвестору Гришину. Отвечает на два вопроса: «Что с моим делом?» и «Что делать дальше?». Авторизация по ИНН + телефон. Данные из `electronic_case` Supabase.

**Порядок выполнения:**

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| [T01](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T01_s01_skeleton.md) | Каркас (bot.py, config.py, keyboards.py, messages.py, DemoSupabaseService, DemoSessionMiddleware, DDL) | — | 🔵 planned |
| [T02](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T02_s01_auth.md) | Авторизация (start, contact, text routing, error_count) | T01 | 🔵 planned |
| [T03](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T03_s01_alevtina_service.md) | AlevtinaService (промпт + JSON GPT-вызов) | T01 | 🔵 planned |
| [T04](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T04_s01_case_status.md) | case_status + кеш case_context | T02, T03 | 🔵 planned |
| [T05](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T05_s01_next_steps.md) | next_steps (шаги под стадию БФЛ) | T02, T03 | 🔵 planned |
| [T06](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T06_s01_dialog_history.md) | История диалога (history в context_data) | T02, T03 | 🔵 planned |
| [T07](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T07_s01_intents.md) | Интенты greeting/gratitude/off_topic + фоллбэки | T02, T03 | 🔵 planned |
| [T08](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T08_s01_prompt_tuning.md) | Промпт-тюнинг на реальных делах | T04–T07 | 🔵 planned |
| [T09](docs/3.%20GRISH-tasks/S01_demo_case_status_bot/T09_s01_deploy.md) | Деплой на 194.87.243.188 | T08 | 🔵 planned |

**Параллелизм:** T02 ‖ T03 → T04 ‖ T05 ‖ T06 ‖ T07 → T08 → T09

**Старт:** T01 — точка входа. После T01 можно запустить T02 и T03 одновременно.

---

## Ключевые решения

- `demo_bot_sessions` — отдельная таблица (изоляция от `bot_sessions` Алины, т.к. `chat_id` совпадает у одного пользователя в обоих ботах)
- `DemoSessionMiddleware` — своя реализация (не переиспользует `SessionMiddleware` из-за жёсткой типизации под `SupabaseService`)
- Один GPT-вызов с `response_format: json_object` → `{intent, answer}`
- `case_context` кешируется в `context_data` после первого запроса
- `BOT_TOKEN_DEMO` — единственная новая переменная окружения

---

## Ссылки

- Спека: [S01_demo_case_status_bot.md](docs/2.%20GRISH-specifications/S01_demo_case_status_bot.md)
- BR: [BR01_demo_case_status_bot.md](docs/1.%20GRISH-business%20requirements/BR01_demo_case_status_bot.md)
- Архитектура: [GRISH-architecture.md](GRISH-architecture.md)
