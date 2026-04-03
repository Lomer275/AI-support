# S05: Эскалация и качество ответов

**Статус:** draft  
**Дата:** 2026-04-03  
**Версия:** 1.2  
**BR:** [BR01_ai_manager_bfl.md](../1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md)

---

## 🎯 Цель

Анализ реального диалога (dialog2, клиент Дмитрий Валерьевич) выявил два класса проблем:

**1. Сломанная эскалация.** Двусторонняя переписка Bitrix ↔ Telegram не работает ни в одну сторону. Эскалация переключает на общую очередь Open Lines, а не на ответственного менеджера конкретной сделки. Координатор триггерит `switcher=true` слишком поздно — после четвёртого сигнала раздражения, игнорируя первые три.

**2. Деградация качества ответов.** Агенты не умеют работать с пробелами в данных — заполняют пустоту шаблоном вместо «не знаю». Арбитражный управляющий (АУ) не присутствует в контексте агентов. Одна фраза про стадию дела повторяется в 5 из 8 ответов. Шаблон «вам не нужно ничего делать» вставляется вне зависимости от вопроса.

Цель спринта — починить эскалацию полностью и устранить системные проблемы качества, выявленные по реальному диалогу.

---

## 📦 Scope

### Входит:

**Phase 1 — Двусторонняя переписка Bitrix ↔ Telegram:** ✅ 2026-04-03 (T24)

Оба направления **код имеет**, но не работают. Задача — диагностика и фикс, а не написание с нуля.

- [ ] **Telegram → Bitrix:** `handlers/text.py:150` при `session.get("escalated")` вызывает `imconnector_svc.send_message()` — код есть. Диагностировать почему сообщение не доходит: проверить payload `imconnector.send.messages`, формат `chat.id`, логи ответа Bitrix API
- [ ] **Bitrix → Telegram:** `webhook_server.py` обрабатывает `ONIMCONNECTORMESSAGEADD` и вызывает `bot.send_message(chat_id, text)` — код есть. Диагностировать: доходит ли вебхук от Bitrix на порт 8080, корректно ли парсится `data[MESSAGES][0][chat][id]`, совпадает ли он с Telegram `chat_id`
- [ ] Логировать входящий payload вебхука целиком при диагностике (временно, убрать после фикса)
- [ ] Отладка end-to-end: оператор пишет в Bitrix → клиент видит в Telegram, и наоборот

**Phase 2 — Перевод на ответственного сделки:** 🔵 Planned

> ⚠️ Ключевая проблема: чат в Bitrix создаётся автоматически при получении первого сообщения через коннектор — его Bitrix `CHAT_ID` нигде не сохраняется. Сейчас в `bot_sessions` хранится `bitrix_chat_id=str(telegram_chat_id)` — это **Telegram** ID, не Bitrix. Для вызова `imopenlines.chat.transfer` нужен именно Bitrix chat ID.

- [ ] Выяснить, возвращает ли `imconnector.send.messages` Bitrix chat ID в ответе — если да, сохранять его в `bot_sessions.bitrix_chat_id` при первой эскалации
- [ ] Если ID не возвращается — получать через `imopenlines.chat.list` по фильтру `USER_ID=telegram_chat_id` после создания чата
- [ ] После получения Bitrix chat ID вызывать `imopenlines.chat.transfer`:
  ```python
  await self._call("imopenlines.chat.transfer", {
      "CHAT_ID": bitrix_chat_id,
      "USER_ID": assigned_user_id,  # ASSIGNED_BY_ID из сделки
  })
  ```
- [ ] Получать `ASSIGNED_BY_ID` из `electronic_case.cases` (или из Bitrix если поле не синхронизировано)
- [ ] Добавить `assigned_user_id` в `cases_mapper.py` и схему `electronic_case` (если отсутствует)
- [ ] Fallback: если `ASSIGNED_BY_ID` пустой — не вызывать transfer, оставить чат в общей очереди (не падать)
- [ ] Watchdog (60 мин) — оставить без изменений

**Phase 3 — Умная эскалация:** 🔵 Planned
- [ ] Обновить промпт Координатора: `switcher=true` при первом явном сигнале раздражения
- [ ] Сигналы раздражения (триггер при любом из):
  - Риторические вопросы: «почему не знаете», «за что я вам плачу», «кто здесь вообще работает»
  - Повторный вопрос на тот же ответ без признания «не знаю» со стороны AI
  - Прямое выражение недовольства: «жаловаться», «это безобразие», «верните деньги»
- [ ] Обновить промпт Координатора: запретить продолжать шаблонные ответы после первого сигнала

**Phase 4 — АУ в контексте агентов:** ✅ 2026-04-03 (T26, реализовано в S04)
- [ ] Добавить поле `arbitration_manager` (ФИО арбитражного управляющего) в `cases_mapper.py`
- [ ] Синхронизировать из Bitrix: определить поле `UF_CRM_*` с ФИО АУ или взять из существующих полей сделки
- [ ] Убедиться что `get_case_context()` в `electronic_case.py` включает АУ в строку контекста
- [ ] Протестировать: вопрос «кто мой арбитражный управляющий» → ответ с реальным ФИО

