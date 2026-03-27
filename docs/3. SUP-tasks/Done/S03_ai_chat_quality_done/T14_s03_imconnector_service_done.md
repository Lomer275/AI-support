Дата: 2026-03-27
Статус: ✅ done

**Статус:** ✅ Выполнено
**Дата закрытия:** 2026-03-27

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
  - Инициализирован `ImConnectorService`, добавлен в `dp["imconnector_svc"]`

- `config.py`:
  - Добавлены поля: `bitrix_url`, `bitrix_openline_id`, `bitrix_connector_id`, `bitrix_oauth_client_id`, `bitrix_oauth_client_secret`, `bitrix_oauth_access_token`, `bitrix_oauth_refresh_token`

- `scripts/test_imconnector.py`:
  - Тест-скрипт для ручной проверки `send_escalation()` без запуска бота

## Env-переменные

```
BITRIX_URL=https://bitrix.express-bankrot.ru/rest/
BITRIX_OPENLINE_ID=56
BITRIX_CONNECTOR_ID=tg_alina_support
BITRIX_OAUTH_CLIENT_ID=local.698209be2f39e1.14611442
BITRIX_OAUTH_CLIENT_SECRET=TdW7KjN7oJa7wAyRggg2MCwz8HfNE4DMxmxjA3vLSbewtLK74q
BITRIX_OAUTH_ACCESS_TOKEN=<обновляется автоматически>
BITRIX_OAUTH_REFRESH_TOKEN=<из Redis старого бота>
```

## Примечания

- OAuth-токены взяты из Redis работающего Django-бота на VPS (89.223.125.143)
- `connector_id=tg_alina_support`, `openline_id=56` — новая линия для Алины
- Токены хранятся in-memory (не Redis) — при рестарте делается один автоматический refresh
- Обнаружен и исправлен баг: конфликт имён метода `_refresh_token()` и атрибута `self._refresh_token` → переименован атрибут в `self._refresh_tok`

## Результат тестирования

- `scripts/test_imconnector.py` запущен локально
- `access_token` истёк → автообновление сработало успешно
- `send_escalation()` вернул `True`
- Обращение появилось в Bitrix → Открытые линии → tg_alina_support ✅

## Критерии приёмки

1. ✅ `ImConnectorService` инициализируется без ошибок
2. ✅ При истёкшем access_token — автоматически обновляется через refresh_token
3. ✅ `send_escalation()` создаёт обращение в Bitrix Open Lines с историей диалога
4. ✅ При ошибке Bitrix — логирует предупреждение, возвращает `False`, бот не падает
5. ✅ В Bitrix видно новое обращение от клиента с его именем и Telegram chat_id
