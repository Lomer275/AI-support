Дата: 2026-04-03
Статус: draft
Спецификация: docs/2. GRISH-specifications/S01_demo_case_status_bot.md

# T04_s01_case_status — Интент case_status и кеш контекста

## Customer-facing инкремент

Клиент спрашивает «Что с моим делом?» — получает структурированную сводку: стадия, суд, документы, финансы. Данные дела загружаются один раз и кешируются на всю сессию.

## Цель

Реализовать ветку `case_status` в `text.py`: кеш `case_context`, поток при `case_context = None`, передачу данных в `AlevtinaService`.

## Контекст

T02 (авторизация) и T03 (AlevtinaService) готовы. `text.py` имеет заглушку для `authorized`-состояния. `ElectronicCaseService.get_case_context(inn)` уже существует в корневом `services/electronic_case.py`. `DemoSupabaseService.update_context()` готов из T01.

## Scope

- `demo_bot/handlers/text.py` — ветка `state == 'authorized'`:
  1. Прочитать `case_context` из `session["context_data"].get("case_context")`
  2. Если `None`:
     - Вызвать `await electronic_case_svc.get_case_context(inn)`
     - Если снова `None`: отправить `CASE_NOT_FOUND_MSG`, вернуть
     - Иначе: `await demo_supabase.update_context(chat_id, case_context=case_context)`
  3. Вызвать `await alevtina_svc.handle(text, history, case_context)`
  4. Если `result["intent"] == "case_status"`: отправить `result["answer"]` с `ParseMode.HTML`

- `demo_bot/bot.py` — инициализация `ElectronicCaseService` и инжекция в `workflow_data["electronic_case"]`

## Out of scope

- Интенты `next_steps`, `greeting`, `gratitude`, `off_topic` — T05, T07
- Запись истории в `context_data` — T06
- Содержание промпта для `case_status` — за это отвечает T03 (AlevtinaService) и T08 (тюнинг)

## Технические детали

**Поток case_context в text.py:**
```python
# authorized branch
inn = session["inn"]
chat_id = message.chat.id
context_data = session.get("context_data", {})
history = context_data.get("history", [])

case_context = context_data.get("case_context")
if case_context is None:
    case_context = await electronic_case_svc.get_case_context(inn)
    if case_context is None:
        await message.answer(CASE_NOT_FOUND_MSG)
        return
    await demo_supabase.update_context(chat_id, case_context=case_context)

result = await alevtina_svc.handle(message.text, history, case_context)

if result["intent"] == "case_status":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)
# другие интенты — T05, T07
```

**ElectronicCaseService** — импортируется из корня: `from services.electronic_case import ElectronicCaseService`. Инициализируется в `bot.py` с тем же Supabase-клиентом для `electronic_case` проекта (переменные `SUPABASE_CASES_URL`, `SUPABASE_CASES_ANON_KEY`).

**update_context** обновляет только `case_context` в JSONB, не трогает `history`. Реализован в T01.

**ParseMode.HTML** — из `aiogram.enums`. Ответ GPT должен использовать `<b>` для заголовков секций.

## Как протестировать

### 1. Первый запрос — загрузка и кеш

1. Авторизоваться за клиента с заполненным делом в `electronic_case`
2. Написать «Что с моим делом?»
3. Проверить:
   - Получен ответ с данными дела (стадия, суд)
   - В `demo_bot_sessions.context_data` появился ключ `case_context`
   - Ответ содержит `<b>` теги (HTML)

### 2. Повторный запрос — из кеша

1. Написать «Что сейчас происходит?» (второй раз)
2. Проверить в логах: `electronic_case_svc.get_case_context()` НЕ вызывался повторно

### 3. Дело не найдено в electronic_case

1. Авторизоваться за клиента, которого нет в `electronic_case`
2. Написать любое сообщение
3. Проверить: получен `CASE_NOT_FOUND_MSG`, бот не упал

## Критерии приёмки

1. После первого сообщения `case_context` сохранён в `context_data` в Supabase
2. Второй запрос не делает запрос к `electronic_case` Supabase
3. Ответ на `case_status` содержит реальные данные дела, отправлен с `ParseMode.HTML`
4. При отсутствии дела в `electronic_case` — `CASE_NOT_FOUND_MSG` без краша
5. `context_data["history"]` не затирается при обновлении `case_context`

## Правила завершения задачи

**После акцепта задачи AI выполняет автоматически:**

1. **Обновить файл задачи:**
   - Статус → `✅ accepted`
   - Добавить дату завершения

2. **Переместить файл:**
   - Из: `docs/3. GRISH-tasks/S01_demo_case_status_bot/T04_s01_case_status.md`
   - В: `docs/3. GRISH-tasks/Done/S01_demo_case_status_bot_done/T04_s01_case_status_done.md`

3. **Обновить спецификацию:**
   - Статус T04 → `✅ done`

4. **Обновить GRISH-HANDOFF.md:**
   - Отметить T04 как выполненную
