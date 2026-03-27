# Двусторонний чат: Мессенджер ↔ Bitrix24 — Архитектурный разбор

> Дата: 2026-03-26
> Источник: анализ исходного кода (bitrix/, Handler/, tg_bot/)

---

## Общая схема

```
Клиент (Telegram/MAX)
       │
       ▼
[aiogram бот] ──── tg_bot/handlers/menu/registration/support.py
       │
       ├─── AI-фаза ──────► [N8N Webhook] ─► AI-ответ
       │                          │
       │              switcher='true'? ─► Эскалация
       │
       ├─── Чат с оператором ──► [ImConnectorAPI]
       │                             │
       │                             ▼
       │                    POST /imconnector.send.messages.json
       │                    (Bitrix24 OAuth, открытая линия)
       │
       ▼
[Bitrix24 Открытые линии]
       │
       │ Оператор отвечает
       ▼
[Webhook: POST /message/] ──── Handler/views.py → message_handler()
       │
       ├─── connector = arbitrasupportbot ─► message_handler_tg()
       │         │
       │         ▼
       │    Telegram Bot API: sendMessage / sendPhoto / sendDocument
       │
       └─── connector = maxarbitrasupport ─► message_handler_max()
                 │
                 ▼
            MAX API: POST platform-api.max.ru/messages
```

---

## Направление 1: Мессенджер → Bitrix24

### Фаза 1: AI-чат (N8N)

**Точка входа:** `tg_bot/handlers/menu/registration/support.py` → `on_ai_chat_message()`

Пользователь нажимает «Поддержка» → бот переводит его в состояние `ai_chat`.

Каждое текстовое сообщение:

1. Добавляется в историю `tg_data['ai_chat_history']`
2. Бот делает `POST N8N_WEBHOOK_URL` с payload:
   ```json
   {
     "user_id": 123456789,
     "chat_id": 123456789,
     "message": "текст пользователя",
     "user_name": "Иван Иванов",
     "inn": "771234567890",
     "history": [...последние 10 сообщений...]
   }
   ```
3. N8N возвращает:
   ```json
   {
     "answer": "Текст AI-ответа",
     "switcher": "false"
   }
   ```
4. Если `switcher == 'false'` → AI отвечает в Telegram, история пополняется
5. Если `switcher == 'true'` → **эскалация к оператору**

Таймаут ожидания N8N: **120 секунд**.

---

### Фаза 2: Эскалация — отправка в Bitrix24 Open Lines

**Файл:** `bitrix/imconnector.py` → `ImConnectorAPI.send_message()`

После решения AI о переключении:

1. Форматируется история диалога:
   ```
   === ИСТОРИЯ ДИАЛОГА С AI-БОТОМ ===
   Пользователь: ...
   Бот: ...
   === КОНЕЦ ИСТОРИИ ===
   💬 Последний вопрос требует уточнения у специалиста: ...
   ```

2. Вызывается `bitrix_send()` (синхронно через `sync_to_async`):
   ```
   POST {BITRIX_URL}/imconnector.send.messages.json
   ```
   Структура запроса:
   ```json
   {
     "CONNECTOR": "arbitrasupportbot",
     "LINE":      "ID_открытой_линии",
     "MESSAGES": [{
       "user":    { "id": "123456789", "name": "Иван Иванов", "phone": "+79031234567" },
       "message": { "id": "0", "date": 1748000000, "text": "история диалога..." },
       "chat":    { "id": "123456789", "url": "" }
     }],
     "auth": "oauth_access_token"
   }
   ```
   > Ключевой момент: `chat.id` = Telegram ID пользователя. Именно по нему Bitrix потом отправит ответ обратно.

3. Из ответа извлекается `session.CHAT_ID` — внутренний ID чата в Bitrix:
   ```
   result.DATA.RESULT[0].session.CHAT_ID
   ```
   Сохраняется в `tg_data['bitrix_chat_id']`.

