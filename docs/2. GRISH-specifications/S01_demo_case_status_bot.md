# S01: Демо-бот «Алевтина»

**Статус:** draft  
**Дата:** 2026-04-03  
**Версия:** 1.4  
**BR:** [BR01 — Демо-бот «Что с моим делом?»](../1.%20GRISH-business%20requirements/BR01_demo_case_status_bot.md)

---

## 🎯 Цель

Отдельный Telegram-бот **Алевтина** для демонстрации инвестору Гришину. Авторизует клиента по ИНН и телефону, находит его дело в Supabase `electronic_case` и ведёт чистый диалог — без кнопок, без меню, без эскалации на оператора.

Алевтина отвечает ровно на два типа вопросов:
1. **«Что с моим делом?»** — структурированная сводка по делу (стадия, суд, документы, финансы)
2. **«Что делать дальше?»** — конкретные следующие шаги под текущую стадию БФЛ

Всё остальное — redirectит обратно к этим двум темам. Ответы не порождают новые вопросы.

---

## 📦 Scope

### Входит:

**Phase 1 — Авторизация:**
- [ ] `/start` — если не авторизован: сброс сессии, запрос ИНН; если авторизован: «Чем могу помочь?»
- [ ] Поиск ИНН в Bitrix24 (`BitrixService.search_by_inn`)
- [ ] Запрос телефона — единственная кнопка в боте «Поделиться номером»
- [ ] Если пользователь пишет телефон текстом в состоянии `waiting_phone` — просим нажать кнопку
- [ ] Верификация телефона (`normalize_phone`) → переход в `authorized`
- [ ] Сессия в отдельной таблице `demo_bot_sessions` (см. раздел БД)
- [ ] INN error counter: `error_count=1` → стандартный ответ; `≥2` → упоминание @Lobster_21
- [ ] Bitrix-исключение не инкрементирует счётчик ошибок

**Phase 2 — Диалог:**
- [ ] Приветственное сообщение сразу после авторизации
- [ ] На каждое сообщение: один GPT-вызов, возвращающий JSON `{intent, answer}`
- [ ] Интенты: `case_status` / `next_steps` / `greeting` / `gratitude` / `off_topic`
- [ ] Ответ на `case_status` — форматированная сводка из `electronic_case`
- [ ] Ответ на `next_steps` — шаги под текущую стадию дела
- [ ] `greeting` → приветствие; `gratitude` → «Рада помочь!»; `off_topic` → redirect
- [ ] `case_context` кешируется в `demo_bot_sessions.context_data` после первого запроса
- [ ] История диалога: последние 6 сообщений хранятся в `demo_bot_sessions.context_data`
- [ ] Хардкод-фоллбэк при ошибке OpenAI

### Не входит:

- Эскалация на оператора (ImConnector / Bitrix Open Lines)
- Многоагентный pipeline (R1/R2/Coordinator)
- Webhook-сервер (Bitrix-события не обрабатываются)
- Загрузка и валидация документов
- Inline-кнопки и меню (кроме кнопки телефона)

---

## 🏗 Архитектура и структура

### Размещение

Отдельный каталог `demo_bot/` в корне репозитория. Переиспользует сервисы основного бота через прямой импорт при запуске из корня (`PYTHONPATH=.`).

```
demo_bot/
├── bot.py                    # Точка входа: Bot, Dispatcher, polling
├── config.py                 # DemoSettings.from_env() — читает BOT_TOKEN_DEMO
├── keyboards.py              # Только phone_share_keyboard() + remove_keyboard
├── messages.py               # Хардкод-тексты: ИНН не найден, телефон не совпал, ожидание кнопки
├── handlers/
│   ├── __init__.py           # register_all_handlers: start → contact → text
│   ├── start.py              # /start: сброс если не авторизован; «Чем могу помочь?» если авторизован
│   ├── contact.py            # Верификация телефона, переход в authorized + приветствие
│   └── text.py               # waiting_inn: извлечь ИНН → Bitrix → ответ из messages.py;
│                             # waiting_phone: попросить нажать кнопку (messages.py);
│                             # authorized: кеш case_context → AlevtinaService
├── middlewares/
│   └── session.py            # DemoSessionMiddleware(DemoSupabaseService) — своя реализация
└── services/
    ├── demo_supabase.py      # DemoSupabaseService — все методы (get/update/context)
    └── alevtina_service.py   # Один GPT-вызов: JSON {intent, answer}
```

