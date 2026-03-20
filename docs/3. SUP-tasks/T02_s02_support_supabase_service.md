Дата: 2026-03-20
Статус: ⬜ pending
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T02 — Реализовать `SupportSupabaseService`

## Customer-facing инкремент

Бот получает доступ к судебным документам клиента и может хранить историю диалога — основа для персонализированных ответов Алины.

## Цель

Создать `services/supabase_support.py` с тремя методами: загрузка контекста клиента из `smart_process_kad_arbitr`, чтение и запись истории чата в `chat_history`.

## Изменения в коде

- `services/supabase_support.py` — новый файл:
  - Класс `SupportSupabaseService(session: aiohttp.ClientSession)`
  - Подключается к `SUPABASE_SUPPORT_URL` / `SUPABASE_SUPPORT_ANON_KEY`
  - `search_client_by_inn(inn: str) -> str`:
    - POST на RPC `search_client_by_inn` с `{"p_inn": inn}`
    - Форматирует результат по логике Formatter-ноды из `Support_new.json`:
      - Для каждого документа с `full_document_text` длиннее 20 символов: добавляет заголовок (тип, дата, название) и текст (до 3000 символов)
      - Если документов нет → возвращает `"[Данные не найдены]"`
  - `get_chat_history(chat_id: int, limit: int = 10) -> list[dict]`:
    - GET на `chat_history?chat_id=eq.{chat_id}&order=created_at.asc&limit={limit}`
    - Возвращает `[{"role": "...", "content": "..."}]`
    - При ошибке → логирует и возвращает `[]`
  - `save_chat_message(chat_id: int, role: str, content: str) -> None`:
    - POST на `chat_history` с `{"chat_id": chat_id, "role": role, "content": content}`
    - При ошибке → логирует, не прерывает

## Предварительно

Проверить, что RPC `search_client_by_inn` доступен через anon-ключ. Если нет (ошибка 401/403) — сообщить, потребуется `service_role`-ключ или изменение RLS-политики.

## Как протестировать

1. Создать экземпляр `SupportSupabaseService` с реальным `aiohttp.ClientSession`
2. Вызвать `search_client_by_inn("360300651183")` — должен вернуть непустую строку с текстами документов
3. Вызвать `get_chat_history(999999)` — должен вернуть `[]` (нет записей)
4. Вызвать `save_chat_message(999999, "user", "тест")` — убедиться что запись появилась в Supabase
5. Вызвать `get_chat_history(999999)` снова — должен вернуть 1 запись

## Критерии приёмки

- [ ] `search_client_by_inn` возвращает форматированный контекст при наличии документов
- [ ] `search_client_by_inn` возвращает `"[Данные не найдены]"` если документов нет
- [ ] `get_chat_history` возвращает записи в хронологическом порядке (старые → новые)
- [ ] `save_chat_message` сохраняет запись в Supabase
- [ ] Ошибки соединения логируются, не бросают исключение наружу
