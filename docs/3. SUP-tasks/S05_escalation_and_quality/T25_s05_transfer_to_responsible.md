Дата: 2026-04-03
Статус: draft
Спецификация: docs/2. SUP-specifications/S05_escalation_and_quality.md

# T25_s05_transfer_to_responsible — Перевод на ответственного сделки

## Customer-facing инкремент

После эскалации чат автоматически переводится на менеджера, закреплённого за сделкой клиента, а не падает в общую очередь Open Lines.

## Цель

Получить Bitrix chat ID после создания чата через коннектор и вызвать `imopenlines.chat.transfer` с `ASSIGNED_BY_ID` из сделки. Добавить `assigned_user_id` в маппинг сделок.

## Контекст

Текущий флоу: `switcher=true` → `send_escalation()` → Bitrix создаёт чат в общей очереди. Чат не переводится на ответственного. Проблема: Bitrix chat ID нигде не сохраняется — нужно его получить для вызова `transfer`.

⚠️ Зависит от T24: нужно рабочее соединение чтобы проверить ответы Bitrix API.

⚠️ Конфликт с T26: оба трогают `cases_mapper.py` — координировать.

## Scope

**Шаг 1 — Получить Bitrix chat ID:**
- Проверить ответ `imconnector.send.messages` — содержит ли он Bitrix chat ID
- Если да: сохранять в `bot_sessions.bitrix_chat_id` при первой отправке сообщения через коннектор
- Если нет: после отправки делать запрос `imopenlines.chat.list` с фильтром по `USER_ID=telegram_chat_id` и брать ID первого найденного чата
- Добавить метод `get_or_find_bitrix_chat_id(telegram_chat_id)` в `ImConnectorService`

**Шаг 2 — Добавить `assigned_user_id` в маппинг:**
- В `cases_mapper.py`: добавить `ASSIGNED_BY_ID` в `DEAL_SELECT` и маппинг в `build_case_row()` → поле `assigned_user_id` в `electronic_case.cases`
- Добавить колонку `assigned_user_id TEXT` в схему таблицы `cases` (SQL ALTER или в DDL)
- В `ElectronicCaseService`: добавить чтение `assigned_user_id` из `cases` (или передавать напрямую из сессии)

**Шаг 3 — Вызов transfer:**
- В `ImConnectorService` добавить метод `transfer_to_responsible(bitrix_chat_id, assigned_user_id)`:
  ```python
  await self._call("imopenlines.chat.transfer", {
      "CHAT_ID": bitrix_chat_id,
      "USER_ID": assigned_user_id,
  })
  ```
- Вызывать после успешной эскалации в `text.py` (после `send_escalation`)
- Fallback: если `assigned_user_id` пустой или transfer упал — логировать предупреждение, не падать

## Out of scope

- Изменение watchdog (60 мин)
- Уведомление ответственного в Telegram/email

## Технические детали

`ASSIGNED_BY_ID` — стандартное поле сделки Bitrix, не кастомный `UF_CRM_*`. Уже может быть доступно в существующем batch-запросе `crm.deal.get` — проверить `DEAL_SELECT` в `cases_mapper.py`.

Вызов `transfer` делать **после** `send_escalation` и `update_session(escalated=True)` в `text.py`:
```python
if switcher == "true":
    await imconnector_svc.send_escalation(chat_id, contact_name, text, history)
    await supabase.update_session(chat_id, escalated=True, ...)
    bitrix_chat_id = await imconnector_svc.get_or_find_bitrix_chat_id(chat_id)
    if bitrix_chat_id and assigned_user_id:
        await imconnector_svc.transfer_to_responsible(bitrix_chat_id, assigned_user_id)
```

## Как протестировать

### 1. Transfer работает

1. Довести диалог до эскалации (`switcher=true`)
2. Проверить в Bitrix: чат открылся у конкретного менеджера (ответственного за сделку), не в общей очереди
3. Проверить логи: `transfer_to_responsible` вызван, ответ Bitrix без ошибок

### 2. Fallback при пустом `assigned_user_id`

1. Найти сделку без ответственного в Bitrix
2. Эскалировать с неё
3. Проверить: чат создался в общей очереди, бот не упал, в логах предупреждение

## Критерии приёмки

1. После эскалации чат в Bitrix переведён на ответственного менеджера
2. `assigned_user_id` присутствует в `electronic_case.cases` и синхронизируется через webhook
3. При пустом `assigned_user_id` — graceful fallback без ошибок
4. Bitrix chat ID корректно получен и сохранён

## Правила завершения задачи

**После акцепта AI выполняет автоматически:**

1. Статус → `✅ accepted`, добавить дату завершения
2. Переместить: → `docs/3. SUP-tasks/Done/S05_escalation_and_quality_done/T25_s05_transfer_to_responsible_done.md`
3. Обновить S05: статус T25 → `✅ done`
4. Обновить SUP-HANDOFF