### Переиспользуемые модули (импорт из корня)

| Модуль | Что берём | Примечание |
|--------|-----------|------------|
| `services/bitrix.py` | `BitrixService`, `STAGE_LABELS` | Использует корневой `config.settings` — это ожидаемо, Bitrix общий |
| `services/electronic_case.py` | `ElectronicCaseService.get_case_context()` | Тянет `CHECKLIST_ITEMS` из `document_validator.py` — зависимость нормальная |
| `utils.py` (только) | `normalize_phone()`, `extract_inn()`, `moscow_now()` | `SessionMiddleware` НЕ переиспользуется — см. ниже |
| `utils.py` | `normalize_phone()`, `extract_inn()`, `moscow_now()` | Без изменений |

### Почему НЕ переиспользуем `middlewares/session.py`

`SessionMiddleware` принимает `SupabaseService` и инжектирует `data["supabase"]` — жёсткая типизация под основную таблицу. Для демо-бота нужен `DemoSupabaseService` и таблица `demo_bot_sessions`. Решение: отдельный `demo_bot/middlewares/session.py` с `DemoSessionMiddleware(DemoSupabaseService)`.

### AI-ответы во время авторизации (`messages.py`)

В состояниях `waiting_inn` и `waiting_phone` нет смысла вызывать GPT — ответы стандартные. Все тексты хранятся в `demo_bot/messages.py` как константы:

```python
INN_NOT_FOUND_1 = "Не нашла вашего дела по этому ИНН. Проверьте номер и попробуйте ещё раз."
INN_NOT_FOUND_2 = "Снова не нашла. Проверьте ИНН или обратитесь к менеджеру @Lobster_21."
INN_BITRIX_ERROR = "Технические трудности при поиске. Попробуйте ещё раз через минуту."
PHONE_MISMATCH  = "Номер телефона не совпал с данными в системе. Обратитесь к менеджеру @Lobster_21."
PHONE_USE_BUTTON = "Пожалуйста, используйте кнопку «Поделиться номером» ниже."
WELCOME_AUTHORIZED = "{first_name}, вы авторизованы. Я — Алевтина, ваш помощник по делу о банкротстве.\nСпросите, что происходит с вашим делом или что нужно сделать дальше."
FALLBACK_ALEVTINA  = "Сейчас не могу получить информацию. Обратитесь к вашему менеджеру напрямую."
CASE_NOT_FOUND_MSG = "Данные по вашему делу пока недоступны. Попробуйте через несколько минут или свяжитесь с менеджером напрямую."
```

### Почему НЕ переиспользуем `services/supabase.py`

Основной `SupabaseService` работает с таблицей `bot_sessions`. В Telegram `chat_id` для личного чата равен `user_id` — он одинаков для любого бота. Если один пользователь пишет обоим ботам, они разделят одну строку в `bot_sessions`, что приведёт к коллизии `state`, `context_data` и `error_count`. Решение: **отдельная таблица `demo_bot_sessions`** и новый `DemoSupabaseService`.

### AlevtinaService — один GPT-вызов

Каждое сообщение обрабатывается **одним** вызовом OpenAI с `response_format: json_object`. GPT одновременно классифицирует намерение и генерирует ответ.

```
Запрос к GPT:
  system: [личность + правила + знание БФЛ + данные дела]
  messages: history[-6] + {"role": "user", "content": user_message}
  response_format: {"type": "json_object"}

Ответ GPT (всегда JSON):
  {"intent": "case_status", "answer": "...текст ответа..."}
  {"intent": "next_steps",  "answer": "...текст ответа..."}
  {"intent": "greeting",    "answer": "..."}
  {"intent": "gratitude",   "answer": "..."}
  {"intent": "off_topic",   "answer": "..."}
```