**OAuth-авторизация:**
ImConnector не использует webhook-токен. Он использует OAuth2 access_token, хранящийся в Redis. Автообновление — через `bitrix/oauth.py` → `refresh_tokens()`:
```
POST https://oauth.bitrix24.tech/oauth/token/
grant_type=refresh_token&client_id=...&client_secret=...&refresh_token=...
```

---

### Фаза 3: CRM-интеграция при эскалации

После успешной отправки в Bitrix выполняются три параллельных CRM-операции:

#### 3.1. CRM Активность (`crm.activity.add`)

```python
fields = {
    'OWNER_TYPE_ID': 2,                  # сделка
    'OWNER_ID': deal_id,
    'TYPE_ID': 6,
    'PROVIDER_ID': 'IMOPENLINES_SESSION',
    'SUBJECT': 'AI-чат требует помощи - Иван Иванов',
    'DESCRIPTION': '=== AI-чат требует помощи...\nИстория (последние 5 сообщений)',
    'DIRECTION': 2,                      # входящее
    'COMMUNICATIONS': [{'VALUE': phone, 'ENTITY_ID': contact_id, 'ENTITY_TYPE_ID': 3}]
}
```

#### 3.2. Переназначение чата на ответственного

**Файл:** `support.py` → `transfer_chat_to_responsible()`

Каскад из 3 попыток (используется `deal.ASSIGNED_BY_ID`):

| Попытка | Метод | Описание |
|---------|-------|----------|
| 1 | `imopenlines.operator.transfer` | Стандартный перевод (оператор в очереди) |
| 2 | `imopenlines.bot.session.transfer` | Альтернативный (без очереди, с `LEAVE: Y`) |
| 3 (fallback) | `im.notify.system.add` | IM-уведомление оператору о новом чате |

#### 3.3. Смена состояния пользователя

Бот переводит `tg_state = 'in_chat_with_operator'`.

---

### Фаза 4: Активный чат с оператором

**Файл:** `support.py` → `on_chat_message()` (State: `in_chat_with_operator`)

Каждое следующее сообщение от клиента:

```python
result = await sync_to_async(bitrix_send)(
    name=sender_name,
    chat_id=str(user.telegram_id),   # ID не меняется — Bitrix матчит по нему
    message_id=message.message_id,
    text=text,
    phone=user.phone,
    files=files or None
)
```

**Файлы** (фото/документы):
1. Скачиваются из Telegram через `bot.download(file_id)`
2. Загружаются в папку Bitrix Disk сделки (`FilesAPI.upload_to_folder()`)
3. Получается `DOWNLOAD_URL` через `disk.file.get`
4. URL передаётся в `files=[{'url': ..., 'name': ...}]` в ImConnector

---

## Направление 2: Bitrix24 → Мессенджер

### Webhook-эндпоинт

**URL:** `POST /message/`
**Файл:** `Handler/urls.py` → `Handler/views.py` → `message_handler()`

Bitrix24 Open Lines вызывает этот эндпоинт каждый раз, когда оператор отправляет сообщение в чат.

Маршрутизация по коннектору:

```python
if request.POST.get("data[CONNECTOR]") == 'maxarbitrasupport':
    message_handler_max(request)
elif request.POST.get("data[CONNECTOR]") == 'arbitrasupportbot':
    message_handler_tg(request)
```

### Парсинг входящих данных

**Файл:** `Handler/serializer.py` → `parse_bitrix_message()`

Bitrix отправляет форму (`application/x-www-form-urlencoded`):

