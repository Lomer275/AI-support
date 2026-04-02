# Документация: Версионирование и Changelog для проекта

**Версия:** 1.0  
**Дата создания:** 21 ноября 2025  
**Статус:** Действует

---

## 🎯 Цель

Настроить систему версионирования и оформления коммитов, совместимую с GitHub и автогенерацией `CHANGELOG.md`.

Система обеспечивает:
- Прозрачную историю изменений для команды и пользователей
- Автоматизацию релизных процессов через GitHub Actions
- Единообразие коммитов и релизов
- Понятную коммуникацию изменений

---

## 1. Semantic Versioning (SemVer)

Проект следует стандарту [Semantic Versioning 2.0.0](https://semver.org/lang/ru/).

### Формат версии
```
MAJOR.MINOR.PATCH
```

### Компоненты версии

| Компонент | Когда увеличивать | Примеры изменений |
|-----------|-------------------|-------------------|
| **MAJOR** | Несовместимые изменения (ломают API/структуру) | Изменение формата БД без миграции; удаление публичных методов; смена протокола API |
| **MINOR** | Новые функции без поломок | Добавление новых команд бота; новые интеграции; расширение API |
| **PATCH** | Исправления ошибок, мелкие правки | Баг-фиксы; опечатки в документации; оптимизация производительности |

### Примеры версий

| Изменение | Текущая версия | Новая версия |
|-----------|----------------|--------------|
| Первый релиз | — | **1.0.0** |
| Добавлена транскрипция Whisper | 1.0.0 | **1.1.0** |
| Исправлен баг с дублированием видео | 1.1.0 | **1.1.1** |
| Изменена схема БД (несовместимо) | 1.1.1 | **2.0.0** |
| Добавлен анализ через GPT-4 Vision | 2.0.0 | **2.1.0** |
| Исправлена ошибка парсинга object_id | 2.1.0 | **2.1.1** |

### Pre-release версии

Для версий в разработке используется формат:
```
MAJOR.MINOR.PATCH-<label>.<number>
```

**Примеры:**
- `0.1.0-alpha.1` — ранняя альфа-версия
- `0.2.0-beta.3` — бета-версия перед релизом
- `1.0.0-rc.1` — релиз-кандидат

### Версия 0.x.x — Начальная разработка

- Версии `0.x.x` используются для начальной разработки
- Любое изменение может быть несовместимым
- Первый стабильный релиз — `1.0.0`

**Текущая версия проекта:** `v0.1.0`

---

## 2. Conventional Commits

Проект следует стандарту [Conventional Commits 1.0.0](https://www.conventionalcommits.org/).

### Шаблон коммита
```
<тип>(область): краткое описание

[опциональное тело коммита]

[опциональный футер]
```

### Основные типы коммитов

| Тип | Назначение | Влияние на версию |
|-----|------------|-------------------|
| `feat` | Новая фича | MINOR ↑ |
| `fix` | Исправление бага | PATCH ↑ |
| `docs` | Изменения в документации | — |
| `refactor` | Рефакторинг кода без новых фич | — |
| `test` | Добавление или изменение тестов | — |
| `chore` | Служебные изменения, зависимости | — |
| `perf` | Улучшение производительности | PATCH ↑ |
| `style` | Форматирование кода (без логики) | — |
| `ci` | Изменения в CI/CD конфигурации | — |

### Breaking Changes

Для несовместимых изменений добавляется `!` или `BREAKING CHANGE:` в футере:

```bash
feat(database)!: изменить схему таблицы cleanings

BREAKING CHANGE: поле object_id теперь обязательное, требуется миграция данных
```

**Влияние:** MAJOR ↑

### Области (scope)

Опциональная область указывает модуль/компонент:

- `bot` — изменения в ботах (Pyrogram/Aiogram)
- `database` — изменения в моделях БД
- `video` — обработка видео
- `openai` — интеграция с OpenAI
- `airtable` — интеграция с Airtable
- `dropbox` — интеграция с Dropbox
- `worker` — фоновые воркеры
- `docs` — документация

### Примеры коммитов

**Новая фича:**
```bash
feat(video): добавить транскрипцию через OpenAI Whisper

- Интеграция с Whisper API
- Сохранение транскриптов с таймкодами
- Определение номера объекта из речи
```

**Исправление бага:**
```bash
fix(bot): исправить дублирование скачанных видео

Добавлена проверка существования файла перед скачиванием
```

**Документация:**
```bash
docs: создать HANDOFF.md и CHANGELOG.md

Добавлены ключевые документы для управления проектом
```

**Рефакторинг:**
```bash
refactor(database): оптимизировать запросы к таблице videos

Использование eager loading для связанных таблиц
```

**Breaking change:**
```bash
feat(database)!: изменить структуру модели Cleaning

BREAKING CHANGE: удалено поле legacy_status, все статусы теперь в enum
```

---

## 3. Применение на GitHub

### GitHub Releases

| Возможность | Что даёт |
|-------------|----------|
| **Теги (`v1.0.0`)** | GitHub видит релиз, отображает на странице Releases |
| **Release Notes** | GitHub автоматически подтянет список коммитов и `CHANGELOG.md` |
| **Actions (release-please / semantic-release)** | Автоматическая генерация changelog и новых релизов |
| **Cursor / CI** | Понимает Conventional Commits и может генерировать релизные заметки |

### Пример цикла релиза

1. Сделать коммиты по стандарту Conventional Commits
2. Вручную или автоматически проставить тег `v0.2.0`
3. GitHub создаст страницу релиза и подтянет `CHANGELOG.md`
4. Cursor и Actions смогут использовать эти данные для контекста разработки

### Создание тега

**PowerShell:**
```powershell
# Создать аннотированный тег
git tag -a v0.2.0 -m "Release v0.2.0: Video processing pipeline"

# Отправить тег на GitHub
git push origin v0.2.0
```

**Bash:**
```bash
git tag -a v0.2.0 -m "Release v0.2.0: Video processing pipeline"
git push origin v0.2.0
```

### Удаление тега (если ошибка)

```powershell
# Удалить локально
git tag -d v0.2.0

# Удалить на GitHub
git push origin :refs/tags/v0.2.0
```

---

## 4. Автоматизация (опционально)

Для автогенерации changelog и версий можно добавить GitHub Action.

### Вариант 1: release-please

Создать файл `.github/workflows/release.yml`:

```yaml
name: Release
on:
  push:
    branches: [ main ]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: google-github-actions/release-please-action@v4
        with:
          release-type: simple
          package-name: cleaning-bot
```

**Что делает:**
- Автоматически создает PR с обновленным CHANGELOG.md
- При мердже PR создает GitHub Release с тегом
- Версия определяется из коммитов (feat → MINOR, fix → PATCH)

### Вариант 2: semantic-release

```yaml
name: Release
on:
  push:
    branches: [ main ]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install semantic-release
        run: npm install -g semantic-release @semantic-release/changelog
      
      - name: Run semantic-release
        run: npx semantic-release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Требует:** файл `.releaserc.json` с конфигурацией.

---

## 5. Workflow релизов

### Подготовка к релизу

1. **Убедиться, что все изменения закоммичены:**
   ```powershell
   git status
   ```

2. **Проверить CHANGELOG.md:**
   - Секция `[Не выпущено]` содержит все новые изменения
   - Изменения отсортированы по типу (Добавлено/Изменено/Исправлено/Удалено)

3. **Определить новую версию:**
   - Есть `feat` → MINOR ↑ (0.1.0 → 0.2.0)
   - Только `fix` → PATCH ↑ (0.1.0 → 0.1.1)
   - Есть BREAKING CHANGE → MAJOR ↑ (0.1.0 → 1.0.0)

### Создание релиза

1. **Обновить CHANGELOG.md:**
   ```markdown
   ## [0.2.0] - 2025-11-22
   
   ### Добавлено
   - Транскрипция видео через OpenAI Whisper
   - Определение номера объекта из речи клинера
   ```

2. **Обновить версию в README.md:**
   ```markdown
   **Текущая версия:** v0.2.0
   ```

3. **Закоммитить изменения:**
   ```powershell
   git add CHANGELOG.md README.md
   git commit -m "chore: release v0.2.0"
   ```

4. **Создать тег:**
   ```powershell
   git tag -a v0.2.0 -m "Release v0.2.0: Video processing pipeline"
   ```

5. **Отправить на GitHub:**
   ```powershell
   git push origin main
   git push origin v0.2.0
   ```

6. **Создать GitHub Release:**
   - Перейти на GitHub: Releases → Draft a new release
   - Выбрать тег `v0.2.0`
   - Заголовок: `v0.2.0 - Video processing pipeline`
   - Описание: скопировать из CHANGELOG.md
   - Опубликовать

---

## 6. Итоговая структура

| Файл | Назначение |
|------|------------|
| `CHANGELOG.md` | История изменений по релизам (источник истины) |
| `HANDOFF.md` | Текущее состояние и следующие шаги (без истории) |
| `README.md` | Ссылка на текущую версию и changelog |
| GitHub Releases | Автоматически обновляется по тегам SemVer |

---

## 7. Рекомендации

### Для разработчиков

- **Всегда** используйте Conventional Commits
- Пишите понятные сообщения коммитов на русском языке
- Указывайте область (scope) для больших проектов
- Группируйте связанные изменения в один коммит

### Для reviewer'ов

- Проверяйте соответствие коммитов Conventional Commits
- Убеждайтесь, что BREAKING CHANGE отмечены явно
- Проверяйте обновление CHANGELOG.md перед мерджем в main

### Для DevOps

- Настройте автоматизацию через GitHub Actions (release-please или semantic-release)
- Защитите ветку `main` от прямых push'ей
- Требуйте подписанные коммиты (опционально)

---

## Примеры

### Хорошие коммиты ✅

```bash
feat(video): добавить транскрипцию через Whisper
fix(bot): исправить сбой при отсутствии object_id
docs: обновить README с инструкциями по запуску
refactor(database): упростить модель Screenshot
chore(deps): обновить aiogram до 3.2.0
```

### Плохие коммиты ❌

```bash
update code                           # Слишком общее
Fixed bug                             # Нет типа, нет области
feat: new feature                     # На английском, непонятно что именно
WIP                                   # Не информативно
Обновил бота и базу                   # Нет типа, смешаны изменения
```

---

## Дополнительные ресурсы

- [Semantic Versioning](https://semver.org/lang/ru/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)
- [GitHub: Creating releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

---

_Правила версионирования являются обязательными для всех участников проекта._


