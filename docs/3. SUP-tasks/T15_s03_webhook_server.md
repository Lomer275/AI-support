Дата: 2026-03-27
Статус: 🟡 draft
Спецификация: docs/2. SUP-specifications/S03_ai_chat_quality.md

# T15 — Webhook-сервер: приём ответов оператора из Bitrix

## Customer-facing инкремент

Ответы оператора из Bitrix мгновенно приходят клиенту в Telegram — диалог с живым специалистом происходит прямо в боте, без необходимости переключаться в другой канал.

## Цель

Создать aiohttp-эндпоинт, принимающий POST-запросы от Bitrix Open Lines (события `ONIMCONNECTORMESSAGEADD` и `IMOPENLINES.SESSION.FINISH`). Сервер извлекает `chat_id` из поля `connector_mid`, форматирует текст (очищает BB-коды Bitrix) и пересылает его клиенту в Telegram. Запускается в том же процессе, что и aiogram-бот, на порту 8080.

## Изменения в коде

- `webhook_server.py` (новый файл):
  - `async handle_bitrix_webhook(request) -> web.Response`:
    - Парсить JSON тела запроса
    - Определить тип события: `ONIMCONNECTORMESSAGEADD` (новое сообщение) или `IMOPENLINES.SESSION.FINISH` (закрытие чата)
    - Извлечь `chat_id` из `data["connector_mid"]` или `data["chat"]["id"]`
    - Очистить BB-коды: `[b]...[/b]` → `*...*`, `[br]` → `\n`, остальные теги — удалить
    - При `ONIMCONNECTORMESSAGEADD`: отправить сообщение клиенту через `bot.send_message(chat_id, text)`
    - При `IMOPENLINES.SESSION.FINISH`: обновить `escalated=false` в Supabase, отправить клиенту «ИИ-ассистент снова готов помочь»
    - Вернуть `200 OK`
  - `create_webhook_app(bot, supabase) -> web.Application` — фабрика приложения

- `bot.py`:
  - После старта aiogram-поллинга запустить aiohttp-сервер на `WEBHOOK_PORT` (8080) в том же event loop
  - Передать `bot` и `supabase` в `create_webhook_app()`

## Как протестировать

1. Убедиться, что nginx проксирует `https://dev.express-bankrot.ru/webhook/bitrix/` → `localhost:8080`
2. Эскалировать диалог (T14): оператор должен видеть обращение в Bitrix
3. Оператор отвечает в Bitrix Open Lines
4. Проверить: клиент получил сообщение в Telegram
5. Оператор закрывает чат в Bitrix
6. Проверить: клиент получил «ИИ-ассистент снова готов помочь»; `escalated=false` в Supabase

## Критерии приёмки

1. Эндпоинт `POST /webhook/bitrix/` возвращает 200 при валидном запросе от Bitrix
2. Текст с BB-кодами корректно очищается перед отправкой в Telegram
3. Ответ оператора доставляется клиенту в Telegram в течение 2 секунд
4. При закрытии сессии оператором: `escalated=false` в Supabase, клиент уведомлён
5. При невалидном теле запроса — 200 (не даём Bitrix повторять запрос)