| Поле Bitrix | Описание |
|-------------|----------|
| `data[CONNECTOR]` | ID коннектора (`arbitrasupportbot` / `maxarbitrasupport`) |
| `data[LINE]` | ID открытой линии |
| `data[MESSAGES][0][chat][id]` | **Telegram ID пользователя** (использовался как chat.id при отправке) |
| `data[MESSAGES][0][message][text]` | Текст от оператора |
| `data[MESSAGES][0][message][files][N][type]` | Тип файла: `image` / `file` |
| `data[MESSAGES][0][message][files][N][link]` | URL файла |
| `data[MESSAGES][0][message][files][N][name]` | Имя файла |
| `data[MESSAGES][0][im][chat_id]` | Внутренний chat_id Bitrix |
| `data[MESSAGES][0][im][message_id]` | Внутренний message_id Bitrix |
| `auth[access_token]` | OAuth токен для подтверждения доставки |
| `auth[client_endpoint]` | REST endpoint Bitrix для delivery status |

### Telegram-ветка (`message_handler_tg`)

1. Парсинг: извлекается `chat_id` = Telegram ID, `text`, `files[]`
2. Поиск пользователя: `User.objects.filter(telegram_id=int(chat_id))`
3. Если пользователь не в режиме чата — переключается + отправляется кнопка «Завершить диалог»
4. Отправка текста:
   ```
   POST https://api.telegram.org/bot{TG_TOKEN}/sendMessage
   {"chat_id": ..., "text": cleaned_text}
   ```
5. Отправка фото:
   ```
   POST .../sendPhoto
   {"chat_id": ..., "photo": file_url}
   ```
6. Отправка документа:
   ```
   POST .../sendDocument
   {"chat_id": ..., "document": file_url}
   ```
7. Текст очищается от BB-кодов Bitrix (`[b]`, `[i]`, `[br]`, `[url=...]`) через `clean_bb_codes()`
8. Сообщение оператора добавляется в timeline сделки (`crm.timeline.comment.add`)

### MAX-ветка (`message_handler_max`)

1. Поиск пользователя: `User.objects.get(max_user_id=int(chat_id))`
2. Отправка текста:
   ```
   POST https://platform-api.max.ru/messages?chat_id={id}
   Authorization: {MAX_TOKEN}
   {"text": cleaned_text}
   ```
   При ошибке «Unknown recipient» — повтор с `?user_id=` вместо `?chat_id=`
3. Фото и документы — отправляются как текст с URL (attachments API не реализован)
4. После успешной доставки — подтверждение в Bitrix:

### Подтверждение доставки (`send_delivery_status`)

**Файл:** `Handler/sendlers.py` → `send_delivery_status()`

Вызывается для MAX-ветки. Сообщает Bitrix24, что сообщение доставлено (галочка «прочитано»):

```
POST {auth[client_endpoint]}/imconnector.send.status.delivery.json
{
  "CONNECTOR": "maxarbitrasupport",
  "LINE": "...",
  "MESSAGES": [{
    "im": { "chat_id": im_chat_id, "message_id": im_message_id },
    "message": { "id": [im_message_id] },
    "chat": { "id": chat_id }
  }],
  "auth": access_token
}
```

---

## Модель данных User

| Поле | Назначение в чате |
|------|------------------|
| `telegram_id` | = `chat.id` в ImConnector = ключ для поиска при входящем webhook |
| `max_user_id` | = `chat.id` для MAX-коннектора |
| `max_chat_id` | Chat ID в MAX (может отличаться от user_id) |
| `contact_id` | Bitrix24 Contact ID — для CRM активности |
| `deal_id` | Bitrix24 Deal ID — для timeline и поиска ответственного |
| `tg_state` | Состояние: `start` / `ai_chat` / `in_chat_with_operator` |
| `max_state` | Аналог для MAX |
| `tg_data['bitrix_chat_id']` | Bitrix session CHAT_ID (из ответа ImConnector) |
| `tg_data['ai_chat_history']` | История AI-диалога `[{role, content}]` |
| `tg_data['deal_id']` | Кэш deal_id в сессии чата |
| `phone` | Телефон — передаётся в ImConnector для CRM-идентификации |

---

## Webhook-события от Bitrix (задачи)

**URL:** `POST /webhook/bitrix/` — `bitrix_webhook()` (заглушка)
**URL:** `POST /...` — `tasks_handler()` (реализовано)

Bitrix присылает события задач:

