Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

**Статус:** ✅ Выполнено
**Дата закрытия:** 2026-04-01

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
# handlers/text.py — в _handle_authorized()
case_context = ""
if electronic_case_svc and inn:
    try:
        case_context = await electronic_case_svc.get_case_context(inn) or ""
        if case_context:
            logger.info("[CONTEXT] source=electronic_case inn=%s", inn)
    except Exception:
        logger.exception("[CONTEXT] electronic_case failed for inn=%s", inn)
if not case_context and deal_id:
    try:
        case_context = await bitrix.get_deal_profile(deal_id) or ""
        if case_context:
            logger.warning("[CONTEXT] source=bitrix_fallback inn=%s deal_id=%s", inn, deal_id)
    except Exception:
        logger.exception("get_deal_profile fallback failed for deal_id=%s", deal_id)

ai_text, switcher, escalation_type = await support_svc.answer(
    chat_id, inn, text, contact_name, case_context
)
```

Контекст передаётся через `case_context` в `support_svc.answer()`. `_build_client_card()` обновлён для парсинга формата `[ЭЛЕКТРОННОЕ ДЕЛО КЛИЕНТА]`.

## Как протестировать

1. Авторизоваться в боте как реальный клиент
2. Спросить: "Когда моё заседание?" — ответ должен содержать точную дату из `first_hearing_date`
3. Спросить: "Кто мой арбитражный управляющий?" — точное ФИО из `arbitration_manager`
4. Спросить: "Какие документы мне ещё нужны?" — конкретный список ❌ из чеклиста
5. Спросить: "Сколько я уже заплатил?" — сумма из `paid_to_date`
6. Проверить логи: `source=electronic_case` (не `bitrix_fallback`)
7. Регресс: отключить `electronic_case` (передать `None`) — убедиться что fallback на Bitrix работает

## Критерии приёмки

1. ✅ Агенты используют данные из `ElectronicCaseService`, не из `BitrixService.get_deal_profile()`
2. ✅ `get_case_context('365101031875')` возвращает 821-символьный контекстный блок
3. ✅ Логи содержат `source=electronic_case` для реальных клиентов
4. ✅ Fallback на Bitrix работает если `electronic_case` недоступен
5. ✅ `_build_client_card()` парсит новый формат `[ЭЛЕКТРОННОЕ ДЕЛО КЛИЕНТА]`

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T22
