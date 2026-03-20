Дата: 2026-03-20
Статус: ⬜ pending
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T05 — `SupportService`: Координатор + публичный `answer()`

## Customer-facing инкремент

Финальный агент читает всю дискуссию R1+R2 и историю диалога, формирует ответ клиенту от лица Алины. Публичный метод `answer()` оркеструет весь pipeline и обрабатывает ошибки.

## Цель

Добавить в `SupportService` Координатора и публичный метод `answer()`, который запускает весь 7-агентный pipeline, сохраняет историю и возвращает итоговый ответ клиенту.

## Изменения в коде

- `services/support.py` — добавить в класс `SupportService`:
  - `_coordinator(full_discussion: str, history: list[dict]) -> str | None`
    - Модель: `OPENAI_MODEL_COORDINATOR`, `max_tokens=400`, `temperature=0.6`
    - Промпт: Coordinator2 из `Support_new.json`
    - История передаётся через системный промпт (не как messages)
    - Возвращает JSON-строку `{"answer": "...", "switcher": "true"|"false"}`
  - `_parse_coordinator_output(raw: str) -> dict`
    - Очищает от ```json``` обёрток, парсит JSON
    - При неудаче → возвращает `{"answer": None, "switcher": "false"}`
  - `answer(chat_id, inn, question, contact_name) -> str` — публичный метод:
    ```
    history = await supabase_support.get_chat_history(chat_id)
    client_context = await supabase_support.search_client_by_inn(inn)
    r1_lawyer  = await _r1_lawyer(client_context, question)
    r1_manager = await _r1_manager(client_context, question, r1_lawyer)
    r1_sales   = await _r1_sales(client_context, question)
    r2_lawyer  = await _r2_lawyer(...)
    r2_manager = await _r2_manager(...)
    r2_sales   = await _r2_sales(...)
    full_discussion = _prepare_discussion(...)
    raw = await _coordinator(full_discussion, history)
    result = _parse_coordinator_output(raw)
    answer = result["answer"] или FALLBACK_ALINA
    await supabase_support.save_chat_message(chat_id, "user", question)
    await supabase_support.save_chat_message(chat_id, "assistant", answer)
    return answer
    ```
    - Если любой агент вернул `None` → бросить `RuntimeError` (fallback в хэндлере)
    - `switcher="true"` → ответ отправляется как есть (заглушка)

## Как протестировать

1. Вызвать `answer(chat_id=999, inn="360300651183", question="Когда завершится дело?", contact_name="Тест")`
2. Проверить что ответ — осмысленный текст на русском, 2–4 предложения
3. Проверить что в `chat_history` появились 2 записи (user + assistant)
4. Вызвать повторно с тем же `chat_id` — убедиться что в новом ответе Координатор видит историю

## Критерии приёмки

- [ ] `answer()` возвращает строку (ответ клиенту)
- [ ] История сохраняется в `chat_history` после каждого вызова
- [ ] Координатор получает историю из `get_chat_history`
- [ ] При `None` от любого агента R1/R2 — `answer()` бросает `RuntimeError`
- [ ] Невалидный JSON от Координатора не роняет бота — возвращается `FALLBACK_ALINA`
- [ ] `switcher="true"` — ответ клиенту всё равно отправляется