| Событие | Обработка |
|---------|-----------|
| `ONTASKADD` | `process_new_task(task_id)` — уведомление клиенту о новой задаче |
| `ONTASKUPDATE` | `process_task_update(task_id)` — изменение задачи |
| `ONTASKDELETE` | `process_task_delete(task_id)` — удаление задачи |

Защита от дублей: модель `WebhookEvent` + `select_for_update()` + проверка дублей за 60 сек.

---

## Итоговая цепочка: полный флоу от вопроса до ответа оператора

```
1. Клиент пишет в Telegram-боте
          │
2. Бот (State: ai_chat) → POST N8N_WEBHOOK_URL
          │
3. N8N AI → {answer, switcher}
          │
4a. switcher='false' → AI отвечает в Telegram
          │
4b. switcher='true'  → Эскалация:
          │
5. POST /imconnector.send.messages.json
   (OAuth, connector=arbitrasupportbot, chat.id=telegram_id)
          │
6. Bitrix создаёт сессию Open Lines → {session.CHAT_ID}
          │
7. crm.activity.add (привязка к сделке)
          │
8. imopenlines.operator.transfer → ответственный получает чат
          │
9. tg_state = 'in_chat_with_operator'
          │
10. Оператор пишет в Bitrix24 Open Lines
          │
11. Bitrix POST /message/ (webhook)
    data[CONNECTOR]=arbitrasupportbot
    data[MESSAGES][0][chat][id]=telegram_id
          │
12. message_handler_tg() → sendMessage/sendPhoto/sendDocument
    → Telegram Bot API
          │
13. Клиент получает ответ оператора
          │
14. Клиент продолжает писать → on_chat_message() →
    POST /imconnector.send.messages.json → обратно в Bitrix
```

---

## Конфигурация (env-переменные)

| Переменная | Назначение |
|-----------|-----------|
| `BITRIX_WEBHOOK` | Webhook URL для REST API (crm.*, tasks.*) |
| `BITRIX_URL` | Base URL портала (для ImConnector) |
| `BITRIX_CONNECTOR_ID` | ID коннектора (`arbitrasupportbot`) |
| `BITRIX_OPENLINE_ID` | ID открытой линии |
| `BITRIX_CLIENT_ID` | OAuth client_id |
| `BITRIX_CLIENT_SECRET` | OAuth client_secret |
| `BITRIX_AUTH` | OAuth endpoint URL |
| `BITRIX_CLIENT_USER_ID` | ID пользователя «Клиент» в Bitrix (60500) |
| `TG_TOKEN` | Telegram Bot API token |
| `MAX_TOKEN` | MAX Platform API token |
| `N8N_WEBHOOK_URL` | URL N8N для AI-обработки |

---

## Канал уведомлений: задачи Bitrix → Telegram (независимый от чата)

Отдельный поток: Bitrix шлёт события задач → Django обрабатывает → Telegram-уведомление клиенту.

### URL: `POST /webhook/bitrix/` (задачи)

**Файл:** `Handler/views.py` → `tasks_handler()` + `Handler/tasks.py`

#### Защита от дублей (idempotency)

```python
WebhookEvent.objects.create(event_type=event, task_id=task_id, raw_data=...)
select_for_update()  # блокировка
# Проверка: такое же событие за последние 60 сек с status=COMPLETED?
# Да → STATUS_SKIPPED
# Нет → обрабатываем
```

Модель `WebhookEvent`: статусы `pending → completed / failed / skipped`.

#### Логика `process_new_task(task_id)`

1. `tasks.task.get` → получить задачу с чеклистом
2. Проверить `responsibleId == 60500` (системный пользователь «Клиент») → иначе пропуск
3. Извлечь `deal_id` из `UF_CRM_TASK` (формат `"D_123"`)
4. `crm.deal.get` → получить `CONTACT_ID` сделки
5. `User.objects.filter(contact_id=contact_id)` → найти пользователя в БД
6. `send_task_notification_with_keyboard()` → Telegram Bot API sendMessage + inline-кнопка «Мои задачи»
7. `TaskReminder.aupdate_or_create()` → сохранить для напоминаний по дедлайну

