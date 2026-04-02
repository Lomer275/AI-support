Дата: 2026-03-20
Статус: ✅ done
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T08 — Обновить `handlers/text.py`: подключить `SupportService`

## Customer-facing инкремент

Алина начинает отвечать через 7-агентный pipeline вместо однопромптового ответа — ответы становятся более точными и учитывают реальный контекст дела.

## Цель

Заменить вызов `openai_svc.chat_as_alina()` в `_handle_authorized()` на `support_svc.answer()` с fallback и индикатором «печатает...».

## Изменения в коде

- `handlers/text.py`:
  - В `handle_text` добавить `support_svc: SupportService` в сигнатуру
  - В `_handle_authorized()`:
    - Добавить параметр `support_svc: SupportService`
    - Перед вызовом pipeline: `await bot.send_chat_action(chat_id, ChatAction.TYPING)`
    - Запустить фоновую задачу повтора typing-индикатора каждые 4 сек на время выполнения pipeline
    - Читать `inn = session.get("inn") or ""`
    - Читать `contact_name = session.get("contact_name") or session.get("first_name") or "Клиент"`
    - Попытаться вызвать `await support_svc.answer(chat_id, inn, question, contact_name)`
    - При `Exception` → fallback: `await openai_svc.chat_as_alina(question, contact_name)`

  **Предварительно:** убедиться что RPC `get_or_create_session` возвращает поле `inn` в ответе. Если поле отсутствует — добавить его в SELECT внутри RPC-функции в Supabase.

## Как протестировать

1. Авторизоваться в боте
2. Написать вопрос: «Когда завершится моё дело?»
3. Убедиться что Telegram показывает «печатает...» во время ожидания
4. Получить ответ — он должен учитывать контекст дела (судебные документы)
5. Написать второй вопрос — Координатор должен помнить первый обмен
6. Проверить регрессию: пройти авторизацию заново (`/start`) и убедиться что все шаги работают

## Критерии приёмки

- [x] Авторизованный клиент получает ответ через pipeline
- [x] Telegram показывает «печатает...» в течение всего времени ответа
- [x] При падении pipeline клиент получает fallback-ответ (не стектрейс)
- [x] Ответы в `WAITING_INN` / `WAITING_PHONE` не изменились (регрессия)
- [x] `session["inn"]` корректно передаётся в `answer()`
