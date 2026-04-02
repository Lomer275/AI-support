Дата: 2026-04-03
Статус: draft
Спецификация: docs/2. GRISH-specifications/S01_demo_case_status_bot.md

# T06_s01_dialog_history — История диалога

## Customer-facing инкремент

Бот помнит контекст разговора — последние 3 пары «вопрос/ответ». Клиент может сослаться на предыдущий ответ и бот поймёт.

## Цель

Реализовать запись и чтение истории диалога в `context_data["history"]`. Передавать последние 6 сообщений в каждый GPT-вызов.

## Контекст

T02 и T03 готовы. T04 уже реализует загрузку `case_context` и вызов `AlevtinaService`. T06 добавляет сохранение истории после каждого ответа. `DemoSupabaseService.update_context(chat_id, history=...)` уже готов из T01.

## Scope

- `demo_bot/handlers/text.py` — в ветке `authorized`, после получения ответа от `AlevtinaService`:
  1. Прочитать текущую `history` из `context_data.get("history", [])`
  2. Добавить пару: `{"role": "user", "content": message.text}` и `{"role": "assistant", "content": result["answer"]}`
  3. Обрезать до последних 6 сообщений: `history = history[-6:]`
  4. Сохранить: `await demo_supabase.update_context(chat_id, history=history)`

- Передача в `AlevtinaService`: `history` уже читается из `context_data` до вызова `handle()` — убедиться что передаётся актуальная history (до добавления текущего обмена)

## Out of scope

- Формат и содержание ответов — T04, T05, T07
- Кеш `case_context` — T04

## Технические детали

**Порядок операций в text.py (authorized branch):**
```python
context_data = session.get("context_data", {})
history = context_data.get("history", [])          # 1. Читаем историю ДО текущего сообщения
case_context = context_data.get("case_context")    # 2. Кеш контекста (T04)
# ... загрузка case_context если None (T04) ...

result = await alevtina_svc.handle(message.text, history, case_context)  # 3. GPT-вызов

# 4. Обработка интента (T04, T05, T07) — отправка ответа

# 5. Обновляем историю ПОСЛЕ отправки ответа
new_history = history + [
    {"role": "user", "content": message.text},
    {"role": "assistant", "content": result["answer"]},
]
await demo_supabase.update_context(chat_id, history=new_history[-6:])
```

Для `fallback`-интента история тоже обновляется (записываем что бот ответил фоллбэком).

**update_context** обновляет только ключ `history` в JSONB, не трогает `case_context`. Реализован в T01.

Лимит: 6 сообщений = 3 пары «вопрос/ответ». Берётся как `new_history[-6:]`.

## Как протестировать

### 1. История накапливается

1. Авторизоваться и написать 4 сообщения подряд
2. Проверить в `demo_bot_sessions.context_data["history"]`:
   - Записей не более 6 (последние 3 пары)
   - Первые 2 сообщения удалены (sliding window)

### 2. История влияет на ответ

1. Написать «Что с моим делом?» — получить ответ о стадии X
2. Написать «Расскажи подробнее» — бот должен понять о чём речь из истории

### 3. Фоллбэк тоже пишется в историю

1. Симулировать ошибку OpenAI (отключить сеть)
2. Написать сообщение
3. Проверить: в `history` появились записи с `FALLBACK_ALEVTINA` в ответе

## Критерии приёмки

1. После каждого ответа `context_data["history"]` обновляется в Supabase
2. История содержит не более 6 записей (sliding window)
3. В GPT передаётся история ДО текущего сообщения (не включая его)
4. `case_context` в `context_data` не затирается при обновлении `history`
5. Фоллбэк-ответ тоже записывается в историю

## Правила завершения задачи

**После акцепта задачи AI выполняет автоматически:**

1. **Обновить файл задачи:**
   - Статус → `✅ accepted`
   - Добавить дату завершения

2. **Переместить файл:**
   - Из: `docs/3. GRISH-tasks/S01_demo_case_status_bot/T06_s01_dialog_history.md`
   - В: `docs/3. GRISH-tasks/Done/S01_demo_case_status_bot_done/T06_s01_dialog_history_done.md`

3. **Обновить спецификацию:**
   - Статус T06 → `✅ done`

4. **Обновить GRISH-HANDOFF.md:**
   - Отметить T06 как выполненную
