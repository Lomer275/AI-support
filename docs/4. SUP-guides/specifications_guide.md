# Гайд: как писать спецификации (Sprints)

## 🎯 1. Назначение спецификации

Спецификация — это **разработческий документ для спринта**, который отвечает на вопросы:

* **Что именно нужно построить** — какой функционал, экраны, поведение
* **Зачем это важно сейчас** — какой инкремент получает пользователь или бизнес
* **Какие границы реализации** — что входит и что явно не входит в scope
* **Как это устроено** — архитектура, структура, интеграции
* **Как проверяем результат** — критерии приёмки (DoD)

### Специфика для Cleaning Bot

Проект включает:
* **TMA (Telegram Mini App)** — React + TypeScript веб-приложение в Telegram WebView
* **Backend API** — Python (aiohttp) для обработки данных, AI pipeline, интеграций
* **Telegram Bots** — Pyrogram/Aiogram для мониторинга и управления
* **AI Pipeline** — OpenAI GPT-4o Vision, Whisper для анализа видео уборок
* **Integrations** — Dropbox (хранение), PostgreSQL (БД)

---

## 📚 2. Структура спецификаций в проекте

**ВАЖНО:** Проект использует номенклатуру **SNN** для спринтов и **TNN** для задач (см. [doc_conventions.md](doc_conventions.md)).

### Что такое Sprint Specification (SNN)

Спринт группирует задачи (TNN) для реализации одного функционального блока или фичи.

**Формат имени:**
```
SNN_<snake_case_название>.md
```

**Примеры:**
- `S25_ai_analytics_debug.md` — AI pipeline debugging и analytics
- `S18_tma_localization.md` — Локализация TMA на тайский
- `S11_tma_reference_photos_comparison.md` — Сравнение с reference фото

### Что такое Task (TNN)

Задача — это **конкретная реализуемая единица работы** внутри спринта.

**Формат имени:**
```
TNN_sNN_<snake_case_название>.md
```
где `sNN` — номер спринта (например, `s25` для S25).

**Примеры:**
- `T210_s25_p6_count_all_items.md` — задача в спринте S25
- `T197_s25_remove_blur_retry_done.md` — завершенная задача из S25

---

## 🧭 3. Стандартная структура Sprint Specification

### **Шаблон имени файла**
```
SNN_<snake_case_название>.md
```
Примеры: `S25_ai_analytics_debug.md`, `S18_tma_localization.md`

---

### **3.1. Заголовок**

```markdown
# SNN: <Название Спринта>

**Статус:** draft / active / phase N done / done
**Дата:** YYYY-MM-DD
**Дата завершения:** YYYY-MM-DD (если done)
**BR:** [Ссылка на бизнес-требования](../1. businees requirements/...)
```

**Примеры статусов:**
- `draft` — черновик, планируется
- `active` — в работе
- `Phase 1 done, Phase 2 active` — многофазный спринт
- `done` — завершён, все задачи выполнены

---

### **3.2. 🎯 Цель**

1–2 абзаца:
* Какую проблему решаем
* Какой инкремент получает пользователь или система
* Почему это приоритетно сейчас

**Пример (из S25):**
```markdown
## Цель

Инструменты для отладки AI pipeline и A/B тестирования промптов:
- Понять **почему** AI ответил так (input/output каждого вызова)
- Сравнить эффективность разных версий промптов
- Найти проблемные паттерны (retry, errors)

> **Отличие от S24:** S24 логирует метрики (cost, latency), S25 логирует debug-данные.
```

---

### **3.3. 📦 Scope**

Чёткое разграничение — что входит, что не входит.

**Для многофазных спринтов** группировать по фазам.

**Пример (из S25):**

```markdown
## Scope

### Входит:

**Phase 1 — Debug-данные:** ✅ DONE
- [x] Расширить `ai_pipeline_metrics` полями для debug (T174)
- [x] Обновить `record_ai_metric()` (T175)
- [x] API для получения debug-данных (T176)
- [x] UI для просмотра debug-данных (T177)

**Phase 2 — A/B тесты:** 🔵 Отложено
- [ ] Случайный выбор активной версии промпта
- [ ] UI для сравнения результатов по версиям

**Phase 3 — AI Count Validation Fixes:** 🟡 Active
- [x] Blur override в P6 (T197)
- [ ] Count ALL items including gray (T210)

### Не входит:

- Агрегированные метрики (это S24)
- Редактирование промптов (это S22)
- Алерты (это S24)
```

---

### **3.4. 🏗 Архитектура и структура**

Описать:
* Какие модули/файлы создаются или изменяются
* Как это встраивается в существующую систему
* Диаграммы взаимодействия (если нужно)

**Пример (из S25):**