`text.py` берёт `answer` из JSON и отправляет клиенту. Если JSON не распарсился — `FALLBACK_ALEVTINA`.

Модель: `OPENAI_MODEL` (gpt-4o-mini).

### Кеширование `case_context`

`ElectronicCaseService.get_case_context(inn)` — HTTP-запрос к Supabase. Вызывать на каждое сообщение дорого. Стратегия:

```
При первом сообщении в authorized:
  case_context = await electronic_case_svc.get_case_context(inn)
  сохранить в demo_bot_sessions.context_data["case_context"]

При последующих сообщениях:
  case_context = session["context_data"].get("case_context")
  если None (не загрузился) → повторить запрос
```

### Поток при `case_context = None`

`text.py` проверяет наличие `case_context` **до** вызова `AlevtinaService`:

```python
case_context = session["context_data"].get("case_context")
if case_context is None:
    case_context = await electronic_case_svc.get_case_context(inn)
    if case_context is None:
        # Дело не найдено в electronic_case
        await message.answer(CASE_NOT_FOUND_MSG)
        return
    # Сохранить в сессии
    await demo_supabase.update_context(chat_id, case_context=case_context)

await alevtina_svc.handle(message.text, history, case_context)
```

`CASE_NOT_FOUND_MSG`:
```
«Данные по вашему делу пока недоступны. Попробуйте через несколько минут
или свяжитесь с менеджером напрямую.»
```

---

## 🧠 Промпт-архитектура

### Системный промпт

Собирается из трёх частей на каждый запрос:

**Часть 1 — Личность и правила (статичная):**
```
Ты — Алевтина, помощник клиента компании «Экспресс-Банкрот» по делу о банкротстве.

Ты отвечаешь СТРОГО на два типа вопросов:
1. Что происходит с делом клиента прямо сейчас
2. Что клиенту нужно сделать дальше

Всегда отвечай JSON: {"intent": "<тип>", "answer": "<текст>"}

Типы intent:
- case_status  — вопрос о статусе/состоянии дела
- next_steps   — вопрос о следующих шагах/действиях
- greeting     — приветствие
- gratitude    — благодарность
- off_topic    — всё остальное

Правила ответа:
— greeting: поздоровайся и предложи спросить о деле или шагах.
— gratitude: «Рада помочь! Если появятся вопросы — я здесь.»
— off_topic: «Я специализируюсь только на вашем деле и следующих шагах.»
— Никогда не выдумывай факты. Если данных нет — пиши «нет данных».
— Ответ лаконичный, структурированный, человечный. Без канцелярита.
— Ответ НЕ заканчивается вопросом к клиенту.
— ParseMode HTML: используй <b> для заголовков секций.
```

**Часть 2 — Знание процедуры БФЛ (статичная):**
```
ЭТАПЫ БАНКРОТСТВА ФИЗИЧЕСКОГО ЛИЦА И ДЕЙСТВИЯ КЛИЕНТА:

[C4:NEW] Сбор документов (до 14 дней)
  Клиент передаёт документы менеджеру. Без полного пакета дело не движется.
  Обязательные: паспорт, СНИЛС, ИНН.

[C4:UC_07IZ0U] Исковое заявление подготовлено
  Юрист готовит заявление. Клиент начинает копить:
  25 000 руб. — депозит арбитражного суда
  23 000 руб. — публикация финансового управляющего

[C4:PREPAYMENT_INVOICE] Заявление подано в суд
  Ожидание определения суда. Проверять на kad.arbitr.ru по ИНН.
  Суд может принять или оставить без движения.

[C4:11] Заявление оставлено без движения
  Суд запросил доп. документы — срочно передать менеджеру.
  Просрочка = риск отказа.

[C4:EXECUTING] Заявление принято судом, назначено заседание
  Оплатить депозит (25 000 руб.) и публикацию (23 000 руб.) по реквизитам от менеджера.
  Квитанции передать менеджеру.

[C4:12/13/17] Реструктуризация
  Долг не растёт. Коллекторы и приставы не беспокоят.
  НЕ пользоваться личными банковскими картами.
  Получать прожиточный минимум (ПМ) — инструкцию даёт менеджер.
  Финансовый управляющий (ФУ) контролирует счета.

[C4:14/15/18] Реализация имущества
  То же что реструктуризация. Плюс ФУ ведёт реализацию имущества при наличии.
  Клиент ничего не предпринимает самостоятельно.

[C4:WON] Долги списаны
  Суд вынес решение. Счета разблокируются в течение 10 дней.

[C4:2] Замороженная / [C4:UC_PQHMFA] Расторжение / [C4:LOSE] Закрыта
  Нестандартный статус. Рекомендуй связаться с менеджером напрямую.
```

