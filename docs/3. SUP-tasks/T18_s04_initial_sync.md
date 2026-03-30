Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

# T18_s04_initial_sync — Начальная синхронизация ~1000 сделок из Bitrix

## Customer-facing инкремент

ИИ-агент видит профиль любого из ~1000 активных клиентов в базе — данные загружены из Bitrix без ручного ввода.

## Цель

Создать одноразовый скрипт `scripts/sync_bitrix_to_cases.py`, который выгружает все активные сделки из Bitrix24 и заполняет таблицы `cases`, `property`, `debts`, `documents` (метаданные чеклиста), `communications` (комментарии МС).

## Scope

- Новый файл `scripts/sync_bitrix_to_cases.py`
- Тянуть активные сделки: `CATEGORY_ID=4`, `STAGE_SEMANTIC_ID=P`
- Для каждой сделки — batch-запрос: сделка + контакт + задача чеклиста
- Незаполненные поля Bitrix → `NULL` (не ошибка, не прерывать скрипт)
- Rate limit Bitrix: пауза между batch-запросами (~0.5 сек), всего ~25 мин
- Идемпотентность: повторный запуск → `upsert` по `inn`, не дубли
- Логировать прогресс: `Обработано X/1000 сделок`
- Логировать пропущенные сделки (нет ИНН, нет контакта) в отдельный список

## Out of scope

- Загрузка физических файлов из папок Bitrix (это T20)
- Синхронизация в реальном времени (это T19)
- Переписки из Open Lines (пока только комментарии сделки)

## Технические детали

Переиспользует `BitrixService` из `services/bitrix.py`.

Маппинг полей Bitrix → `cases`:
```python
cases.inn              ← UF_CRM_1751273997835
cases.deal_id          ← deal['ID']
cases.stage            ← deal['STAGE_ID']
cases.full_name        ← contact['NAME'] + contact['LAST_NAME']
cases.phone            ← contact['PHONE'][0]['VALUE']
cases.total_debt_amount ← UF_CRM_1614679272145
cases.creditors_count  ← UF_CRM_1575950599001
cases.contract_number  ← UF_CRM_1577191308
cases.arbitration_manager ← UF_CRM_1607524042544
cases.folder_url       ← UF_CRM_1601916846
# ... (полный маппинг по спеке S04)
```

## Как протестировать

1. Запустить на 5 сделках: `python scripts/sync_bitrix_to_cases.py --limit 5`
2. Проверить в Supabase что 5 строк в `cases` заполнены корректно
3. Проверить что у сделок без ИНН в логах есть запись "пропущено"
4. Запустить повторно с теми же 5 — убедиться что строк по-прежнему 5 (upsert, не дубли)
5. Запустить полный прогон: `python scripts/sync_bitrix_to_cases.py`
6. Проверить итоговый счётчик в логах

## Критерии приёмки

1. Скрипт завершается без необработанных исключений на всех ~1000 сделках
2. Незаполненные поля Bitrix сохраняются как `NULL`, не вызывают ошибок
3. Повторный запуск не создаёт дублей (upsert по `inn`)
4. `synced_at` проставлен у всех записей
5. Сделки без ИНН логируются и пропускаются без падения скрипта
6. Итоговый лог содержит: обработано / пропущено / ошибки

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T17