```markdown
## Архитектура и структура

### Изменяемые файлы

```
backend/src/
├── database.py                    # + новые поля в AIPipelineMetric
├── services/
│   ├── openai_manager.py          # + расширение record_ai_metric()
│   └── prompt_service.py          # + A/B выбор версии (Phase 2)
└── api/routers/
    └── debug.py                   # NEW: API endpoints для debug

backend/src/demo/
└── dashboard.html                 # + UI для AI Debug
```

### Mapping: Step → Prompt → Метод

| Step | Prompt | Метод в openai_manager.py |
|------|--------|---------------------------|
| whisper | — | `speech_to_text_async` |
| screenshot_selection | p1_select_screenshots | `select_screenshots` |
| vision_analysis | p2_analyze_cleanliness | `analyze_item_condition` |
```
```

---

### **3.5. 🧱 Модели данных / БД**

**Только если спринт меняет схему БД.**

Описать:
* Какие модели SQLAlchemy создаются/изменяются
* Какие поля добавляются
* Какие индексы нужны
* Связи между таблицами
* SQL миграции (если нужны)

**Пример (из S25):**

```markdown
## Технические детали

### 1. Расширение модели данных

**Новые поля для таблицы `ai_pipeline_metrics`:**

```python
# S25: Debug-данные
prompt_name = Column(String(50))    # p6_compare_reference
prompt_version = Column(Integer)    # версия из таблицы prompts
input_data = Column(JSON)           # входные данные для AI
response = Column(JSON)             # полный ответ AI
result = Column(String(20))         # ok, retry, error
```

**Индексы:**
```sql
CREATE INDEX idx_metrics_prompt ON ai_pipeline_metrics(prompt_name, prompt_version);
CREATE INDEX idx_metrics_result ON ai_pipeline_metrics(result);
```
```

---

### **3.6. 📋 Задачи (Tasks)**

**Обязательная секция** — список всех задач спринта с их статусами.

Группировать по фазам (если есть), указывать зависимости.

**Пример (из S25):**

```markdown
## Задачи

### Phase 1 — Debug-данные

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T174 | [Расширить ai_pipeline_metrics](../3.%20Tasks/Done/S25.../T174_..._done.md) | — | ✅ 2025-12-24 |
| T175 | [Обновить record_ai_metric()](../3.%20Tasks/Done/S25.../T175_..._done.md) | T174 | ✅ 2025-12-25 |
| T176 | [API GET /api/debug/cleaning/{id}](../3.%20Tasks/Done/S25.../T176_..._done.md) | T175 | ✅ 2025-12-25 |

### Phase 3 — AI Count Validation Fixes

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T197 | [Blur override в P6](../3.%20Tasks/Done/...) | — | ✅ 2026-01-11 |
| T210 | [Count ALL items including gray](../3.%20Tasks/S25.../T210_...) | T203 | 🟡 To Do |
| T211 | [Fallback: parse description](../3.%20Tasks/S25.../T211_...) | T210 | 🔵 Backlog |
```

**Условные обозначения статусов:**
- ✅ — завершено (с датой)
- 🟡 — в работе (To Do / In Progress)
- 🔵 — в бэклоге / отложено
- ❌ — отменено

---

### **3.7. 🧪 Acceptance Criteria / DoD**

Список критериев, по которым можно считать спринт/фазу завершённой.

**Пример:**
```markdown
## DoD (Definition of Done)