**Часть 3 — Данные конкретного дела (динамическая):**
```
{case_context}  ← из ElectronicCaseService.get_case_context(inn), кешируется в context_data
```

---

## 📋 Граничные сценарии

| Сценарий | Поведение |
|----------|-----------|
| `/start` — не авторизован | Сброс сессии → запрос ИНН |
| `/start` — авторизован | «Чем могу помочь? Спросите о вашем деле или следующих шагах» |
| ИНН не найден, 1-я попытка | AI-ответ без упоминания поддержки |
| ИНН не найден, ≥2 попытки | AI-ответ + обязательно @Lobster_21 |
| Bitrix недоступен | «Технические трудности», счётчик ошибок не растёт |
| Телефон не совпал | AI-ответ + @Lobster_21 |
| Пользователь пишет телефон текстом | «Пожалуйста, используйте кнопку "Поделиться номером"» |
| Дело не найдено в `electronic_case` | `CASE_NOT_FOUND_MSG` — graceful, без краша |
| `case_context` уже в `context_data` | Берём из кеша, Supabase не дёргаем |
| GPT вернул невалидный JSON | `FALLBACK_ALEVTINA` |
| OpenAI недоступен | `FALLBACK_ALEVTINA` |
| Незаполненные критичные поля | «нет данных» в ответе |
| Незаполненные некритичные поля | Секция пропускается |
| Стадия не входит в STAGE_LABELS | GPT рекомендует связаться с менеджером |

**Тексты фоллбэков:**
```
FALLBACK_ALEVTINA = «Сейчас не могу получить информацию. Обратитесь к вашему менеджеру напрямую.»
CASE_NOT_FOUND_MSG = «Данные по вашему делу пока недоступны. Попробуйте через несколько минут или свяжитесь с менеджером напрямую.»
```

**Приветственное сообщение после авторизации:**
```
«{first_name}, вы авторизованы. Я — Алевтина, ваш помощник по делу о банкротстве.
Спросите меня, что происходит с вашим делом или что нужно сделать дальше.»
```

---

## 🧱 База данных

### Новая таблица `demo_bot_sessions`

Отдельная таблица в том же основном Supabase-проекте. Изолирует сессии Алевтины от `bot_sessions` Алины.

```sql
CREATE TABLE demo_bot_sessions (
    chat_id                 BIGINT PRIMARY KEY,
    update_id               BIGINT,
    state                   TEXT DEFAULT 'waiting_inn',
    inn                     TEXT,
    deal_id                 TEXT,
    contact_id              TEXT,
    first_name              TEXT,
    bitrix_phone            TEXT,
    error_count             INT DEFAULT 0,
    context_data            JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
```

**`context_data` структура:**
```json
{
  "case_context": "...строка из ElectronicCaseService...",
  "history": [
    {"role": "user",      "content": "Что с моим делом?"},
    {"role": "assistant", "content": "..."},
    {"role": "user",      "content": "А что дальше?"},
    {"role": "assistant", "content": "..."}
  ]
}
```

