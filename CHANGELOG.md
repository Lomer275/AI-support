# Changelog

## [0.2.0] — S02: Multi-Agent Chat

### 2026-03-20

#### Added
- `services/supabase_support.py` — `SupportSupabaseService`: загрузка судебных документов клиента по ИНН (RPC `search_client_by_inn`), чтение и запись истории диалога (`chat_history`) (T02)
- `services/support.py` — `SupportService`: полный 7-агентный pipeline (T03–T05)
  - R1-раунд: `_r1_lawyer`, `_r1_manager`, `_r1_sales`
  - R2-раунд: `_r2_lawyer`, `_r2_manager`, `_r2_sales`
  - Координатор: `_coordinator` с промптом Coordinator2, `_parse_coordinator_output`
  - Публичный метод `answer()` с оркестрацией, сохранением истории и fallback

#### Changed
- `handlers/text.py` — `_handle_authorized()` заменён: `support_svc.answer()` вместо `chat_as_alina`; фоновый цикл `send_chat_action(TYPING)` каждые 4 сек; fallback на `chat_as_alina` при исключении (T08)

#### Infrastructure
- Таблица `chat_history` создана в Supabase support (`sgsxxmxybcysvbfsohau`) с индексом `idx_chat_history_chat_id_created` (T01)

---

## [0.1.0] — S01: Authorization

### 2026-03-20

#### Added
- Авторизация через ИНН + телефон (state machine: `waiting_inn` → `waiting_phone` → `authorized`)
- Интеграция с Bitrix24 (batch API: поиск сделки по ИНН, обновление статуса авторизации)
- Дедупликация Telegram-апдейтов через Supabase RPC `get_or_create_session`
- `services/supabase.py` — `SupabaseService`
- `services/bitrix.py` — `BitrixService`
- `services/openai_client.py` — `OpenAIService` (5 промптов)
- Хэндлеры: `/start`, контакт (телефон), inline-callbacks, текст (FSM по состоянию)
