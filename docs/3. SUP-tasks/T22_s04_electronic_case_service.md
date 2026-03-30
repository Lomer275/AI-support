Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

# T22_s04_electronic_case_service — Сервис ElectronicCaseService

## Customer-facing инкремент

ИИ-агент отвечает точной датой заседания, именем арбитражного управляющего и конкретным списком недостающих документов — данные берутся из единой базы одним запросом.

## Цель

Создать `services/electronic_case.py` — сервис, который читает данные из Supabase-проекта `electronic_case` и возвращает форматированный контекст для агентов. Заменяет `BitrixService.get_deal_profile()` в цепочке чата.

## Scope

- Новый файл `services/electronic_case.py`
- Метод `get_case_context(inn: str) -> str` — возвращает полный форматированный контекст для промптов агентов
- Метод `get_checklist_status(inn: str) -> str` — возвращает список документов: ✅ сдан / ❌ не сдан / ⚪ не применимо
- Один SELECT по `inn` с JOIN на `property`, `debts`, `payments`, `documents`
- `NULL` поля → явная строка `[не заполнено в CRM]` в контексте
- Инициализация сервиса в `bot.py` (аналогично другим сервисам)
- Добавить `ElectronicCaseService` в `workflow_data` через `dp`

## Out of scope

- Запись данных (только чтение)
- Кэширование (пока не нужно — один SELECT быстрый)
- Интеграция в промпты агентов (это T23)

## Технические детали

Формат контекста `get_case_context()`:
```
[ЭЛЕКТРОННОЕ ДЕЛО КЛИЕНТА]
Клиент: {full_name}
Стадия: {stage} (с {stage_updated_at})
Арбитражный управляющий: {arbitration_manager}
Регион суда: {court_region}
Дата подачи иска: {filing_actual_date}
Первое заседание: {first_hearing_date}

Долги: {total_debt_amount} ₽, кредиторов: {creditors_count}
Имущество: {property summary или "[не заполнено в CRM]"}
Ежемесячный платёж: {monthly_payment_amount} ₽
Оплачено по договору: {paid_to_date} ₽

{checklist_status}

[Не заполнено в CRM: {список NULL полей}]
```

```python
class ElectronicCaseService:
    def __init__(self, supabase_url: str, supabase_key: str): ...

    async def get_case_context(self, inn: str) -> str:
        """Форматированный контекст для агентов. None если клиент не найден."""

    async def get_checklist_status(self, inn: str) -> str:
        """✅/❌/⚪ статус документов."""
```

## Как протестировать

1. После T18: вызвать `get_case_context("123456789012")` для реального ИНН
2. Убедиться что возвращается заполненный контекст с данными из Supabase
3. Для ИНН с пустыми полями — убедиться что видно `[не заполнено в CRM]`
4. Для несуществующего ИНН — убедиться что возвращается `None`, не исключение
5. Проверить `get_checklist_status()` — ✅/❌/⚪ отображаются корректно

## Критерии приёмки

1. `get_case_context()` возвращает строку с данными клиента за один SELECT
2. `NULL` поля отображаются как `[не заполнено в CRM]`, не вызывают ошибок
3. Несуществующий ИНН → `None` (не исключение)
4. Сервис инициализируется в `bot.py` и доступен через `data["electronic_case_svc"]`
5. `get_checklist_status()` возвращает список с ✅/❌/⚪ для каждого документа

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T17, T18