Лимит истории: последние **6 сообщений** (3 пары). `case_context` — строка, обновляется при первом `authorized`-сообщении и больше не трогается.

### `DemoSupabaseService`

Новый сервис `demo_bot/services/demo_supabase.py`. Методы:
- `get_or_create_session(chat_id, update_id, first_name)` → dict с дедупликацией
- `update_session(chat_id, **fields)` — обновление любых полей
- `update_context(chat_id, case_context=None, history=None)` — атомарное обновление `context_data`

Не переиспользуем `SupabaseService` — у него другая таблица и RPC `get_or_create_session`.

---

## 🖥 Деплой

- **Сервер:** `194.87.243.188` (основной сервер проекта)
- **Режим:** Long Polling
- **Конфигурация:** добавить в `.env` одну переменную: `BOT_TOKEN_DEMO`

```yaml
# docker-compose.yml — добавить сервис:
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

`PYTHONPATH=/app` обеспечивает корректный импорт `services/`, `utils.py` и `middlewares/` из корня.

---

## 📋 Задачи и параллелизм

```
Group 1 ──► T01: Каркас (bot.py, config.py, keyboards.py, messages.py,
                         DemoSupabaseService (все методы),
                         DemoSessionMiddleware, demo_bot_sessions DDL)
                        │
              ┌─────────┴──────────┐
Group 2      T02: Авторизация    T03: AlevtinaService (промпт + JSON-вызов)
          (start, contact,
           text routing)
              └─────────┬──────────┘
                        │
          ┌─────┬───────┴────────┬──────┐
Group 3  T04  T05              T06    T07
      case_  next_          кеш +  greeting/
      status steps         история gratitude/
                                   off_topic
          └─────┴───────┬────────┴──────┘
                        │
Group 4 ──► T08: Промпт-тюнинг на реальных делах
                        │
