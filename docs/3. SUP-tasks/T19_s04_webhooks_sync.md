Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

# T19_s04_webhooks_sync — Постоянная синхронизация через вебхуки Bitrix

## Customer-facing инкремент

ИИ-агент всегда видит актуальную стадию дела клиента — смена стадии в Bitrix отражается в базе в течение нескольких секунд.

## Цель

Расширить существующий `webhook_server.py` обработчиком события `onCrmDealUpdate` от Bitrix. При изменении сделки — обновлять соответствующие поля в `electronic_case`.

## Scope

- Добавить обработчик `onCrmDealUpdate` в `webhook_server.py`
- Обновлять `cases`: `stage`, `stage_updated_at` и все поля которые могли измениться
- При получении нового файла в сделке — создавать запись в `documents` со статусом `pending` и запускать `DocumentValidator` (T20)
- При новом комментарии в сделке — добавлять запись в `communications`
- Идемпотентность: повторный вебхук с теми же данными не создаёт дублей (проверка по `bitrix_id`)
- Логировать каждое обновление: `[WEBHOOK] deal_id=123, field=STAGE_ID, value=...`

## Out of scope

- Обработка событий закрытия/удаления сделок
- Синхронизация `property` и `debts` по вебхукам (только при начальной синхронизации T18; эти данные меняются редко)
- Вебхуки от других сущностей Bitrix (контакты, задачи)

## Технические детали

Переиспользует существующий `webhook_server.py` (aiohttp, порт 8080). Уже обрабатывает `ONIMCONNECTORMESSAGEADD` и `IMOPENLINES.SESSION.FINISH` — добавляем новый роут или расширяем существующий обработчик.

```python
# webhook_server.py — новый обработчик
async def handle_crm_deal_update(data: dict):
    deal_id = data.get('data', {}).get('FIELDS', {}).get('ID')
    if not deal_id:
        return
    # Получить inn по deal_id из cases
    # Обновить изменившиеся поля через upsert
    # Если новый файл → запустить document_validator
    # Если новый комментарий → добавить в communications
```

Нужно зарегистрировать вебхук в Bitrix24 (через UI или REST API):
- Событие: `ONCRMDEALADD`, `ONCRMDEALUPDATE`
- URL: `http://89.223.125.143:8080/bitrix/crm-deal-update`

## Как протестировать

1. Зарегистрировать вебхук в Bitrix (тестовый)
2. Вручную изменить стадию любой сделки в Bitrix
3. Проверить в логах: событие получено, поле обновлено
4. Проверить в Supabase: `cases.stage` и `stage_updated_at` обновились
5. Отправить дублирующий вебхук вручную — убедиться что дублей в `communications` нет
6. Проверить что существующие обработчики (`ONIMCONNECTORMESSAGEADD` и `IMOPENLINES.SESSION.FINISH`) не сломались

## Критерии приёмки

1. Смена стадии сделки в Bitrix → `cases.stage` обновляется в течение 10 секунд
2. Дублирующие вебхуки не создают дублей в `communications`
3. Новый файл в сделке → запись в `documents` со статусом `pending`
4. Существующие вебхук-обработчики (Open Lines) работают без регрессии
5. Все события логируются с `deal_id` и изменившимся полем

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T17
