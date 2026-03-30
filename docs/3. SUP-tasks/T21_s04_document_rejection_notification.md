Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

# T21_s04_document_rejection_notification — Уведомление клиента об отклонении документа

## Customer-facing инкремент

Клиент получает сообщение в Telegram с объяснением почему документ не принят и что нужно сделать — без звонка МС.

## Цель

При отклонении документа модулем T20 автоматически отправлять клиенту сообщение в Telegram с причиной отклонения и инструкцией.

## Scope

- Добавить вызов уведомления в `DocumentValidator` после установки статуса `rejected`
- Сообщение отправляется через существующий `bot` (aiogram) по `chat_id` из `cases`
- Два шаблона сообщений:
  - `wrong_type`: "Документ '[название]' не подходит — мы ожидали {expected_type}. Загрузите нужный документ."
  - `unreadable`: "Документ '[название]' нечитаем — плохое качество фото или скан. Переснимите и загрузите заново."
- Если `chat_id` не найден в `cases` — только логировать, не падать

## Out of scope

- Уведомления об успешной проверке (`verified`) — избыточно
- Повторные напоминания через время (это S05)
- Отправка уведомлений МС в Bitrix

## Технические детали

```python
# в document_validator.py
async def _notify_client(self, inn: str, file_name: str, reason: str, expected_type: str):
    case = await self.cases_service.get_by_inn(inn)
    if not case or not case.chat_id:
        logger.warning(f"No chat_id for inn={inn}, skipping notification")
        return
    text = self._build_rejection_message(file_name, reason, expected_type)
    await self.bot.send_message(chat_id=case.chat_id, text=text)
```

Шаблоны сообщений — в `handlers/` или отдельный `templates/document_messages.py`.

## Как протестировать

1. Загрузить заведомо неверный документ в папку тестовой сделки в Bitrix
2. Убедиться что клиент (тестовый Telegram аккаунт) получил сообщение
3. Проверить текст сообщения: содержит имя файла, причину, инструкцию
4. Убедиться что для сделки без `chat_id` — только лог, не исключение

## Критерии приёмки

1. Клиент получает Telegram-сообщение при `rejected` документе
2. Сообщение содержит: имя файла, понятную причину, инструкцию что делать
3. Сообщение на русском, в стиле Алины (первое лицо)
4. Если `chat_id` не найден — логируется предупреждение, бот не падает

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T20
