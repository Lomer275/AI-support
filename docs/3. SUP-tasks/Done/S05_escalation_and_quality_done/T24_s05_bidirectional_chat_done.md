Дата: 2026-04-03
Статус: ✅ accepted 2026-04-03
Спецификация: docs/2. SUP-specifications/S05_escalation_and_quality.md

# T24_s05_bidirectional_chat — Диагностика и фикс двусторонней переписки Bitrix ↔ Telegram

## Customer-facing инкремент

Оператор пишет ответ в Bitrix Open Lines → клиент мгновенно получает его в Telegram. Клиент пишет в Telegram в статусе эскалации → оператор видит сообщение в Bitrix.

## Цель

Диагностировать и починить оба направления переписки. Код реализации существует в обоих направлениях — задача найти и устранить причину некорректной работы.

## Контекст

**Telegram → Bitrix:** `handlers/text.py:150-153` — при `session.get("escalated")` сообщение пересылается через `imconnector_svc.send_message()`. Код есть, не работает.

**Bitrix → Telegram:** `webhook_server.py` обрабатывает `ONIMCONNECTORMESSAGEADD`, парсит `data[MESSAGES][0][chat][id]` как Telegram `chat_id`, вызывает `bot.send_message(chat_id, text)`. Код есть, не работает.

## Scope

**Диагностика Telegram → Bitrix:**
- Добавить подробное логирование в `imconnector_svc.send_message()`: логировать полный payload запроса и ответ Bitrix API
- Проверить: корректно ли формируется `chat.id` в payload `imconnector.send.messages`
- Проверить: создаётся ли сессия в Bitrix Open Lines при первом сообщении через коннектор
- Проверить значения `BITRIX_CONNECTOR_ID` и `BITRIX_OPENLINE_ID` в `.env`

**Диагностика Bitrix → Telegram:**
- Убедиться что Bitrix шлёт вебхуки на `http://89.223.125.143:8080/webhook/bitrix/` при ответе оператора
- Временно логировать полный raw payload входящего вебхука `ONIMCONNECTORMESSAGEADD`
- Проверить: совпадает ли `data[MESSAGES][0][chat][id]` из вебхука с Telegram `chat_id` клиента
- Проверить: не фильтруется ли вебхук по `connector` — убедиться что connector в вебхуке совпадает с `BITRIX_CONNECTOR_ID`

**Фикс:**
- Устранить найденные расхождения в payload / маппинге IDs / настройках коннектора
- Убрать временные debug-логи после подтверждения работоспособности

## Out of scope

- Перевод на ответственного сделки — T25
- Изменение промптов агентов

## Технические детали

**Текущий флоу Telegram → Bitrix** (`text.py:150-153`):
```python
if session.get("escalated"):
    await imconnector_svc.send_message(chat_id, contact_name, text)
    return
```

`send_message` отправляет `imconnector.send.messages` с `chat.id = str(chat_id)`. Именно этот ID Bitrix должен использовать для маршрутизации в чат.

**Текущий флоу Bitrix → Telegram** (`webhook_server.py:_handle_message`):
```python
chat_id = int(post.get("data[MESSAGES][0][chat][id]"))
await bot.send_message(chat_id, text)
```

Если Bitrix отдаёт другой ID в этом поле (например, внутренний Bitrix chat ID, а не Telegram chat_id) — сообщение улетит не туда или упадёт с ошибкой.

## Как протестировать

### 1. Telegram → Bitrix

1. Авторизоваться, довести до эскалации (`escalated=True` в `bot_sessions`)
2. Написать тестовое сообщение в Telegram
3. Проверить логи: `send_message` вызван, Bitrix вернул успех
4. Проверить в Bitrix Open Lines: сообщение появилось в чате

### 2. Bitrix → Telegram

1. Оператор пишет ответ в Bitrix Open Lines
2. Проверить логи `webhook_server.py`: `ONIMCONNECTORMESSAGEADD` получен, `chat_id` распарсен
3. Проверить в Telegram: клиент получил сообщение

### 3. Полный цикл

1. Клиент пишет → появляется у оператора в Bitrix
2. Оператор отвечает → появляется у клиента в Telegram
3. Нет дублей, нет потерь

## Критерии приёмки

1. Сообщение клиента из Telegram доходит до оператора в Bitrix Open Lines
2. Ответ оператора из Bitrix доходит клиенту в Telegram
3. В логах нет ошибок при обработке вебхука и при вызове `send_message`
4. `chat_id` корректно маппится в обоих направлениях

## Правила завершения задачи

**После акцепта AI выполняет автоматически:**

1. Статус → `✅ accepted`, добавить дату завершения
2. Переместить: → `docs/3. SUP-tasks/Done/S05_escalation_and_quality_done/T24_s05_bidirectional_chat_done.md`
3. Обновить S05: статус T24 → `✅ done`
4. Обновить SUP-HANDOFF
