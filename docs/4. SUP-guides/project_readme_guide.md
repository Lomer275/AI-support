## Гайд по составлению корневого README для проекта Cleaning-bot

Этот гайд помогает быстро собрать «опорный» `README.md` для проектов с Telegram-ботами: новый разработчик должен за 5–10 минут понять **что это за проект, как его запустить и где искать детали**.

### Кому нужен README

- **Новые разработчики**: понять контекст, архитектуру двух ботов и минимальный путь запуска.
- **Владелец продукта / заказчик**: увидеть цель проекта и основные компоненты.
- **Внешний архитектор / интегратор**: быстро понять границы ботов, хранение данных и точки интеграций с внешними сервисами.

### Специфика проекта Cleaning-bot

Проект использует **dual-bot архитектуру**:
- **Pyrogram userbot** — работает от имени обычного пользователя, мониторит группы
- **Aiogram bot** — классический бот с командами и админ-панелью

Оба бота запускаются в отдельных потоках с изолированными event loops через threading.

### Обязательная структура корневого README

Рекомендуемый порядок разделов (адаптируйте названия под проект, но сохраняйте смысл блоков).

#### **1. Шапка проекта**
- Краткое имя проекта (одна строка).
- **Текущая версия** в формате SemVer (`vMAJOR.MINOR.PATCH`) и краткий статус этапа.
- Блок быстрых ссылок:
  - на актуальное состояние / следующие шаги (`HANDOFF.md` или аналог),
  - на историю изменений (`CHANGELOG.md`),
  - на конвенции документации (`docs/guides/doc_conventions.md` или аналог).

#### **2. Overview (обзор)**
- 2–4 предложения: что делает система, для кого, какой основной сценарий.
- Основные технологии: Pyrogram (userbot), Aiogram (bot), SQLAlchemy, внешние сервисы.
- Краткий статус этапа разработки.

#### **3. Components / Архитектурный обзор**
Для Cleaning-bot это:
- **Pyrogram Bot** — userbot для мониторинга групп и обработки сообщений от обычного аккаунта.
- **Aiogram Bot** — бот для админ-команд, сцен добавления групп/админов, клавиатур.
- **Database (SQLAlchemy)** — хранение конфигурации групп, пользователей, логов.
- **Services** — интеграции с Airtable, Dropbox, OpenAI.
- **Video Processor** — обработка и анализ видео-контента.
- **Workers** — фоновые задачи (например, cleaning_worker).

Для каждого компонента 1–3 пункта: за что отвечает и от чего зависит.

#### **4. Dual-Bot Architecture (специфика проекта)**
- Пояснить, почему два бота и как они взаимодействуют.
- Описать threading модель: каждый бот в отдельном потоке с собственным event loop.
- Упомянуть graceful shutdown через signal handler.

#### **5. Requirements / Требования**
Явно указать:
- Python 3.10+ (или актуальную версию).
- Необходимость **Telegram аккаунта** для Pyrogram userbot.
- Необходимость создания **bot token** через @BotFather для Aiogram.
- API ключи для внешних сервисов (Airtable, Dropbox, OpenAI).
- Опционально: Docker + Docker Compose (если планируется контейнеризация).

#### **6. Initial Setup (первоначальная настройка)**
**Критично для Cleaning-bot**: перед запуском нужно:
1. Создать `.env` файл с переменными окружения.
2. Запустить **один раз** `login.py` для авторизации Pyrogram и создания `my_account.session`.

Пример команд:

```powershell
# Создать виртуальное окружение
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Установить зависимости
pip install -r requirements.txt

# Авторизация Pyrogram (ОДИН РАЗ)
python login.py
```

После успешной авторизации появится файл `my_account.session` — его нельзя коммитить в Git.

#### **7. Environment Configuration (переменные окружения)**
- Описание того, откуда читаются переменные (`.env`).
- Список **обязательных** переменных окружения **без выдуманных значений по умолчанию**:
  - только имена, краткий комментарий «за что отвечает»,
  - правило: имена переменных — часть контракта, их **нельзя тихо переименовывать**.

Пример для Cleaning-bot:

```text
# Pyrogram (Userbot)
API_ID=<your_telegram_api_id>
API_HASH=<your_telegram_api_hash>

# Aiogram (Bot)
BOT_TOKEN=<your_bot_token_from_botfather>

# Database
DATABASE_URL=<sqlite:///database.db или postgresql DSN>

# External Services
AIRTABLE_API_KEY=<your_airtable_key>
AIRTABLE_BASE_ID=<your_base_id>
DROPBOX_ACCESS_TOKEN=<your_dropbox_token>
OPENAI_API_KEY=<your_openai_key>
```

Явно подчеркните: секреты (`.env`, `my_account.session`) не коммитятся — добавьте в `.gitignore`.

