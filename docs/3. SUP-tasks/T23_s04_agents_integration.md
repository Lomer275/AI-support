Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

# T23_s04_agents_integration — Интеграция ElectronicCaseService в агентский пайплайн

## Customer-facing инкремент

Алина отвечает на вопросы "когда моё заседание?", "кто мой управляющий?", "какие документы ещё нужны?" — точными данными из электронного дела, без галлюцинаций.

## Цель

Заменить `BitrixService.get_deal_profile()` в `SupportService` на `ElectronicCaseService.get_case_context()`. Инжектировать контекст электронного дела во все промпты R1/R2/Coordinator.

## Scope

- В `services/support.py`:
  - Заменить вызов `bitrix_svc.get_deal_profile()` на `electronic_case_svc.get_case_context(inn)`
  - Передавать `case_context` в промпты всех R1-агентов (lawyer, sales, manager), R2-агентов и Coordinator
  - Если `get_case_context()` вернул `None` — использовать `bitrix_svc.get_deal_profile()` как fallback
- Обновить промпты агентов: заменить секцию `[ПРОФИЛЬ КЛИЕНТА ИЗ BITRIX]` на `[ЭЛЕКТРОННОЕ ДЕЛО КЛИЕНТА]`
- Убрать вызов `bitrix_svc.get_deal_profile()` из основного пути (оставить только как fallback)
- Логировать источник контекста: `[CONTEXT] source=electronic_case` или `source=bitrix_fallback`

## Out of scope

- Удаление `BitrixService` из проекта (он нужен для T19 и T18)
- Изменение структуры пайплайна R1 → R2 → Coordinator
- Изменение логики эскалации

## Технические детали

```python
# services/support.py — в методе answer()
case_context = await self.electronic_case_svc.get_case_context(inn)
if case_context is None:
    logger.warning(f"[CONTEXT] source=bitrix_fallback inn={inn}")
    case_context = await self.bitrix_svc.get_deal_profile(deal_id)
else:
    logger.info(f"[CONTEXT] source=electronic_case inn={inn}")

# Передать case_context во все агенты вместо deal_profile
```

## Как протестировать

1. Авторизоваться в боте как реальный клиент
2. Спросить: "Когда моё заседание?" — ответ должен содержать точную дату из `first_hearing_date`
3. Спросить: "Кто мой арбитражный управляющий?" — точное ФИО из `arbitration_manager`
4. Спросить: "Какие документы мне ещё нужны?" — конкретный список ❌ из чеклиста
5. Спросить: "Сколько я уже заплатил?" — сумма из `paid_to_date`
6. Проверить логи: `source=electronic_case` (не `bitrix_fallback`)
7. Регресс: отключить `electronic_case` (передать `None`) — убедиться что fallback на Bitrix работает

## Критерии приёмки

1. Агенты используют данные из `ElectronicCaseService`, не из `BitrixService.get_deal_profile()`
2. Ответ на "когда заседание?" содержит точную дату из базы
3. Ответ на "какие документы нужны?" содержит конкретный список ❌, не общий
4. При `NULL` полях агент пишет "[не заполнено в CRM]", не галлюцинирует
5. Fallback на Bitrix работает если `electronic_case` недоступен
6. Логи содержат `source=electronic_case` для реальных клиентов

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T22