#### `process_task_update(task_id)`

Аналогично, но если `task.status in ('5', '7')` (завершена/отклонена) → только помечает `TaskReminder.is_completed=True`, без уведомления.

#### `process_task_delete(task_id)`

Просто удаляет все `TaskReminder` с данным `task_id`. Не проверяет исполнителя (задача уже удалена из Bitrix).

#### Форматирование уведомления о задаче

```
Уважаемый клиент, у вас появилась новая задача!

{title}

Срок: 25.03.2026 14:00

Для начала выполнения задачи необходимо нажать на кнопку 'Мои задачи'...
```

Дата конвертируется из московского времени Bitrix в локальный TZ клиента (по региону из `UF_CRM_1758259616`).

---

## OAuth: жизненный цикл токенов

**Файлы:** `shared/redis/redis_storage.py`, `bitrix/oauth.py`

ImConnector требует OAuth2 access_token, а не webhook-токен. Управление:

```
Redis db=2, prefix "bitrix:"

bitrix:access_token   → TTL 1 час     (3600 сек)
bitrix:refresh_token  → TTL 180 дней  (15552000 сек)
bitrix:*              → остальные поля токена
```

**Автообновление** (`auto_refresh_if_needed()`):
1. Проверить TTL `bitrix:access_token` в Redis
2. Если TTL < 300 сек (5 минут) или ключ отсутствует → `refresh_tokens()`
3. `POST https://oauth.bitrix24.tech/oauth/token/` с `grant_type=refresh_token`
4. Retry: 3 попытки с задержкой 2 сек
5. Сохранить новые токены обратно в Redis

Вызывается перед **каждым** запросом к ImConnector в `ImConnectorAPI._get_access_token()`.

---

## Аналитика (EventLog)

**Файл:** `tg_bot/analytics.py`

Fire-and-forget логирование через `asyncio.create_task(log_event(...))`:

| Событие | Когда |
|---------|-------|
| `section_open` | Пользователь открыл раздел «Поддержка» |
| `escalation` | AI решил переключить на оператора |
| `auth_start/success/fail` | Авторизация |
| `payment_start` | Раздел оплаты |
| `doc_upload` | Загрузка документа |
| `task_done` | Клиент выполнил задачу |

Записи хранятся в `Handler_eventlog` (PostgreSQL), индексируются по `telegram_id`, `event_type`, `created_at`.

---

## Ключевые решения и ограничения

### Как Bitrix знает, куда отправить ответ?
При отправке в ImConnector `chat.id` = `user.telegram_id`. Bitrix сохраняет этот ID в сессии. Когда оператор отвечает, Bitrix шлёт webhook обратно с `data[MESSAGES][0][chat][id] = telegram_id`. Сервер находит пользователя по этому ID и отправляет сообщение в Telegram.

### Два типа авторизации
- **Webhook-токен** (`BITRIX_WEBHOOK`): для обычных REST-методов (crm, tasks)
- **OAuth** (Redis + `BITRIX_CLIENT_ID/SECRET`): только для ImConnector (Open Lines)

### BB-коды
Bitrix использует BB-форматирование в чате. Все тексты проходят через `clean_bb_codes()` перед отправкой в Telegram/MAX.

### Старая и новая логика
В коде есть закомментированная «старая логика» (до 2025-12-16): прямой чат без AI, с созданием CRM-активности при первом сообщении. Текущая «новая логика» добавляет N8N AI-прослойку с автоэскалацией.

### Ограничения текущей реализации
- MAX: фото и документы отправляются только как текст с URL (нет реального binary upload)
- TG: нет подтверждения доставки в Bitrix (`send_delivery_status` реализован только для MAX)
- `tasks_handler` (уведомления о задачах) — отдельный независимый канал, не связан с чатом