#### **8. Запуск проекта**
Минимальный сценарий: как запустить оба бота одной командой.

```powershell
# Убедитесь, что виртуальное окружение активировано
.\.venv\Scripts\Activate.ps1

# Запуск обоих ботов
python main.py
```

Пояснить:
- Pyrogram и Aiogram запускаются в отдельных потоках.
- Логи отображаются в консоли с префиксами уровней.
- Для остановки: `Ctrl+C` (graceful shutdown через signal handler).

#### **9. Структура проекта**
Краткое описание ключевых папок:

```text
/
├── src/
│   ├── bots/              # Pyrogram и Aiogram боты
│   │   ├── aiogram_bot.py
│   │   ├── pyrogram_bot.py
│   │   ├── keyboards/     # Клавиатуры для Aiogram
│   │   ├── middlewares/   # Middleware (admin, tracking, validation)
│   │   ├── routers/       # Роутеры Aiogram
│   │   └── scenes/        # Aiogram-сцены (FSM)
│   ├── database.py        # SQLAlchemy модели и сессии
│   ├── services/          # Внешние интеграции
│   │   ├── airtable_manager.py
│   │   ├── dropbox_manager.py
│   │   └── openai_manager.py
│   ├── video_processor.py # Обработка видео
│   ├── video.py           # Утилиты для видео
│   ├── utilities/         # Общие утилиты (CSV и т.п.)
│   └── workers/           # Фоновые задачи
│       └── cleaning_worker.py
├── sources/               # Статические ресурсы (изображения)
├── temp/                  # Временные файлы (создается автоматически)
├── docs/                  # Документация
│   └── guides/            # Гайды по разработке
├── login.py               # Скрипт авторизации Pyrogram (один раз)
├── main.py                # Точка входа
└── requirements.txt       # Зависимости Python
```

#### **10. Дополнительные контуры (по необходимости)**
Примеры разделов для будущего:
- **Версионирование**: ссылка на `docs/guides/versioning_guidelines.md`.
- **Тестирование**: как запускать тесты (когда появятся).
- **Docker**: как собрать и запустить в контейнерах.
- **Бэкап БД**: команды для экспорта/импорта данных.
- **Troubleshooting**: частые проблемы и их решения.
- **Миграции БД**: если используются Alembic или аналоги.

### Минимальный чеклист содержимого README

Перед тем как признать README «достаточно хорошим», проверьте:

#### **Контекст**
- [ ] Название проекта и one-liner понятны без знания домена.
- [ ] Указана текущая версия и есть ссылка на `CHANGELOG.md`.
- [ ] Есть ссылка на документ с актуальным состоянием/следующими шагами (аналог `HANDOFF.md`).

#### **Архитектура и компоненты**
- [ ] Объяснена dual-bot архитектура (Pyrogram + Aiogram).
- [ ] Перечислены все основные компоненты (боты, БД, сервисы, workers).
- [ ] Понятно, где хранятся данные (БД, сессии, временные файлы).
- [ ] Упомянута threading модель и изоляция event loops.

#### **Первоначальная настройка**
- [ ] Описан процесс авторизации Pyrogram через `login.py`.
- [ ] Объяснено, что `my_account.session` создается один раз и не коммитится.
- [ ] Указано, как получить BOT_TOKEN через @BotFather.

#### **Запуск**
- [ ] Есть четкая последовательность команд для первого запуска.
- [ ] Описано, как остановить ботов (Ctrl+C).
- [ ] Упомянуто, что логи выводятся в консоль.

#### **Переменные окружения**
- [ ] Перечислен минимальный необходимый набор переменных.
- [ ] Имя каждой переменной соответствует коду (см. `login.py`, `main.py`, конфиги ботов).
- [ ] В README нет вымышленных дефолтных значений, которые могут скрыть отсутствие нужной конфигурации.
- [ ] Явно указано, что `.env` и `my_account.session` должны быть в `.gitignore`.

#### **Навигация**
- [ ] README ссылается на конвенции документации (`docs/guides/doc_conventions.md`).
- [ ] При наличии бэклога/спек есть ссылки на соответствующие папки (`docs/specifications`, `docs/tasks`).

### Шаблон каркаса README для Cleaning-bot

Ниже — минимальный каркас корневого `README.md` для проектов с dual-bot архитектурой. Замените плейсхолдеры в `<>` и уберите неактуальные блоки.

