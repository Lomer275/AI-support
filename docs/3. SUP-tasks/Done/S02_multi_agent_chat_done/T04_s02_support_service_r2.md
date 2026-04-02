Дата: 2026-03-20
Статус: ✅ done
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T04 — `SupportService`: R2-раунд + сборка `full_discussion`

## Customer-facing инкремент

Второй раунд уточняет позиции R1 — агенты видят мнения коллег и корректируют рекомендации. Результат собирается в единый контекст для финального Координатора.

## Цель

Добавить в `SupportService` три метода R2-раунда и вспомогательную функцию сборки `full_discussion`. Промпты — из нод `R2 Lawyer`, `R2 Manager`, `R2 Sales` в `Support_new.json`.

## Изменения в коде

- `services/support.py` — добавить в класс `SupportService`:
  - `_r2_lawyer(client_context, question, r1_lawyer, r1_manager, r1_sales) -> str | None`
    - Промпт: R2 Lawyer из `Support_new.json`
  - `_r2_manager(client_context, question, r1_lawyer, r1_manager, r1_sales, r2_lawyer) -> str | None`
    - Промпт: R2 Manager из `Support_new.json`
  - `_r2_sales(client_context, question, r1_lawyer, r1_manager, r1_sales, r2_lawyer, r2_manager) -> str | None`
    - Промпт: R2 Sales из `Support_new.json`
  - `_prepare_discussion(question, r1_lawyer, r1_manager, r1_sales, r2_lawyer, r2_manager, r2_sales, client_context) -> str`
    - Формат (точный перенос из `Prepare Coordinator`-ноды `Support_new.json`):
      ```
      ВОПРОС КЛИЕНТА:
      {question}

      === РАУНД 1 ===
      ЮРИСТ R1: {r1_lawyer}
      МЕНЕДЖЕР R1: {r1_manager}
      КУРАТОР R1: {r1_sales}

      === РАУНД 2 (КОРРЕКТИРОВКИ) ===
      ЮРИСТ R2: {r2_lawyer}
      МЕНЕДЖЕР R2: {r2_manager}
      КУРАТОР R2: {r2_sales}

      === КОНТЕКСТ КЛИЕНТА ===
      {client_context}
      ```

## Как протестировать

1. Подготовить моковые строки r1_lawyer / r1_manager / r1_sales (можно из T03)
2. Вызвать `_r2_lawyer(...)` — ответ содержит «Что я изменил в позиции», «Юридическое ядро ответа»
3. Вызвать `_r2_manager(...)` — ответ содержит «Ключевые фразы для ответа»
4. Вызвать `_r2_sales(...)` — ответ содержит «Рискованные обещания»
5. Вызвать `_prepare_discussion(...)` — убедиться что все секции присутствуют в правильном порядке

## Критерии приёмки

- [x] Все три R2-метода получают именно те входы, что указаны в таблице агентов спецификации
- [x] `_prepare_discussion` собирает строку с шестью секциями в правильном порядке
- [x] Промпты соответствуют нодам R2 из `Support_new.json`
- [x] При возврате `None` любым R2-агентом — исключение будет поймано в `answer()` (T05)
