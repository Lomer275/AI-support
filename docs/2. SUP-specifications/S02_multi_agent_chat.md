# S02: Multi-Agent Chat (Ответы на типовые вопросы)

**Статус:** 🟡 Draft
**Версия:** 1.1
**Дата создания:** 2026-03-20
**Автор:** zhiga
**BR:** [BR01_ai_manager_bfl.md](../1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md)

---

## 🎯 Цель

Заменить однопромптовый `chat_as_alina` на multi-agent pipeline, который отвечает клиенту с учётом реального контекста его дела (судебные документы из Supabase) и истории диалога. Качество ответов должно приблизиться к уровню n8n-воркфлоу `Support_new.json`, перенесённому в Python.

---

## 📦 Scope

### Входит:

- Новый сервис `SupportSupabaseService`: загрузка судебных документов клиента (`smart_process_kad_arbitr` via RPC `search_client_by_inn`), хранение и чтение истории диалога (`chat_history`)
- `SupportService`: pipeline из 7 агентов — R1 (Юрист → Менеджер → Куратор) → R2 (Юрист → Менеджер → Куратор) → Координатор
- Память диалога: последние 10 сообщений по `chat_id` в таблице `chat_history`
- Fallback: при исключении в `SupportService` — откат на `openai_svc.chat_as_alina()` (существующий промпт)
- Поле `switcher` в ответе Координатора — заглушка (эскалация реализуется в отдельном спринте)
- Новые env-переменные и новые поля `config.py`

### Не входит:

- Эскалация на оператора (`switcher=true`)
- Ответы в состояниях `WAITING_INN` / `WAITING_PHONE` — остаются на прежних промптах
- Изменение логики авторизации

---

## 🏗 Архитектура

### Новые и изменяемые файлы

```
services/
├── supabase_support.py   # NEW: SupportSupabaseService (support Supabase project)
└── support.py            # NEW: SupportService — весь 7-агентный pipeline

handlers/
└── text.py               # CHANGE: _handle_authorized() → support_svc.answer()
                          #   читает session["inn"] и передаёт в answer()
                          #   перед вызовом: bot.send_chat_action(TYPING)

bot.py                    # ADD: инициализация SupportSupabaseService + SupportService,
                          #       dp["support_svc"] = support_svc

config.py                 # ADD: supabase_support_url, supabase_support_anon_key,
                          #       openai_model_support, openai_model_coordinator

.env                      # ADD: SUPABASE_SUPPORT_URL, SUPABASE_SUPPORT_ANON_KEY,
                          #       OPENAI_MODEL_SUPPORT, OPENAI_MODEL_COORDINATOR
```

**Два Supabase-проекта:**
- `SupabaseService` (существующий) → `SUPABASE_URL` / `SUPABASE_ANON_KEY` — сессии бота (`bot_sessions`)
- `SupportSupabaseService` (новый) → `SUPABASE_SUPPORT_URL` / `SUPABASE_SUPPORT_ANON_KEY` — судебные документы и история чата

### Data flow

```
Клиент → сообщение (состояние AUTHORIZED)
  ↓
bot.send_chat_action(chat_id, ChatAction.TYPING)  ← отправить до начала pipeline
  ↓
support_supabase.get_chat_history(chat_id, limit=10)  →  history[]
support_supabase.search_client_by_inn(inn)            →  client_context (str)
  ↓
R1 Юрист   (client_context, question)                          →  r1_lawyer
R1 Менеджер (client_context, question, r1_lawyer)              →  r1_manager
R1 Куратор  (client_context, question)                         →  r1_sales
  ↓
R2 Юрист   (client_context, question, r1_lawyer, r1_manager, r1_sales)               →  r2_lawyer
R2 Менеджер (client_context, question, r1_lawyer, r1_manager, r1_sales, r2_lawyer)   →  r2_manager
R2 Куратор  (client_context, question, r1_lawyer, r1_manager, r1_sales,
             r2_lawyer, r2_manager)                                                   →  r2_sales
  ↓
Prepare discussion:
  full_discussion = "ВОПРОС КЛИЕНТА:\n{question}\n\n
    === РАУНД 1 ===\nЮРИСТ R1: {r1_lawyer}\nМЕНЕДЖЕР R1: {r1_manager}\nКУРАТОР R1: {r1_sales}\n\n
    === РАУНД 2 ===\nЮРИСТ R2: {r2_lawyer}\nМЕНЕДЖЕР R2: {r2_manager}\nКУРАТОР R2: {r2_sales}\n\n
    === КОНТЕКСТ КЛИЕНТА ===\n{client_context}"
  ↓
Координатор (full_discussion, history[])  →  CoordinatorOutput{answer, switcher}
  ↓
switcher=true  →  ответ отправляется клиенту как есть (заглушка)
  ↓
support_supabase.save_chat_message(chat_id, "user",      question)
support_supabase.save_chat_message(chat_id, "assistant", answer)
  ↓
ответ клиенту

Исключение на любом шаге →  fallback: openai_svc.chat_as_alina(question, contact_name)
```