```markdown
# <PROJECT_NAME>

**Текущая версия:** v<MAJOR.MINOR.PATCH> (<Краткое описание этапа>)

> 📋 **Для новых разработчиков:** См. [`HANDOFF.md`](HANDOFF.md) для текущего состояния проекта и следующих шагов.  
> 📜 **История изменений:** См. [`CHANGELOG.md`](CHANGELOG.md) для истории изменений и релизов.  
> 📐 **Конвенции документации:** См. [`docs/guides/doc_conventions.md`](docs/guides/doc_conventions.md)

## Overview

Этот проект реализует систему <краткое описание функционала> на базе **двух Telegram-ботов**:
- **Pyrogram userbot** — мониторинг и обработка сообщений от имени пользователя.
- **Aiogram bot** — административные команды и управление через бот-интерфейс.

Основные технологии: Python 3.10+, Pyrogram (kurigram), Aiogram 3.x, SQLAlchemy, интеграции с Airtable/Dropbox/OpenAI.

**Текущая версия:** v<MAJOR.MINOR.PATCH>. См. [`CHANGELOG.md`](CHANGELOG.md) для деталей.

> Актуальное состояние и следующие шаги: см. [`HANDOFF.md`](HANDOFF.md)

## Components

- **Pyrogram Bot** (`src/bots/pyrogram_bot.py`) — userbot для мониторинга групп, обработки сообщений.
- **Aiogram Bot** (`src/bots/aiogram_bot.py`) — бот для админ-команд, клавиатур, FSM-сцен.
- **Database** (`src/database.py`) — SQLAlchemy модели для хранения конфигурации, пользователей, логов.
- **Services** (`src/services/`) — интеграции с Airtable, Dropbox, OpenAI.
- **Video Processor** (`src/video_processor.py`, `src/video.py`) — обработка и анализ видео.
- **Workers** (`src/workers/`) — фоновые задачи (например, `cleaning_worker.py`).

### Dual-Bot Architecture

Оба бота запускаются в отдельных потоках (`threading.Thread`), каждый с собственным `asyncio` event loop:
- **Pyrogram Thread** — работает от имени пользователя, требует сессию `my_account.session`.
- **Aiogram Thread** — классический бот, требует `BOT_TOKEN` от @BotFather.

Graceful shutdown реализован через `signal.SIGINT` handler (Ctrl+C).

## Requirements

- **Python 3.10+**
- **Telegram аккаунт** для Pyrogram userbot (нужны `API_ID`, `API_HASH` с https://my.telegram.org).
- **Bot Token** от @BotFather для Aiogram бота.
- **API ключи** для внешних сервисов (Airtable, Dropbox, OpenAI).

## Initial Setup

### 1. Установка зависимостей

```powershell
# Создать виртуальное окружение
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Установить зависимости
pip install -r requirements.txt
```

### 2. Конфигурация переменных окружения

Создайте файл `.env` в корне проекта (см. раздел **Environment Configuration** ниже).

### 3. Авторизация Pyrogram (ОДИН РАЗ)

**Важно:** перед запуском `main.py` необходимо авторизовать Pyrogram userbot.

```powershell
python login.py
```

Скрипт запросит:
- Номер телефона
- Код подтверждения из Telegram
- Пароль двухфакторной аутентификации (если включен)

После успешной авторизации создастся файл `my_account.session` — **не коммитьте его в Git** (добавьте в `.gitignore`).

## Environment Configuration

Переменные окружения загружаются из файла `.env` в корне проекта.  
**Не коммитьте секреты.** Держите `.env` и `my_account.session` в секрете.

Минимальный набор переменных (имена менять нельзя, значения подставьте по вашим данным):

```text
# Pyrogram (Userbot)
API_ID=<your_telegram_api_id>
API_HASH=<your_telegram_api_hash>

# Aiogram (Bot)
BOT_TOKEN=<your_bot_token_from_botfather>

# Database
DATABASE_URL=<sqlite:///database.db или postgresql DSN>

# External Services (если используются)
AIRTABLE_API_KEY=<your_airtable_key>
AIRTABLE_BASE_ID=<your_base_id>
DROPBOX_ACCESS_TOKEN=<your_dropbox_token>
OPENAI_API_KEY=<your_openai_key>
```

**Как получить значения:**
- `API_ID` и `API_HASH`: https://my.telegram.org/apps
- `BOT_TOKEN`: создайте бота через @BotFather
- Ключи внешних сервисов: в соответствующих панелях управления

## Running the Project

После выполнения **Initial Setup** запуск простой:

```powershell
# Убедитесь, что виртуальное окружение активировано
.\.venv\Scripts\Activate.ps1

# Запуск обоих ботов
python main.py
```

**Что происходит:**
- Запускается Pyrogram userbot (требует `my_account.session`).
- Запускается Aiogram bot (требует `BOT_TOKEN`).
- Логи выводятся в консоль с префиксами `INFO`/`WARNING`/`ERROR`.
- Для остановки: **Ctrl+C** (graceful shutdown).

**Полезные команды:**

```powershell
# Повторная авторизация Pyrogram (если сессия устарела)
python login.py

# Проверка зависимостей
pip list