**Phase 5 — Ответ при отсутствии данных:** 🔵 Planned
- [ ] Обновить промпты агентов R1/R2: если данных по вопросу нет в контексте → честно признать и предложить уточнить у менеджера
- [ ] Шаблон ответа: «Этой информации у меня нет. Хотите, я переключу вас на вашего менеджера?»
- [ ] `switcher=true` если клиент соглашается на переключение после «нет данных»
- [ ] Запретить агентам заполнять пробел шаблоном или предположением

**Phase 6 — Устранение повторений:** 🔵 Planned
- [ ] Передавать последние 3 ответа AI в контекст агентов R1 как «уже сказанное»
- [ ] Добавить в промпт R1: запрет повторять стадию дела если она уже упоминалась в ответах
- [ ] Убрать шаблон «вам не нужно ничего делать» из промптов агентов (заменить на конкретику по ситуации или убрать совсем)

**Phase 7 — Фикс тройного ответа от AI:** ✅ 2026-04-03 (T30)

Вероятная причина: клиент отправил три сообщения подряд быстро («почему не знаете» / «никто не отвечает» / «за что я плачу»). Каждое запустило отдельный pipeline в `SupportService.answer()` — все три выполнились параллельно и каждый прислал свой ответ. Это **не баг Coordinator**, а race condition на уровне обработки апдейтов.

- [ ] Диагностировать через логи: проверить timestamp трёх ответов — если они близко по времени, причина в параллельных pipeline
- [ ] Реализовать защиту от параллельных вызовов: per-chat lock (asyncio.Lock по `chat_id`) в `_handle_authorized` — новое сообщение ждёт завершения предыдущего pipeline
- [ ] Убедиться что при `switcher=true` клиент получает ровно одно сообщение эскалации (сначала `ai_text`, затем статус о переводе — но не три разных ответа)

### Не входит:

- Изменение watchdog (60 мин) — остаётся как есть
- Новые типы эскалации (email, звонок)
- Изменение логики авторизации
- Переработка multi-agent pipeline (S02) — только точечные изменения промптов

---

## 🏗 Архитектура и структура

### Файлы, затрагиваемые в спринте:

```
services/
├── imconnector.py      # FIX: диагностика send_message() (T→B); ADD: chat.transfer + получение Bitrix chat_id
├── electronic_case.py  # CHANGE: добавить arbitration_manager в get_case_context()
├── cases_mapper.py     # CHANGE: маппинг ASSIGNED_BY_ID + поля АУ из Bitrix  ⚠️ конфликт T2/T4
└── support.py          # CHANGE: last_3_answers в _r1_lawyer; промпты Coordinator/R1/R2 (инлайн)
                        # ⚠️ конфликт T3/T5/T6/T7 — все трогают этот файл

handlers/text.py        # ADD: per-chat asyncio.Lock против параллельных pipeline (T7)
webhook_server.py       # FIX: диагностика ONIMCONNECTORMESSAGEADD (B→T)
```

> Промпты инлайн в `support.py` — отдельного файла `prompts/` нет.
> Чат Bitrix создаётся автоматически при первом сообщении через коннектор — `imopenlines.crm.chat.add()` не вызывается.

### Двусторонняя переписка — ожидаемый флоу:

```
Telegram → Bitrix:
  клиент пишет в Telegram (escalation_state="in_operator_chat")
  → text.py пересылает через ImConnectorService.send_message()
  → появляется в чате Open Lines в Bitrix у ответственного

Bitrix → Telegram:
  оператор пишет в Bitrix Open Lines
  → Bitrix шлёт ONIMCONNECTORMESSAGEADD на webhook_server.py (порт 8080)
  → webhook_server.py парсит и отправляет в Telegram через bot.send_message()
```

### Перевод на ответственного — вызов после создания чата:

```python
# В ImConnectorService после imopenlines.crm.chat.add():
await self._call("imopenlines.chat.transfer", {
    "CHAT_ID": chat_id,
    "USER_ID": assigned_user_id,   # ASSIGNED_BY_ID из сделки
})
```

### Контекст агентов — добавление last_3_answers:

История уже читается из Supabase `chat_history` через `SupportSupabaseService` внутри `SupportService.answer()`. Источник — тот же что передаётся в `send_escalation`. Дополнительного вызова не нужно.

```python
# В SupportService.answer(), после получения history из Supabase:
last_answers = [m["content"] for m in history if m["role"] == "assistant"][-3:]
last_answers_text = "\n---\n".join(last_answers) if last_answers else ""
# Добавить в system-промпт _r1_lawyer():
# "Ты уже отвечал клиенту следующее (не повторяй эти утверждения дословно):\n{last_answers_text}"
```

---

## 📋 Задачи и параллелизм

> ⚠️ Номера TNN будут присвоены после декомпозиции (/task-planner)

**Группа 1 — всё параллельно (разные файлы):**