### Входные данные каждого агента (точная таблица)

Источник правды — промпты в `Support_new.json`. Ниже — полная таблица входов:

| Агент | Получает в системный промпт |
|-------|-----------------------------|
| R1 Юрист | `client_context`, `question` |
| R1 Менеджер | `client_context`, `question`, `r1_lawyer` |
| R1 Куратор | `client_context`, `question` *(не видит r1_lawyer/r1_manager — независимый агент)* |
| R2 Юрист | `client_context`, `question`, `r1_lawyer`, `r1_manager`, `r1_sales` |
| R2 Менеджер | `client_context`, `question`, `r1_lawyer`, `r1_manager`, `r1_sales`, `r2_lawyer` |
| R2 Куратор | `client_context`, `question`, `r1_lawyer`, `r1_manager`, `r1_sales`, `r2_lawyer`, `r2_manager` |
| Координатор | `full_discussion` (содержит `question`), `history[]` через системный промпт |

---

## 🧱 Модели данных

### Новая таблица `chat_history` (Supabase support — проект `sgsxxmxybcysvbfsohau`)

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | bigserial PK | |
| `chat_id` | bigint | Telegram chat id |
| `role` | text | `user` \| `assistant` |
| `content` | text | Текст сообщения |
| `created_at` | timestamptz | default now() |

Индекс: `(chat_id, created_at DESC)` для выборки последних N записей.

### `SupportSupabaseService` — интерфейс

```python
class SupportSupabaseService:
    async def search_client_by_inn(self, inn: str) -> str
    # Вызывает RPC search_client_by_inn(p_inn), форматирует документы
    # в единую строку client_context (тип, дата, название, текст до 3000 символов).
    # Если документов нет — возвращает "[Данные не найдены]".
    # Логика форматирования — точный перенос из Formatter-ноды Support_new.json.

    async def get_chat_history(self, chat_id: int, limit: int = 10) -> list[dict]
    # Возвращает [{"role": "user"|"assistant", "content": "..."}]
    # в порядке от старых к новым.

    async def save_chat_message(self, chat_id: int, role: str, content: str) -> None
```

### `SupportService` — интерфейс

```python
class SupportService:
    async def answer(
        self,
        chat_id: int,
        inn: str,
        question: str,
        contact_name: str,  # используется только в fallback chat_as_alina; в агентов не передаётся
    ) -> str
    # Запускает полный pipeline.
    # При любом исключении внутри — пробрасывает наружу (fallback в хэндлере).
```

### Выходная схема Координатора

Координатор обязан вернуть валидный JSON:

```json
{"answer": "<строка — ответ клиенту>", "switcher": "true" | "false"}
```

- `answer` — строка, 2–4 предложения на русском, без смайликов
- `switcher` — строка `"true"` или `"false"` (не boolean)
- При `switcher="true"` значение `answer` жёстко зафиксировано: `"Подождите несколько минут, мне нужно уточнить"`

При невалидном JSON — попытка strip/clean и повторный `json.loads`; при неудаче — `FALLBACK_ALINA`.

### Параметры агентов

| Агент | Модель | max_tokens | temperature |
|-------|--------|------------|-------------|
| R1/R2 Юрист, Менеджер, Куратор | `OPENAI_MODEL_SUPPORT` | 500 | 0.8 |
| Координатор | `OPENAI_MODEL_COORDINATOR` | 400 *(tuning required)* | 0.6 |

> `max_tokens=400` для Координатора — начальное значение, требует проверки в тестовом прогоне. При обрезании JSON — увеличить до 600.

---

## ⚠️ Обработка ошибок

| Ситуация | Поведение |
|---------|-----------|
| Документы по ИНН не найдены | `client_context = "[Данные не найдены]"`, pipeline продолжается |
| Любой агент R1/R2 вернул `None` или исключение | Исключение пробрасывается из `SupportService`, хэндлер вызывает fallback `chat_as_alina` |
| Координатор вернул невалидный JSON | Попытка очистки и парсинга; при неудаче — `FALLBACK_ALINA` |
| `switcher="true"` | Ответ отправляется клиенту как есть (заглушка) |
| `get_chat_history` упал | Логировать, вернуть `[]`, pipeline продолжается без истории |
| `save_chat_message` упал | Логировать, не прерывать ответ клиенту |
| `SUPABASE_SUPPORT_ANON_KEY` не имеет прав к RPC | Ошибка попадает в обработчик исключений → fallback |

