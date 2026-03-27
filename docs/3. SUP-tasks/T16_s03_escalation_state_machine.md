Дата: 2026-03-27
Статус: 🟡 draft
Спецификация: docs/2. SUP-specifications/S03_ai_chat_quality.md

# T16 — Стейт-машина эскалации: маршрутизация, тайм-аут, возобновление ИИ

## Customer-facing инкремент

Во время работы оператора сообщения клиента идут напрямую оператору, а не теряются в ИИ. Если оператор не ответил в течение часа — ИИ возобновляет работу сам и мягко спрашивает, как прошёл разговор.

## Цель

Реализовать полную стейт-машину эскалации: при `switcher=true` — перевести сессию в состояние `escalated=true`, маршрутизировать входящие сообщения оператору (а не ИИ), запустить watchdog-таймер на 1 час, по истечении — автоматически вернуть ИИ. Использовать 4 новые колонки в `bot_sessions`.

## Изменения в коде

- `handlers/text.py` — `_handle_authorized()`:
  - В начале проверить `session.get("escalated")`:
    - Если `True` — переслать сообщение оператору через `imconnector_svc.send_message()` и `return` (не обращаться к ИИ)
    - Если `False` — продолжить обычный флоу
  - После получения ответа от `SupportService`:
    - Если `result["switcher"] == "true"`:
      - Вызвать `imconnector_svc.send_escalation(chat_id, contact_name, text, history)`
      - Обновить сессию: `escalated=True`, `escalated_at=now()`, `bitrix_chat_id=chat_id`

- `services/supabase.py` — `update_session()`:
  - Добавить поддержку новых полей: `escalated`, `bitrix_chat_id`, `escalated_at`, `operator_last_reply_at`

- `bot.py` — watchdog-задача:
  - `async escalation_watchdog()` — фоновая корутина, просыпается каждые 5 минут
  - Запрашивает из Supabase все сессии где `escalated=true` и `escalated_at < now() - 1 hour`
  - Для каждой: обновить `escalated=false`, отправить клиенту: «Похоже, специалист пока не ответил. Я снова здесь — чем могу помочь?»

- `webhook_server.py` — обновление `operator_last_reply_at`:
  - При каждом входящем сообщении от оператора обновлять `operator_last_reply_at=now()` в Supabase

## Как протестировать

1. Авторизоваться, написать: «Верните деньги немедленно!»
2. Проверить в Supabase: `escalated=true`, `escalated_at` заполнен
3. Написать следующее сообщение — проверить: оно ушло оператору в Bitrix, ИИ не ответил
4. Оператор закрывает чат → проверить: `escalated=false`, клиент получил уведомление о возврате ИИ
5. (Для watchdog) Вручную поставить `escalated_at = now() - 2 hours` в Supabase → подождать до 5 минут → проверить: `escalated=false`, клиент получил сообщение о возврате ИИ

## Критерии приёмки

1. При `switcher=true`: `escalated=true` сохраняется в Supabase, сообщение уходит оператору
2. Пока `escalated=true`: все сообщения клиента идут оператору, ИИ не отвечает
3. После закрытия сессии оператором: `escalated=false`, ИИ возобновлён, клиент уведомлён
4. Watchdog: через 1 час без ответа оператора — автоматический возврат к ИИ с сообщением
5. `operator_last_reply_at` обновляется при каждом ответе оператора
