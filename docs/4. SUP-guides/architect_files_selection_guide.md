# Гайд: Выбор файлов для AI-архитектора

**Версия:** 1.0  
**Дата создания:** 2025-01-30  
**Статус:** Действует

---

## 🎯 Назначение

Этот гайд помогает быстро определить минимальный набор критичных файлов для передачи внешнему AI-архитектору при анализе задачи или бага.

**Цели:**
- Снизить расход токенов при передаче контекста архитектору
- Целевой расход: **~180k токенов или меньше**
- Обеспечить, что архитектор получит все необходимые файлы для анализа

**Входные данные:** MD-файл с описанием задачи/бага (например, `docs/3. Tasks/BUG_*.md`)

---

## 📋 Алгоритм анализа MD-файла

### Шаг 1: Чтение и парсинг

1. **Прочитать MD-файл с задачей/багом**
   - Найти разделы: "Описание проблемы", "Корневая причина", "Что делать дальше"
   - Обратить внимание на упоминания файлов, компонентов, функций

2. **Найти упоминания файлов**
   - Поиск путей: `TMA_functional/src/...`, `bot/src/...`
   - Поиск имен компонентов: `VideoRecording`, `useTmaWebSocket`
   - Поиск функций: `onRecordingComplete`, `handleAcceptClick`
   - Поиск API endpoints: `/api/items/...`, `/ws/tma`

3. **Определить область проблемы**
   - **Фронтенд:** упоминания `TMA_functional`, `.tsx`, `.ts`, React компоненты
   - **Бэкенд:** упоминания `bot/src`, `.py`, API endpoints
   - **Инфраструктура:** упоминания `Caddyfile`, `docker-compose.yml`, WebSocket, проксирование
   - **Интеграция:** упоминания и фронтенда, и бэкенда

---

### Шаг 2: Определение критичных файлов

1. **Найти все упомянутые файлы в MD**
   - Составить список файлов, явно упомянутых в описании проблемы
   - Проверить разделы "Файл:", "Что проверить:", "Действия:"

2. **Найти файлы, импортируемые критичными файлами**
   - Для каждого критичного файла проверить его импорты
   - Найти зависимости: hooks, API clients, types, contexts, components

3. **Определить зависимости**
   - **Hooks:** `use-tma-websocket.ts`, `use-video-recorder.tsx`
   - **API clients:** `api-client.ts`, `area-api-client.ts`, `api.ts`
   - **Types:** `area-types.ts`, `video-types.ts`
   - **Contexts:** `cleaning-session-context.tsx`, `launch-context.tsx`
   - **Components:** `VideoPreview.tsx`, `ErrorBoundary.tsx`

4. **Проверить упоминания инфраструктуры**
   - Если упоминается **WebSocket** → проверить `Caddyfile`, `bot/src/api/routers/websocket.py`
   - Если упоминается **проксирование** → проверить `Caddyfile`, `docker-compose.yml`
   - Если упоминается **роутинг** → проверить `Caddyfile`

---

### Шаг 3: Исключение ненужного

**Чеклист исключений (с исключениями):**

#### ❌ Конфигурационные файлы (обычно исключаем)
- `eslint.config.js`, `postcss.config.js`, `tailwind.config.ts`
- `tsconfig.*.json`, `vite.config.ts`
- `package.json`, `package-lock.json`, `bun.lockb`
- `Dockerfile`, `Dockerfile.dev`, `nginx.conf`
- `components.json`, `index.html`

**⚠️ ИСКЛЮЧЕНИЕ:** Следующие файлы могут быть критичны:
- **`Caddyfile`** — если проблема с проксированием, WebSocket upgrade, роутингом
- **`docker-compose.yml`** — если проблема с конфигурацией сервисов, портами, volumes, ngrok

#### ❌ Документация
- `README.md`, `CHANGELOG.md`, `HANDOFF.md`
- `docs/` (вся папка)
- Комментарии в коде не критичны, но сам код нужен

#### ❌ Сгенерированные файлы
- `node_modules/`, `dist/`, `.venv/`, `__pycache__/`
- `*.db`, `*.log`, `*.lockb`

