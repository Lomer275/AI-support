Дата: 2026-03-27
Статус: ✅ done

**Статус:** ✅ Выполнено
**Дата закрытия:** 2026-03-27

# T15 — Webhook-сервер: приём ответов оператора из Bitrix

## Customer-facing инкремент

Ответы оператора из Bitrix мгновенно приходят клиенту в Telegram — диалог с живым специалистом происходит прямо в боте, без необходимости переключаться в другой канал.

## Цель

Создать aiohttp-эндпоинт, принимающий POST-запросы от Bitrix Open Lines (события `ONIMCONNECTORMESSAGEADD` и `IMOPENLINES.SESSION.FINISH`). Сервер извлекает `chat_id` из поля `connector_mid`, форматирует текст (очищает BB-коды Bitrix) и пересылает его клиенту в Telegram. Запускается в том же процессе, что и aiogram-бот, на порту 8080.

## Изменения в коде

- `webhook_server.py` (новый файл):
  - `async handle_bitrix_webhook(request) -> web.Response` — парсит `application/x-www-form-urlencoded`, роутит по типу события
  - `ONIMCONNECTORMESSAGEADD` → очищает BB-коды → `bot.send_message()` / `send_photo()` / `send_document()`
  - `IMOPENLINES.SESSION.FINISH` → `supabase.update_session(escalated=False)` + уведомление клиенту
  - Всегда возвращает `200 OK`
  - `create_webhook_app(bot, supabase) -> web.Application` — фабрика

- `bot.py`:
  - Webhook-сервер запускается через `AppRunner` + `TCPSite` до `dp.start_polling()`, в том же event loop
  - `runner.cleanup()` в блоке `finally`

- `config.py`:
  - `WEBHOOK_PORT` (по умолчанию `8080`)

- `docker-compose.yml`:
  - `ports: - "8080:8080"` — проброс порта из контейнера

## Формат webhook от Bitrix

`application/x-www-form-urlencoded`. Ключевые поля:
- `data[MESSAGES][0][chat][id]` — Telegram chat_id (ключ маршрутизации)
- `data[MESSAGES][0][message][text]` — текст от оператора
- `data[PARAMS][CONNECTOR_MID]` — chat_id при SESSION.FINISH
- `event` — тип события

## Примечания

- Формат подтверждён из реального Django-кода на VPS (`/home/webuser/Arbitra/Handler/`)
- nginx уже настроен: `https://dev.express-bankrot.ru/webhook/bitrix/` → `localhost:8080`
- Коннектор `tg_alina_support` уже зарегистрирован в Bitrix (проверено через `imconnector.list`)

## Результат тестирования

- КП1: `POST /webhook/bitrix/` → `HTTP: 200` ✅
- КП2: BB-коды очищены — `[b]Тест T15:[/b][br]` → `Тест T15:\n` в Telegram ✅
- КП3: Доставка за `0.18s` (лимит 2s) — подтверждено через Telegram MCP ✅
- КП4: `SESSION.FINISH` — уведомление доставлено клиенту в Telegram ✅
- КП5: Невалидное тело → `200` ✅

## Критерии приёмки

1. ✅ Эндпоинт `POST /webhook/bitrix/` возвращает 200 при валидном запросе от Bitrix
2. ✅ Текст с BB-кодами корректно очищается перед отправкой в Telegram
3. ✅ Ответ оператора доставляется клиенту в Telegram в течение 2 секунд
4. ✅ При закрытии сессии оператором: `escalated=false` в Supabase, клиент уведомлён
5. ✅ При невалидном теле запроса — 200 (не даём Bitrix повторять запрос)
