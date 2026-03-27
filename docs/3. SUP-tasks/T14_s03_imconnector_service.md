Дата: 2026-03-27
Статус: 🟡 draft
Спецификация: docs/2. SUP-specifications/S03_ai_chat_quality.md

# T14 — ImConnectorService: отправка сообщения оператору в Bitrix

## Customer-facing инкремент

Когда ИИ решает, что нужен живой специалист (`switcher=true`), сообщение клиента вместе с историей диалога автоматически появляется у оператора в Bitrix Open Lines — оператору не нужно искать контекст вручную.

## Цель

Создать `ImConnectorService` — сервис для отправки сообщений в Bitrix Open Lines через OAuth (метод `imconnector.send.messages`). Сервис должен автоматически обновлять access_token при истечении, передавать историю диалога при первом обращении и логировать ошибки без падения бота.

## Изменения в коде

- `services/imconnector.py` (новый файл):
  - Класс `ImConnectorService.__init__(session, bitrix_url, client_id, client_secret, access_token, refresh_token, openline_id, connector_id)`
  - `async _refresh_token() -> bool` — обновить access_token через `oauth.bitrix24.tech`, вернуть `True` при успехе
  - `async _call(method, params) -> dict` — POST к Bitrix REST с Bearer-токеном, при `expired_token` — вызвать `_refresh_token()` и повторить один раз
  - `async send_message(chat_id: int, user_name: str, text: str) -> bool`:
    - Отправить сообщение через `imconnector.send.messages`
    - `connector_id = BITRIX_CONNECTOR_ID`, `line = BITRIX_OPENLINE_ID`
    - `chat.id = str(chat_id)` — ключ маршрутизации ответов обратно в Telegram
    - Вернуть `True` при успехе, `False` при ошибке
  - `async send_escalation(chat_id: int, user_name: str, trigger_text: str, history: list[dict]) -> bool`:
    - Формировать стартовое сообщение: имя клиента + Telegram chat_id + последние сообщения истории + вопрос-триггер
    - Вызывать `send_message()` с этим текстом

- `bot.py`:
  - Инициализировать `ImConnectorService` и добавить в `dp["imconnector_svc"]`

- `config.py`:
  - Добавить поля: `bitrix_url`, `bitrix_openline_id`, `bitrix_connector_id`, `bitrix_oauth_client_id`, `bitrix_oauth_client_secret`, `bitrix_oauth_access_token`, `bitrix_oauth_refresh_token`

## Как протестировать

1. Запустить бота локально / на VPS
2. Авторизоваться и отправить: «Хочу поговорить с менеджером»
3. Проверить в логах: `ImConnectorService.send_escalation called`
4. Открыть Bitrix → Открытые линии → ai_support → проверить, что появилось обращение с историей
5. Проверить: `chat_id` клиента присутствует в сообщении оператору

## Критерии приёмки

1. `ImConnectorService` инициализируется без ошибок
2. При истёкшем access_token — автоматически обновляется через refresh_token
3. `send_escalation()` создаёт обращение в Bitrix Open Lines с историей диалога
4. При ошибке Bitrix — логирует предупреждение, возвращает `False`, бот не падает
5. В Bitrix видно новое обращение от клиента с его именем и Telegram chat_id