> **Риск RLS:** `search_client_by_inn` в n8n использовала `service_role`-ключ. Anon-ключ может быть заблокирован RLS. При реализации T02 — первым делом проверить права.

---

## 📋 Задачи

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T01 | Создать таблицу `chat_history` в Supabase support (sgsxxmxybcysvbfsohau) | — | pending |
| T02 | Реализовать `SupportSupabaseService`: `search_client_by_inn` + форматтер (логика из Formatter-ноды `Support_new.json`), `get_chat_history`, `save_chat_message` | T01 | pending |
| T03 | Реализовать `SupportService` — R1-раунд: методы `_r1_lawyer`, `_r1_manager`, `_r1_sales` с промптами из `Support_new.json`; каждый метод принимает только свои входы согласно таблице агентов | T02 | pending |
| T04 | Реализовать `SupportService` — R2-раунд: методы `_r2_lawyer`, `_r2_manager`, `_r2_sales`; сборка `full_discussion` по формату из `Prepare Coordinator`-ноды | T03 | pending |
| T05 | Реализовать `SupportService` — Координатор и точка входа: метод `_coordinator` + публичный `answer()`; JSON-парсинг с fallback; обработка `switcher` (заглушка) | T04 | pending |
| T06 | Обновить `config.py` и `.env` (4 новые переменные: `SUPABASE_SUPPORT_URL`, `SUPABASE_SUPPORT_ANON_KEY`, `OPENAI_MODEL_SUPPORT`, `OPENAI_MODEL_COORDINATOR`) | — | pending |
| T07 | Обновить `bot.py` — инициализация `SupportSupabaseService` + `SupportService`, `dp["support_svc"]` | T05, T06 | pending |
| T08 | Обновить `handlers/text.py`: `_handle_authorized()` читает `session["inn"]` и `contact_name = session.get("contact_name") or session.get("first_name") or "Клиент"`; вызывает `bot.send_chat_action(TYPING)`, затем `support_svc.answer()`; при исключении — fallback на `chat_as_alina`. Повтор `send_chat_action` каждые ~4 сек (фоновый цикл). *Предварительно:* проверить что RPC `get_or_create_session` возвращает поле `inn` | T07 | pending |
| T09 | Тестирование: пройти сценарии вручную через Telegram — типовой вопрос с документами, вопрос без документов, второй вопрос (проверка памяти), падение агента (fallback), перезапуск бота (персистентность истории); проверить регрессию `WAITING_INN` / `WAITING_PHONE` | T08 | pending |

---

## 🧪 Acceptance Criteria

- [ ] Авторизованный клиент задаёт вопрос → получает ответ через 7-агентный pipeline
- [ ] В ответе используется контекст судебных документов (если есть по ИНН)
- [ ] Второй вопрос в рамках сессии → Координатор видит историю предыдущего обмена
- [ ] История сохраняется в Supabase и переживает перезапуск бота (проверить: остановить бота, спросить снова — история есть)
- [ ] Если документов по ИНН нет → бот отвечает без падения, `[Данные не найдены]` не попадает в текст клиенту
- [ ] Если любой агент R1/R2 упал → клиент получает fallback `chat_as_alina`, не технический стектрейс
- [ ] `switcher="true"` не ломает ответ — клиент получает текст из поля `answer`
- [ ] Telegram показывает индикатор «печатает...» в течение всего времени выполнения pipeline
- [ ] Ответы в `WAITING_INN` / `WAITING_PHONE` работают как прежде (регрессия)

---

## ⚠️ Риски

- **Латентность 10–25 сек:** `send_chat_action(TYPING)` имеет TTL 5 секунд — нужно отправлять повторно каждые ~4 сек во время pipeline. Реализовать в T06 (фоновый цикл или повтор перед каждым агентом).
- **RLS Supabase support:** Anon-ключ может не иметь прав на `search_client_by_inn`. Проверить в самом начале T02; при необходимости — запросить `service_role`-ключ.
- **Стоимость:** 7 вызовов на каждый вопрос. При росте аудитории — пересмотреть в пользу упрощённого pipeline.
- **`@Lobster_21` захардкожен:** контакт поддержки в промптах агентов. При смене контакта — обновить системные промпты в `SupportService`.

---

## 🔗 Связанные документы

- BR: [BR01_ai_manager_bfl.md](../1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md)
- S01: [S01_authorization.md](S01_authorization.md)
- n8n workflow (источник промптов): [docs/5. SUP-unsorted/Support_new.json](../5.%20SUP-unsorted/Support_new.json)