```
T1: Двусторонняя переписка     → webhook_server.py + imconnector.py (send_message)
T2: Перевод на ответственного  → imconnector.py (_create_chat + transfer) + cases_mapper.py*
T3: Фикс тройного ответа       → support.py (coordinator flow)
T4: АУ в контексте             → cases_mapper.py* + electronic_case.py
T5: Умная эскалация            → support.py (промпт Coordinator)
T6: Ответ при отсутствии данных → support.py (промпт R1/R2)
T7: Устранение повторений      → support.py (last_3_answers + промпт R1)
```

> ⚠️ Конфликты по файлам — координировать или делать последовательно:
> - `cases_mapper.py`: T2 и T4
> - `support.py`: T3, T5, T6, T7 — четыре задачи в одном файле

**Группа 2 — после завершения всей Группы 1:**

```
T8: Регрессия — quality_run.py + воспроизведение dialog2-сценария вручную
```

| ID | Задача | Зависит от | Параллельно с | Статус |
|----|--------|------------|---------------|--------|
| [T24](../3.%20SUP-tasks/S05_escalation_and_quality/T24_s05_bidirectional_chat.md) | Двусторонняя переписка Bitrix ↔ Telegram | — | T25, T26, T27, T28, T29, T30 | 🔵 planned |
| [T25](../3.%20SUP-tasks/S05_escalation_and_quality/T25_s05_transfer_to_responsible.md) | Перевод на ответственного (`chat.transfer` + fallback) | T24 | T26*, T27, T28, T29, T30 | 🔵 planned |
| [T26](../3.%20SUP-tasks/S05_escalation_and_quality/T26_s05_au_in_context.md) | АУ в `cases_mapper.py` и `get_case_context()` | — | T24, T25*, T27, T28, T29, T30 | 🔵 planned |
| [T27](../3.%20SUP-tasks/S05_escalation_and_quality/T27_s05_smart_escalation.md) | Умная эскалация — промпт Coordinator | — | T24, T25, T26, T28*, T29*, T30 | 🔵 planned |
| [T28](../3.%20SUP-tasks/S05_escalation_and_quality/T28_s05_no_data_response.md) | Ответ при отсутствии данных — промпт R1/R2 | T26 | T24, T25, T27*, T29*, T30 | 🔵 planned |
| [T29](../3.%20SUP-tasks/S05_escalation_and_quality/T29_s05_no_repetition.md) | Устранение повторений — last_3_answers + промпт | — | T24, T25, T26, T27*, T28*, T30 | 🔵 planned |
| [T30](../3.%20SUP-tasks/S05_escalation_and_quality/T30_s05_parallel_pipeline_fix.md) | Фикс параллельных pipeline (тройной ответ) | — | T24, T25, T26, T27, T28, T29 | 🔵 planned |
| [T31](../3.%20SUP-tasks/S05_escalation_and_quality/T31_s05_regression.md) | Регрессия — quality_run.py + dialog2-сценарий | T24–T30 | — | 🔵 planned |

> `*` — конфликт по файлу: `cases_mapper.py` (T25, T26), `support.py` (T27, T28, T29)

---

## 🧪 DoD (Definition of Done)

- [ ] Оператор пишет в Bitrix → клиент получает в Telegram (без задержки, без дублей)
- [ ] Клиент пишет в Telegram в статусе эскалации → оператор видит в Bitrix
- [ ] После создания чата Open Lines — чат переведён на ответственного сделки
- [ ] Первый сигнал раздражения клиента → `switcher=true` без продолжения шаблонных ответов
- [ ] Вопрос «кто мой АУ» → ответ с реальным ФИО из `electronic_case`
- [ ] Вопрос без данных → «Этой информации у меня нет. Хотите переключить на менеджера?»
- [ ] Стадия дела не повторяется в каждом ответе подряд
- [ ] Шаблон «вам не нужно ничего делать» убран
- [ ] После `switcher=true` — одно сообщение эскалации, не три
- [ ] Прогон на dialog2-сценарии: все 8 проблем не воспроизводятся

---

## ⚠️ Риски

- **Bitrix Open Lines API** — `imopenlines.chat.transfer` может требовать специфических прав / конфигурации очереди. Нужно проверить в Bitrix-документации и на тестовой среде до внедрения
- **ASSIGNED_BY_ID** — поле может быть пустым в части сделок (нет ответственного). Нужен fallback: если пусто — не вызывать transfer, оставить в общей очереди
- **Webhook двусторонности** — порт 8080 должен быть доступен из Bitrix. Проверить firewall / ngrok для локального тестирования
- **Промпт-изменения** — правки промптов могут улучшить одни сценарии и сломать другие. Прогнать `quality_run.py` до и после каждой фазы промптов

---

## 🔗 Связанные документы

- Диалог: `docs/5. SUP-unsorted/dialog2.md`
- Анализ: `docs/5. SUP-unsorted/dialog2_analysis.md`
- Зависит от: `S02_multi_agent_chat.md`, `S04_electronic_case.md`
- `services/imconnector.py`, `services/support.py`, `services/cases_mapper.py`
- `webhook_server.py`