Group 5 ──► T09: Docker-сервис + деплой на 194.87.243.188
```

| ID | Задача | Зависит от | Параллельно с | Статус |
|----|--------|------------|---------------|--------|
| T01 | [**Каркас**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T01_s01_skeleton.md) — `bot.py`, `config.py`, `keyboards.py`, `messages.py`, `DemoSupabaseService`, `DemoSessionMiddleware`, SQL DDL | — | — | 🔵 planned |
| T02 | [**Авторизация**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T02_s01_auth.md) — `start.py`, `contact.py`, `text.py` (роутинг + messages.py) | T01 | T03 | 🔵 planned |
| T03 | [**AlevtinaService**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T03_s01_alevtina_service.md) — JSON-промпт, один GPT-вызов, парсинг `{intent, answer}` | T01 | T02 | 🔵 planned |
| T04 | [**case_status**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T04_s01_case_status.md) — кеш `case_context`, поток при None, форматирование сводки | T02, T03 | T05, T06, T07 | 🔵 planned |
| T05 | [**next_steps**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T05_s01_next_steps.md) — маппинг стадий БФЛ → шаги | T02, T03 | T04, T06, T07 | 🔵 planned |
| T06 | [**История диалога**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T06_s01_dialog_history.md) — запись/чтение `history`, передача в GPT | T02, T03 | T04, T05, T07 | 🔵 planned |
| T07 | [**Интенты**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T07_s01_intents.md) — `greeting`, `gratitude`, `off_topic`, фоллбэки | T02, T03 | T04, T05, T06 | 🔵 planned |
| T08 | [**Промпт-тюнинг**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T08_s01_prompt_tuning.md) — тест на 2–3 реальных делах, итерация | T04, T05, T06, T07 | — | 🔵 planned |
| T09 | [**Деплой**](../3.%20GRISH-tasks/S01_demo_case_status_bot/T09_s01_deploy.md) — docker-compose сервис, `.env`, SQL миграция, запуск на `194.87.243.188` | T08 | — | 🔵 planned |

---

## 🧪 DoD

- [ ] Тестировщик авторизуется за реального клиента (ИНН + телефон)
- [ ] `/start` для авторизованного — не сбрасывает сессию
- [ ] Сессия Алевтины изолирована от Алины (таблица `demo_bot_sessions`)
- [ ] На `case_status` — корректная сводка по конкретному делу, нет выдуманных фактов
- [ ] На `next_steps` — шаги соответствуют реальной стадии из `cases.stage`
- [ ] `case_context` запрашивается один раз, кешируется в `context_data`
- [ ] `greeting` → приветствие; `gratitude` → «Рада помочь!»; `off_topic` → redirect
- [ ] История из 6 сообщений учитывается в ответах
- [ ] Ответы не заканчиваются вопросом к клиенту
- [ ] Дело не найдено в `electronic_case` → `CASE_NOT_FOUND_MSG` без краша
- [ ] Невалидный JSON от GPT → `FALLBACK_ALEVTINA` без краша
- [ ] OpenAI недоступен → `FALLBACK_ALEVTINA` без краша
- [ ] Текст телефона вместо кнопки → просим нажать кнопку
- [ ] Бот задеплоен на `194.87.243.188`, `PYTHONPATH` настроен

---

## ⚠️ Риски

- **Пустые данные в `electronic_case`** — подобрать 2–3 дела с полными данными до демо; протестировать `get_case_context()` по их ИНН
- **Качество `next_steps`** — зависит от заполненности `cases.stage`. Итерация промпта обязательна до демо
- **Стадия не в STAGE_LABELS** — GPT получает сырой код стадии; промпт должен это обрабатывать
- **`BitrixService` и `config.settings`** — `BitrixService` импортирует корневой `config.py`; при запуске с `PYTHONPATH=/app` это работает, но Bitrix-настройки всегда берутся из основного `.env`, не из `DemoSettings`

---

## 🔗 Связанные документы

- BR: [BR01_demo_case_status_bot.md](../1.%20GRISH-business%20requirements/BR01_demo_case_status_bot.md)
- Стандарт БФЛ: `docs/5. GRISH-unsorted/Копия (1) Стандарт по работе в воронке банкротство физического лица (1).pdf`
- Книга МС: `docs/5. GRISH-unsorted/Книга МС версия 1.0 (1).pdf`
- Переиспользует: `services/bitrix.py` (STAGE_LABELS), `services/electronic_case.py`

---

## 📝 История изменений

### v1.4 (2026-04-03)
- `off_topic` redirect исправлен: убран вопрос в конце (противоречил правилу «ответ не заканчивается вопросом»)
- `SessionMiddleware` НЕ переиспользуется: добавлен `demo_bot/middlewares/session.py` с `DemoSessionMiddleware`
- Добавлен `demo_bot/messages.py` — хардкод-тексты для auth-flow (ИНН не найден, телефон не совпал и др.)
- `DemoSupabaseService` (все методы) перенесён в T01 (каркас) — устранён конфликт параллелизма T02/T03

### v1.3 (2026-04-03)
- **Критично:** отдельная таблица `demo_bot_sessions` + `DemoSupabaseService` — изоляция от `bot_sessions` Алины
- **Критично:** кеширование `case_context` в `context_data` — один запрос к Supabase за сессию
- **Критично:** явный поток при `case_context = None` — `text.py` проверяет до вызова сервиса
- **Критично:** один GPT-вызов с `json_object` response format — `{intent, answer}` в одном ответе
- Добавлен `PYTHONPATH=/app` и `extra_hosts` в docker-compose
- Добавлен сценарий: пользователь пишет телефон текстом
- «Рад помочь!» → «Рада помочь!» (женский род)
- Описан `text.py` для состояний `waiting_inn` и `waiting_phone`
- SQL DDL для `demo_bot_sessions`

### v1.2 (2026-04-03)
- Все 15 стадий БФЛ с маппингом, граничные сценарии, параллелизм задач

### v1.1 (2026-04-03)
- Промпт-архитектура, история диалога, деплой, intent-ы

### v1.0 (2026-04-02)
- Первая версия
