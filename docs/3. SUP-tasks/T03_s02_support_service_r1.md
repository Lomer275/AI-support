Дата: 2026-03-20
Статус: ⬜ pending
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T03 — `SupportService`: R1-раунд (Юрист, Менеджер, Куратор)

## Customer-facing инкремент

Первый раунд независимого анализа вопроса клиента: юридическая оценка, эмоциональный анализ, операционные риски — три точки зрения на одну ситуацию.

## Цель

Создать `services/support.py` с тремя методами R1-раунда. Промпты переносятся дословно из `Support_new.json` (ноды `R1 Lawyer`, `R1 Manager`, `R1 Sales`).

## Изменения в коде

- `services/support.py` — новый файл:
  - Класс `SupportService(http_session, supabase_support, openai_api_key, model_support, model_coordinator)`
  - `_complete(system: str, user: str, model: str, max_tokens: int = 500, temperature: float = 0.8) -> str | None` — базовый вызов OpenAI
  - `_r1_lawyer(client_context: str, question: str) -> str | None`
    - Системный промпт: R1 Lawyer из `Support_new.json`
    - Входы: `client_context`, `question`
  - `_r1_manager(client_context: str, question: str, r1_lawyer: str) -> str | None`
    - Системный промпт: R1 Manager из `Support_new.json`
    - Входы: `client_context`, `question`, `r1_lawyer`
  - `_r1_sales(client_context: str, question: str) -> str | None`
    - Системный промпт: R1 Sales из `Support_new.json`
    - Входы: `client_context`, `question` *(независимый агент — r1_lawyer/r1_manager не получает)*

## Как протестировать

1. Вызвать `_r1_lawyer(client_context="[Данные не найдены]", question="Когда завершится моё дело?")`
2. Убедиться что ответ содержит блоки «Ситуация клиента», «Ключевые факты», «Юридическое мнение», «РЕКОМЕНДАЦИЯ SWITCHER»
3. Проверить `_r1_manager` — ответ содержит «Эмоциональное состояние», «Что важно сказать»
4. Проверить `_r1_sales` — ответ содержит «Этап и сроки», «Риски коммуникации»

## Критерии приёмки

- [ ] Все три метода возвращают непустую строку при валидных входах
- [ ] Промпты соответствуют нодам `R1 Lawyer`, `R1 Manager`, `R1 Sales` из `Support_new.json`
- [ ] `_r1_sales` не получает `r1_lawyer` / `r1_manager` в промпт
- [ ] При ошибке OpenAI методы возвращают `None`, не бросают исключение