### Phase 1 ✅ DONE
- [x] Все поля debug добавлены в ai_pipeline_metrics
- [x] 12 мест вызова record_ai_metric() обновлены
- [x] API /api/debug/cleaning/{id} работает
- [x] Dashboard UI показывает debug данные
- [x] Протестировано на production (cleaning #135+)

### Phase 3 (в работе)
- [x] T197 blur override deployed и работает
- [ ] T210 P6 prompt обновлён и протестирован с Zoya
- [ ] Acceptance rate для gray items вырос с 0% до 90%+
- [ ] Нет регрессии на bright items
```

---

### **3.8. 🔗 Связанные документы**

Ссылки на:
* Бизнес-требования (BR)
* Другие спринты (зависимости)
* Postmortem документы

**Пример:**
```
- BR: `docs/1. business requirements/BR_XX_<название>.md`
- Зависит от: `S18_tma_localization.md` (локализация)
- Блокирует: `S26_advanced_analytics.md` (требует debug-данные из S25)
- Postmortem: `docs/5. Unsorted/postmortem_cleaning_148.md` (AI gray items bug)
```

---

## 🧩 4. Принципы хорошей спецификации

### 4.1. Строгое разделение "что строим" и "как проверяем"
Scope ≠ Acceptance Criteria.
Scope описывает функционал, DoD — критерии готовности.

### 4.2. Reuse-first подход
Всегда писать:
* Что переиспользуем из существующей системы
* Что рефакторим
* Что удаляем/заменяем

**Пример:**
```
Переиспользуем:
- Существующие модели SQLAlchemy (User, Group, Cleaning)
- Сервисы интеграции (Airtable, Dropbox)
- Логику мониторинга в Pyrogram

Рефакторим:
- Создаём API-слой поверх существующих моделей

Не трогаем:
- Логику ботов (Pyrogram/Aiogram)
- Middleware ботов
```

### 4.3. Никакого избыточного "почему" — это в BR
Спецификация должна быть короткой и инженерной.
Подробное обоснование — в бизнес-требованиях.

### 4.4. Один спринт = один инкремент
Идеально, если после реализации спринта можно:
* Залить в прод
* Показать пользователю
* Получить фидбек

### 4.5. Стиль: точный, сухой, инженерный
Без лирики, без "наверное", без "возможно".
Конкретные решения и чёткие критерии.

### 4.6. Fail fast: никаких дефолтных значений
**Важно для проекта:** если данных нет — падаем с ошибкой, а не подставляем значения по умолчанию.

### 4.7. Observability: логируем всё важное
Каждая ошибка, каждое важное событие — в лог с контекстом.

---

## 📄 5. Готовый шаблон Sprint Specification

```markdown
# Sprint Specification: <Название фичи>

**ID:** SNN (например, S25)
**Статус:** 🟡 Active / ✅ Done / 🔵 Draft
**Версия:** 1.0
**Дата создания:** YYYY-MM-DD
**Автор:** <Имя>

---

## 🎯 Цель спринта

<1–2 абзаца: что решаем, зачем важно, какую проблему закрываем>

---

## 📦 Scope

### Входит:

**Phase 1 — <Название фазы>:** ✅ DONE / 🟡 Active / 🔵 Planned
- [x] Завершенная задача (T174)
- [ ] Активная задача (T210)
- [ ] Запланированная задача (T211)

**Phase 2 — <Название фазы>:** 🔵 Planned
- [ ] Задача 1
- [ ] Задача 2

### Не входит / Out of scope:
- ...
- ...

---

## 🏗 Архитектура и структура

Описать:
* Какие модули/компоненты затрагиваются
* Как это встраивается в существующую систему
* Диаграммы взаимодействия (опционально)

**Пример:**
```
### Изменения в AI pipeline

1. P6 prompt (count validation) — добавить инструкцию считать gray items
2. cleaning_worker.py — fallback парсинг description при count mismatch
3. ai_pipeline_metrics — debug поля уже добавлены (Phase 1)
```

---

## 🧱 Модели данных / БД

Описать изменения в базе данных (если есть).

**Пример:**
```markdown
### Таблица `ai_pipeline_metrics` (расширение)

**Новые поля:**
- `prompt_version` (Integer) — версия промпта для отладки
- `input_data` (JSON) — входные данные для AI
- `response` (JSON) — полный ответ AI

**Индексы:**
```sql
CREATE INDEX idx_metrics_prompt ON ai_pipeline_metrics(prompt_name, prompt_version);
```
```

---

## 📋 Задачи (Tasks)

**Обязательная секция** — список всех задач спринта с их статусами.

Группировать по фазам (если есть), указывать зависимости.

**Пример:**

```markdown
### Phase 1 — Debug-данные

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T174 | [Расширить ai_pipeline_metrics](../3.%20Tasks/Done/S25.../T174_..._done.md) | — | ✅ 2025-12-24 |
| T175 | [Обновить record_ai_metric()](../3.%20Tasks/Done/S25.../T175_..._done.md) | T174 | ✅ 2025-12-25 |

### Phase 2 — AI Count Validation Fixes

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T210 | [Count ALL items including gray](../3.%20Tasks/S25.../T210_...) | T203 | 🟡 To Do |
| T211 | [Fallback: parse description](../3.%20Tasks/S25.../T211_...) | T210 | 🔵 Backlog |
```

**Условные обозначения статусов:**
- ✅ — завершено (с датой)
- 🟡 — в работе (To Do / In Progress)
- 🔵 — в бэклоге / отложено
- ❌ — отменено

---

## 🧪 Acceptance Criteria / DoD

Список критериев, по которым можно считать спринт/фазу завершённой.

**Пример:**
```markdown
### Phase 1 ✅ DONE
- [x] Все поля debug добавлены в ai_pipeline_metrics
- [x] 12 мест вызова record_ai_metric() обновлены
- [x] API /api/debug/cleaning/{id} работает
- [x] Протестировано на production (cleaning #135+)

### Phase 2 (в работе)
- [x] T210 P6 prompt обновлён и протестирован с клинером
- [ ] Acceptance rate для gray items вырос с 0% до 90%+
- [ ] Нет регрессии на bright items
```

---

## 🧪 Тест-план (опционально)

Для сложных спринтов — описать сценарии тестирования.

**Пример:**
```
### Production testing

1. Deploy T210 (P6 prompt update)
2. Ask Zoya to test on object 999 (coffee cups, bowls)
3. Check database:
   ```sql
   SELECT item_id, status, retry_count, retry_reason
   FROM items WHERE cleaning_id = [latest_cleaning_id]
   ```
4. Expected: status='ok', retry_count=0, acceptance_rate >= 90%
```

---

## ⚠️ Риски и ограничения (опционально)

Зафиксировать потенциальные проблемы.

**Пример:**
```
- **Риск:** Изменение P6 prompt может вызвать регрессию на bright items → мониторить acceptance rate
- **Ограничение:** Fallback парсинг работает только для "Three mugs", "Two bowls" формата
```

---

## 🔗 Связанные документы

- BR: `docs/1. business requirements/BR_XX_<название>.md`
- Зависит от: `SNN_<название>.md` (другие спринты)
- Блокирует: `SNN_<название>.md`
- Postmortem: `docs/5. Unsorted/<название>.md` (если есть)
```

---

## ✅ 6. Чек-лист перед публикацией спецификации

### Для Sprint Specification (SNN):

- [ ] Заполнен заголовок (ID, статус, версия, дата, автор)
- [ ] Описана цель спринта (1–2 абзаца, какую проблему решаем)
- [ ] Чётко определён scope (что входит / что не входит)
- [ ] Описана архитектура и структура (какие модули/компоненты затрагиваются)
- [ ] Описаны модели данных / изменения в БД (если есть)
- [ ] **Обязательно:** перечислены все задачи (TNN) с зависимостями и статусами
- [ ] Написаны acceptance criteria (DoD) для каждой фазы
- [ ] Указаны риски и ограничения (опционально)
- [ ] Добавлены ссылки на связанные документы (BR, другие спринты, postmortem)

---

## 📚 7. Рекомендации по работе со спецификациями

### 7.1. Версионирование

При изменении спецификации:
1. Обновите **Версию** (например, 1.0 → 1.1)
2. Укажите **Дату** изменения
3. Добавьте секцию **История изменений** в конце документа:

```markdown
## 📝 История изменений

### v1.1 (2026-01-15)
- Добавлена Phase 3: AI Count Validation Fixes
- Добавлены задачи T210 и T211

### v1.0 (2025-12-20)
- Первая версия спецификации
```

### 7.2. Статусы спринта

- **🔵 Draft** — черновик, обсуждается
- **🟡 Active** — в разработке
- **🟢 Review** — на ревью
- **✅ Done** — реализовано и принято

### 7.3. Naming conventions

**Sprint Specifications (SNN):**
```
S01_dual_bot_architecture.md
S18_tma_localization.md
S25_ai_analytics_debug.md
```

**Нумерация:**
- Двузначный номер (01, 02, ..., 99)
- Хронологическая (увеличивается с новыми спринтами)
- `snake_case` для названия (только латиница, строчные буквы)

См. подробнее: [doc_conventions.md](./doc_conventions.md)

### 7.4. Где хранить

**Спринты (SNN):**
```
docs/2. Specifications/
├── S01_dual_bot_architecture.md
├── S18_tma_localization.md
├── S25_ai_analytics_debug.md
└── ...
```

**Задачи (TNN):**
```
docs/3. Tasks/
├── S25_ai_analytics_debug/
│   ├── T210_s25_p6_count_all_items.md
│   └── T211_s25_fallback_parse_description.md
└── Done/
    └── S25_ai_analytics_debug_done/
        ├── T174_s25_extend_ai_metrics_done.md
        └── T175_s25_record_ai_metric_done.md
```

---

## 🎓 8. Заключение

Этот гайд поможет команде создавать **единообразные, чёткие и полные спецификации** для спринтов.

**Ключевые принципы:**
- Один спринт (SNN) = один функциональный инкремент
- Спринт группирует задачи (TNN) по фазам
- Никаких дефолтных значений (fail fast)
- Строгое разделение scope / acceptance criteria
- Reuse-first подход
- Инженерный, сухой стиль
- Observability: логируем всё важное

**При возникновении вопросов:**
- Посмотрите примеры в этом гайде (S25, T210, T211)
- Изучите [doc_conventions.md](./doc_conventions.md) для правил именования
- Изучите [task_decomposition_guide.md](./task_decomposition_guide.md) для детализации задач
- Задайте вопрос команде на ревью
- Обновите этот гайд, если нашли улучшения

**Удачи в разработке!** 🚀