#### ❌ Другие страницы/компоненты
- Если баг в `VideoRecording.tsx`, не нужны: `Index.tsx`, `NotFound.tsx`, `AreaIntro.tsx` и т.д.
- Если баг в конкретном компоненте, не нужны другие компоненты из `components/ui/`
- Исключение: компоненты, явно используемые проблемным файлом

#### ❌ TMA_layout
- Если баг в `TMA_functional`, папка `TMA_layout/` не нужна (это только верстка)

#### ❌ bot/ (если проблема только во фронтенде)
- Если баг только в `TMA_functional`, папка `bot/` не нужна
- Исключение: если упоминаются API endpoints или WebSocket

#### ❌ scripts/
- Папка `scripts/` обычно не связана с багами в коде
- Исключение: если баг связан с миграциями БД или скриптами инициализации

#### ❌ shared/
- Папка `shared/types/` обычно не используется в `TMA_functional`
- Проверить: есть ли импорты из `shared/` в критичных файлах

---

### Шаг 4: Формирование дерева файлов

1. **Создать структуру папок/файлов для включения**
   - Указать полные пути относительно корня проекта
   - Группировать по категориям: pages, hooks, lib, components, infrastructure

2. **Формат дерева:**
```
TMA_functional/
  src/
    pages/
      VideoRecording.tsx
    hooks/
      use-tma-websocket.ts
      use-video-recorder.tsx
    lib/
      api-client.ts
      area-api-client.ts
      area-types.ts
      cleaning-session-context.tsx
      launch-context.tsx
      logger.ts
      video-types.ts
    components/
      VideoPreview.tsx
      ErrorBoundary.tsx
```

3. **Проверить размер**
   - Оценить количество файлов
   - Целевой расход: ~180k токенов или меньше

---

## 📚 Шаблоны для типичных случаев

### Случай 1: Баг во фронтенде (TMA_functional)

**Пример:** Баг с кнопками в `VideoRecording.tsx`

**Включить:**
- `TMA_functional/src/pages/VideoRecording.tsx` — проблемная страница
- `TMA_functional/src/hooks/use-video-recorder.tsx` — хук записи видео
- `TMA_functional/src/hooks/use-tma-websocket.ts` — если используется WebSocket
- `TMA_functional/src/lib/api-client.ts` — если используется API
- `TMA_functional/src/lib/area-api-client.ts` — если используется API зон
- `TMA_functional/src/lib/area-types.ts` — типы данных
- `TMA_functional/src/lib/cleaning-session-context.tsx` — если используется контекст
- `TMA_functional/src/lib/launch-context.tsx` — если используется контекст
- `TMA_functional/src/lib/logger.ts` — если используется логирование
- `TMA_functional/src/lib/video-types.ts` — типы видео
- `TMA_functional/src/components/VideoPreview.tsx` — если используется компонент
- `TMA_functional/src/components/ErrorBoundary.tsx` — если используется компонент

**Исключить:**
- `bot/` — бэкенд не нужен
- `scripts/` — скрипты не связаны
- `TMA_layout/` — только верстка
- `shared/` — не используется
- Конфигурационные файлы (eslint, postcss, tailwind, tsconfig, vite.config, package.json, Dockerfile, nginx.conf)
- Другие страницы (`Index.tsx`, `NotFound.tsx`, `AreaIntro.tsx` и т.д.)
- Другие компоненты из `components/ui/`

---

### Случай 2: Баг в бэкенде (bot/)

**Пример:** Ошибка в API endpoint `/api/items/upload_video`

**Включить:**
- `bot/src/api/routers/items.py` — роутер с проблемным endpoint
- `bot/src/tma_api.py` — если используется основной API модуль
- `bot/src/database.py` — если затронуты модели БД
- `bot/src/services/...` — если используются сервисы (openai_manager, dropbox_manager и т.д.)

**Исключить:**
- `TMA_functional/` — фронтенд не нужен
- `scripts/` — скрипты не связаны
- `docs/` — документация не нужна
- Конфигурационные файлы (Dockerfile, requirements.txt и т.д.)

---

### Случай 3: Баг в интеграции (фронтенд + бэкенд)

