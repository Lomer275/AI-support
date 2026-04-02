Дата: 2026-03-20
Статус: ✅ accepted
Дата завершения: 2026-03-20
Спецификация: docs/2. SUP-specifications/S01_authorization.md

# T02 — Счётчик ошибок ИНН + двухэтапная эскалация

## Customer-facing инкремент

После двух неудачных попыток ввести ИНН Алина предлагает написать в поддержку — клиент не застревает в бесконечной петле.

## Изменения в коде

- `handlers/text.py`:
  - Добавлены fallback-строки с `@Lobster_21` для эскалации
  - В `_handle_waiting_inn`: после каждой ошибки (нет ИНН / не найден) инкрементируется `error_count`, сохраняется в Supabase
  - При `error_count >= 2` → `escalate=True` передаётся в промпты и fallback
- `services/openai_client.py`:
  - `inn_not_found(escalate=False)` — при `escalate=True` добавляет в промпт инструкцию упомянуть `@Lobster_21`
  - `no_inn_in_text(text, digit_count, escalate=False)` — аналогично

## Критерии приёмки

1. ✅ 1-я ошибка ИНН → ответ без `@Lobster_21`
2. ✅ 2-я ошибка ИНН → ответ содержит `@Lobster_21`
3. ✅ `error_count` в Supabase обновляется (1 → 2)
4. ✅ Оба типа ошибок считаются одним счётчиком