# Обновление зависимостей (осторожно!)
pip install -r requirements.txt --upgrade
```

## Project Structure

```text
/
├── src/
│   ├── bots/                    # Pyrogram и Aiogram боты
│   │   ├── __init__.py
│   │   ├── aiogram_bot.py       # Aiogram бот (entry point)
│   │   ├── pyrogram_bot.py      # Pyrogram userbot (entry point)
│   │   ├── keyboards/           # Клавиатуры для Aiogram
│   │   │   ├── __init__.py
│   │   │   └── admin.py
│   │   ├── middlewares/         # Middleware для обоих ботов
│   │   │   ├── __init__.py
│   │   │   ├── admin.py         # Проверка админ-прав
│   │   │   ├── group_validation.py
│   │   │   └── user_tracking.py
│   │   ├── routers/             # Aiogram роутеры
│   │   │   ├── __init__.py
│   │   │   └── admin.py
│   │   ├── scenes/              # Aiogram FSM-сцены
│   │   │   ├── __init__.py
│   │   │   ├── add_admin.py
│   │   │   └── add_group.py
│   │   └── states/              # Aiogram состояния
│   │       ├── __init__.py
│   │       └── admin.py
│   ├── database.py              # SQLAlchemy модели и сессии
│   ├── services/                # Внешние интеграции
│   │   ├── __init__.py
│   │   ├── airtable_manager.py
│   │   ├── dropbox_manager.py
│   │   └── openai_manager.py
│   ├── utilities/               # Общие утилиты
│   │   ├── __init__.py
│   │   └── csv_utils.py
│   ├── video_processor.py       # Обработка видео
│   ├── video.py                 # Утилиты для работы с видео
│   └── workers/                 # Фоновые задачи
│       ├── __init__.py
│       └── cleaning_worker.py   # Worker для очистки сообщений
├── sources/                     # Статические ресурсы
│   ├── logo.png
│   └── reply.png
├── temp/                        # Временные файлы (создается автоматически)
├── docs/                        # Документация
│   └── guides/                  # Гайды по разработке
│       └── project_readme_guide.md
├── .env                         # Переменные окружения (НЕ КОММИТИТЬ)
├── .gitignore                   # Git ignore rules
├── login.py                     # Скрипт авторизации Pyrogram (один раз)
├── main.py                      # Точка входа (запуск обоих ботов)
├── my_account.session           # Pyrogram сессия (НЕ КОММИТИТЬ)
├── requirements.txt             # Зависимости Python
└── README.md                    # Этот файл
```

## Troubleshooting

### Ошибка "Сессия не найдена!"

```
❌ Сессия не найдена!
Сначала запустите: python login.py
```

**Решение:** запустите `python login.py` для создания сессии.

### Ошибка авторизации Pyrogram

```
FloodWait: Telegram is having internal issues, please try again later.
```

**Решение:** подождите несколько минут и повторите `python login.py`.

### Ошибка "BOT_TOKEN not found"

**Решение:** проверьте, что в `.env` есть строка `BOT_TOKEN=<ваш токен>`.

### Конфликт event loops

Если видите ошибки про "event loop is closed" или "attached to a different loop":
- Убедитесь, что не используете `asyncio.run()` внутри кода ботов.
- Каждый бот работает в своем потоке с изолированным event loop.

## Next Steps

См. [`HANDOFF.md`](HANDOFF.md) для:
- Текущего статуса разработки
- Списка завершенных фич
- Планируемых задач
- Известных проблем

## Additional Documentation

- **Версионирование:** `docs/guides/versioning_guidelines.md` (когда появится)
- **Спецификации:** `docs/specifications/` (когда появится)
- **Выполненные задачи:** `docs/tasks/done/` (когда появится)
```

### Отличия от веб-проектов

Для Telegram-ботов с dual-bot архитектурой:

1. **Нет Docker-секции по умолчанию** — боты обычно запускаются напрямую через `python main.py`.
2. **Критична секция Initial Setup** — авторизация Pyrogram через `login.py` обязательна перед первым запуском.
3. **Акцент на threading** — объяснить, почему два потока и как они изолированы.
4. **Секреты сессий** — `my_account.session` так же важен, как и `.env`.
5. **Troubleshooting** — типичные проблемы с авторизацией, сессиями, event loops.

### Контрольный список для адаптации

При переносе этого гайда на другой проект с ботами:

- [ ] Замените `Cleaning-bot` на имя вашего проекта.
- [ ] Обновите список компонентов (если нет `video_processor`, `workers` и т.п.).
- [ ] Проверьте актуальность переменных окружения в секции **Environment Configuration**.
- [ ] Если используете только один бот (Pyrogram или Aiogram) — упростите секцию **Dual-Bot Architecture**.
- [ ] Если есть Docker — добавьте секцию **Running with Docker** из оригинального гайда.
- [ ] Обновите структуру папок в секции **Project Structure** согласно реальной файловой системе.