**Пример:** Проблема с загрузкой видео (фронтенд отправляет, бэкенд не принимает)

**Включить:**
- Критичные файлы из **Случая 1** (фронтенд)
- Критичные файлы из **Случая 2** (бэкенд)
- `TMA_functional/src/lib/api-client.ts` — API клиент на фронте
- `bot/src/api/routers/items.py` — API endpoint на бэкенде

**Исключить:**
- Все остальное по чеклисту из Шага 3

---

### Случай 4: Инфраструктурные проблемы (Caddy, ngrok, Docker, WebSocket)

**Пример:** WebSocket соединение не устанавливается, ошибка 101 Switching Protocols

**Включить:**
- **`Caddyfile`** — конфигурация проксирования и WebSocket upgrade
- **`docker-compose.yml`** — конфигурация сервисов, портов, volumes
- **`bot/src/api/routers/websocket.py`** — WebSocket endpoint на бэкенде
- **`TMA_functional/src/hooks/use-tma-websocket.ts`** — WebSocket хук на фронте
- **`TMA_functional/src/pages/VideoRecording.tsx`** — если используется WebSocket в компоненте

**Исключить:**
- Остальные конфигурационные файлы (eslint, postcss, tailwind, tsconfig, vite.config, package.json, Dockerfile, nginx.conf)
- Другие страницы и компоненты, не связанные с WebSocket

**Пример 2:** Проблема с проксированием через Caddy (роутинг не работает)

**Включить:**
- **`Caddyfile`** — конфигурация роутинга
- **`docker-compose.yml`** — конфигурация сервисов и портов
- Файлы, которые используют проблемные пути (если упоминаются в MD)

**Исключить:**
- Остальные конфигурационные файлы
- Код приложения, если проблема только в инфраструктуре

---

## 💡 Примеры использования

### Пример 1: Баг с кнопками в VideoRecording.tsx

**MD-файл упоминает:**
- `TMA_functional/src/pages/VideoRecording.tsx`
- `onRecordingComplete` делает early return
- `handleAcceptClick` не работает
- `flowState` остается в `"uploading"`

**Анализ:**
- Область: **фронтенд** (TMA_functional)
- Критичные файлы: `VideoRecording.tsx`
- Зависимости: проверить импорты в `VideoRecording.tsx`

**Дерево файлов для включения:**
```
TMA_functional/
  src/
    pages/
      VideoRecording.tsx
    hooks/
      use-video-recorder.tsx
      use-tma-websocket.ts
    lib/
      api-client.ts
      area-api-client.ts
      area-types.ts
      cleaning-session-context.tsx
      launch-context.tsx
      logger.ts
      video-types.ts
    components/
      VideoPreview.tsx
      ErrorBoundary.tsx
```

**Исключить:**
- `bot/`, `scripts/`, `TMA_layout/`, `shared/`
- Конфигурационные файлы
- Другие страницы и компоненты

---

### Пример 2: Проблема с WebSocket соединением

**MD-файл упоминает:**
- WebSocket соединение не устанавливается
- Ошибка в Caddy при проксировании
- `useTmaWebSocket` не подключается
- `bot/src/api/routers/websocket.py` не получает запросы

**Анализ:**
- Область: **инфраструктура + фронтенд + бэкенд**
- Критичные файлы: `Caddyfile`, `use-tma-websocket.ts`, `websocket.py`

**Дерево файлов для включения:**
```
Caddyfile
docker-compose.yml
bot/
  src/
    api/
      routers/
        websocket.py
TMA_functional/
  src/
    hooks/
      use-tma-websocket.ts
    lib/
      api.ts (если используется для построения WebSocket URL)
      logger.ts (если используется логирование)
```

**Исключить:**
- Остальные конфигурационные файлы
- Другие страницы и компоненты
- Другие API роутеры

---

### Пример 3: Ошибка в API endpoint

**MD-файл упоминает:**
- `POST /api/items/upload_video` возвращает 500
- `bot/src/api/routers/items.py` — проблема в обработчике
- Используется `bot/src/database.py` для сохранения

**Анализ:**
- Область: **бэкенд**
- Критичные файлы: `items.py`, `database.py`

**Дерево файлов для включения:**
```
bot/
  src/
    api/
      routers/
        items.py
    database.py
    tma_api.py (если используется основной API модуль)
```

**Исключить:**
- `TMA_functional/`, `scripts/`, `docs/`
- Конфигурационные файлы

---

### Пример 4: Проблема с проксированием через Caddy

**MD-файл упоминает:**
- Запросы к `/tma-api/*` не доходят до бэкенда
- Caddy не проксирует правильно
- Проблема с роутингом в `Caddyfile`

**Анализ:**
- Область: **инфраструктура**
- Критичные файлы: `Caddyfile`, `docker-compose.yml`

**Дерево файлов для включения:**
```
Caddyfile
docker-compose.yml
```

**Исключить:**
- Весь код приложения
- Остальные конфигурационные файлы

---

## ✅ Чеклист финальной проверки

Перед отправкой списка файлов архитектору проверьте:

- [ ] **Все упомянутые в MD файлы включены?**
  - Проверить разделы "Файл:", "Что проверить:", "Действия:"
  - Убедиться, что все явно упомянутые файлы есть в списке

- [ ] **Все зависимости включены?**
  - Проверить импорты в критичных файлах
  - Убедиться, что hooks, API clients, types, contexts включены

- [ ] **Инфраструктурные файлы проверены?**
  - Если проблема с WebSocket → `Caddyfile` включен?
  - Если проблема с проксированием → `Caddyfile` и `docker-compose.yml` включены?
  - Если проблема с роутингом → `Caddyfile` включен?

- [ ] **Ненужные файлы исключены?**
  - Конфигурационные файлы (кроме `Caddyfile` и `docker-compose.yml` при необходимости)
  - Документация
  - Сгенерированные файлы
  - Другие страницы/компоненты, не связанные с проблемой
  - `TMA_layout/` (если баг в `TMA_functional`)
  - `bot/` (если проблема только во фронтенде)
  - `scripts/`, `shared/` (если не используются)

- [ ] **Расход токенов в пределах целевого?**
  - Оценить количество файлов
  - Целевой расход: **~180k токенов или меньше**
  - Если превышает — еще раз проверить исключения

---

## 🔍 Дополнительные советы

### Как найти зависимости файла

1. **Прочитать импорты в критичном файле:**
   ```typescript
   import { useTmaWebSocket } from "@/hooks/use-tma-websocket";
   import { uploadItemVideo } from "@/lib/api-client";
   ```
   → Включить `use-tma-websocket.ts` и `api-client.ts`

2. **Проверить использование компонентов:**
   ```typescript
   import { VideoPreview } from "@/components/VideoPreview";
   ```
   → Включить `VideoPreview.tsx`

3. **Проверить типы:**
   ```typescript
   import type { Item, ItemStatus } from "@/lib/area-types";
   ```
   → Включить `area-types.ts`

### Когда включать инфраструктурные файлы

- **WebSocket проблемы** → всегда проверять `Caddyfile` и `docker-compose.yml`
- **Проксирование не работает** → `Caddyfile` обязателен
- **Роутинг не работает** → `Caddyfile` обязателен
- **Порты не пробрасываются** → `docker-compose.yml` обязателен

### Типичные ошибки

- ❌ **Включить весь `TMA_functional/src/`** — слишком много, нужно только критичные файлы
- ❌ **Включить `bot/` при баге во фронтенде** — не нужен, если не упоминается API
- ❌ **Исключить `Caddyfile` при проблеме с WebSocket** — может быть критичен
- ❌ **Включить все компоненты из `components/ui/`** — нужны только используемые

---

## 📝 Шаблон ответа архитектору

После анализа MD-файла сформируйте ответ в таком формате:

```
На основе анализа бага [название], определены следующие критичные файлы:

**Область проблемы:** [фронтенд/бэкенд/интеграция/инфраструктура]

**Дерево файлов для включения:**

[дерево файлов в формате markdown]

**Исключено:**
- [список исключенных категорий с обоснованием]

**Оценка расхода токенов:** [примерная оценка]
```

---

**Дата создания:** 2025-01-30  
**Последнее обновление:** 2025-01-30  
**Автор:** AI Assistant




































