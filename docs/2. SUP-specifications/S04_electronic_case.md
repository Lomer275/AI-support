# S04: Электронное дело клиента

**Статус:** 🔵 Draft
**Версия:** 1.0
**Дата создания:** 2026-03-30
**BR:** [BR01_ai_manager_bfl.md](../1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md)

---

## 🎯 Цель

ИИ-агенты сейчас получают контекст из двух разрозненных источников: Bitrix24 (сделка, поля) и Support Supabase (судебные документы). Каждый запрос в Bitrix — дорогостоящий batch API-вызов; часть данных не загружается вовсе. В результате агенты не знают реальный статус платежей клиента, историю переписки с МС, конкретный чеклист документов, данные арбитражного управляющего — и галлюцинируют.

Цель спринта — создать **единый источник контекста** для ИИ-агентов: отдельный Supabase-проект `electronic_case`, который синхронизируется с Bitrix через вебхуки и содержит полный профиль клиента. Bitrix убирается из цепочки чата — агенты делают один быстрый SELECT вместо дорогих API-вызовов.

**Область работы ИИ-менеджера:** стадия «Исковое заявление» → «Списание долгов».

---

## 📦 Scope

### Входит:

**Phase 1 — База данных и схема:** 🔵 Planned
- [ ] Создать новый Supabase-проект `electronic_case` (T17)
- [ ] Создать таблицы: `cases`, `property`, `debts`, `payments`, `documents`, `communications` (T17)

**Phase 2 — Начальная синхронизация (1 раз):** 🔵 Planned
- [ ] Скрипт `scripts/sync_bitrix_to_cases.py`: batch-выгрузка ~1000 активных сделок из Bitrix → заполнение всех таблиц (T18)

**Phase 3 — Постоянная синхронизация (вебхуки):** 🔵 Planned
- [ ] Расширить `webhook_server.py`: обработка `onCrmDealUpdate` → обновление `cases`, `documents`, `communications` (T19)

**Phase 4 — Модуль проверки документов:** 🔵 Planned
- [ ] Создать `services/document_validator.py`: 3-уровневая проверка (фильтр → GPT-4o-mini Vision → полнота чеклиста) (T20)
- [ ] Уведомление клиенту в Telegram при отклонении документа (T21)

**Phase 5 — Сервис и интеграция с агентами:** 🔵 Planned
- [ ] Создать `services/electronic_case.py`: `get_case_context()`, `get_checklist_status()` (T22)
- [ ] Инжектировать контекст электронного дела во все R1/R2/Coordinator промпты, заменить `BitrixService.get_deal_profile()` в чате (T23)

### Не входит:

- Сбор документов (34 пункта чеклиста) — это задача МС-человека, бот подключается позже
- Проверка юридической корректности содержимого документов — задача юриста
- Интерфейс для операторов — они работают в Bitrix как раньше
- Поддержка 10-значного ИНН (юрлица) — не в scope

---

## 🏗 Архитектура и структура

### Поток данных

```
Bitrix24 ──(onCrmDealUpdate webhook)──► webhook_server.py ──► electronic_case Supabase
                                                                       │
                                               ┌───────────────────────┤
                                               ▼                       ▼
                                    ElectronicCaseService      DocumentValidator
                                               │
                              ┌────────────────┼────────────────┐
                              ▼                ▼                ▼
                           R1 agents       R2 agents      Coordinator
```

### Изменяемые файлы

```
services/
├── electronic_case.py       # NEW: единый сервис контекста для агентов
├── document_validator.py    # NEW: 3-уровневая проверка документов
└── support.py               # EDIT: заменить get_deal_profile() на ElectronicCaseService

webhook_server.py            # EDIT: добавить обработчик onCrmDealUpdate
bot.py                       # EDIT: инициализация ElectronicCaseService

scripts/
└── sync_bitrix_to_cases.py  # NEW: разовый скрипт начальной синхронизации
```

### Reuse-first

**Переиспользуем:**
- `webhook_server.py` — уже запущен на порту 8080, добавляем новый обработчик
- `BitrixService` — используется только в скрипте синхронизации и `webhook_server.py`, из чата уходит
- `SupportSupabaseService` — без изменений, `smart_process_kad_arbitr` остаётся как есть
- `chat_history` — без изменений

**Не трогаем:**
- Пайплайн R1 → R2 → Coordinator (структура)
- Авторизацию (S01)
- Эскалацию (S03)

---

## 🧱 Модели данных

### `cases` — профиль клиента (1 строка = 1 активная сделка)

```sql
inn                     TEXT PRIMARY KEY
deal_id                 TEXT
chat_id                 TEXT
stage                   TEXT
stage_updated_at        TIMESTAMPTZ

-- Личные данные
full_name               TEXT
phone                   TEXT
birth_date              DATE
city                    TEXT            -- для определения суда

-- Семья
marital_status          TEXT            -- married/single/divorced
dependents_count        INT

-- Финансы
total_debt_amount       NUMERIC
creditors_count         INT
monthly_loan_payment    NUMERIC
official_income         NUMERIC
current_employer        TEXT
income_change_reason    TEXT
salary_bank             TEXT

-- АУ (после введения процедуры)
au_income_amount        NUMERIC
au_income_method        TEXT
au_income_bank          TEXT
au_debtor_status        TEXT

-- Имущество (флаги)
has_property            BOOLEAN
property_count          INT
has_pledge              BOOLEAN
property_removal_before_court  BOOLEAN
au_property_to_sell     TEXT
au_property_excluded    TEXT

-- Договор
contract_number         TEXT
contract_date           DATE
contract_amount         NUMERIC
monthly_payment_amount  NUMERIC
payments_count          INT
prepayment_amount       NUMERIC
prepayment_date         DATE
paid_to_date            NUMERIC
payment_schedule        JSONB           -- [{amount, date}, ...] до 13 платежей

-- Судебная процедура
court_region            TEXT
filing_planned_date     TIMESTAMPTZ
filing_actual_date      DATE
first_hearing_date      DATE
last_hearing_date       DATE
suspended_date          DATE
au_docs_sent_date       DATE
arbitration_manager     TEXT
court_expenses_paid     BOOLEAN
folder_url              TEXT

-- Риски
risk_flags              JSONB
-- {transactions_3y, was_ip, has_llc_shares, has_guarantor,
--  alimony_debt, has_court_orders, gray_income, property_transfer}

-- Служебные
checklist_completion    INT             -- % заполненности чеклиста (0–100)
synced_at               TIMESTAMPTZ
created_at              TIMESTAMPTZ
```

### `property` — имущество

```sql
id                  UUID PRIMARY KEY
inn                 TEXT REFERENCES cases(inn)
type                TEXT    -- real_estate / vehicle / other
description         TEXT
area_sqm            NUMERIC
address             TEXT
brand_model         TEXT
year                INT
estimated_value     NUMERIC
acquired_at         DATE
preservation_strategy TEXT
```

### `debts` — долги

```sql
id                  UUID PRIMARY KEY
inn                 TEXT REFERENCES cases(inn)
creditor_name       TEXT
amount              NUMERIC
overdue_days        INT
has_enforcement     BOOLEAN
fssp_restrictions   JSONB   -- {card_arrest, income_garnishment}
```

### `payments` — история платежей (из квитанций-чеков в папке Bitrix)

```sql
id                  UUID PRIMARY KEY
inn                 TEXT REFERENCES cases(inn)
type                TEXT    -- monthly / court_deposit / publication_fee / other
amount              NUMERIC
payment_date        DATE
receipt_file_id     UUID REFERENCES documents(id)
status              TEXT    -- received / verified / missing
```

### `documents` — чеклист и файлы

```sql
id                  UUID PRIMARY KEY
inn                 TEXT REFERENCES cases(inn)
doc_type            TEXT
file_name           TEXT
bitrix_file_id      TEXT
storage_path        TEXT    -- заполняется только после валидации (Supabase Storage)
checklist_item      TEXT
source              TEXT    -- bitrix_folder / kad_arbitr / efrsb / manual
status              TEXT    -- pending / verified / rejected / not_applicable
rejection_reason    TEXT
verified_at         TIMESTAMPTZ
uploaded_at         TIMESTAMPTZ
```

**Из папки Bitrix загружаем:** квитанции оплаты, договор, график платежей, документы по имуществу.
**Не загружаем:** паспорт, СНИЛС, 2-НДФЛ и прочие личные документы — агенту не нужны.
**`smart_process_kad_arbitr`** (судебные акты) — остаётся в существующем Support Supabase без изменений.

### `communications` — переписки

```sql
id              UUID PRIMARY KEY
inn             TEXT REFERENCES cases(inn)
source          TEXT    -- bitrix_comment / open_lines
content         TEXT
author_type     TEXT    -- manager / lawyer / operator / client
author_name     TEXT
created_at      TIMESTAMPTZ
bitrix_id       TEXT    -- для дедупликации
```

---

## 📋 Задачи

### Phase 1 — База данных

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T17 | Создать Supabase-проект `electronic_case` + все таблицы + индексы | — | 🔵 Planned |

### Phase 2 — Начальная синхронизация

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T18 | `scripts/sync_bitrix_to_cases.py`: batch-выгрузка ~1000 сделок | T17 | 🔵 Planned |

### Phase 3 — Вебхуки

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T19 | Расширить `webhook_server.py`: `onCrmDealUpdate` → обновление `electronic_case` | T17 | 🔵 Planned |

### Phase 4 — Модуль проверки документов

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T20 | `services/document_validator.py`: фильтр → GPT-4o-mini Vision → чеклист | T17 | 🔵 Planned |
| T21 | Уведомление клиенту в Telegram при `rejected` документе | T20 | 🔵 Planned |

### Phase 5 — Сервис и интеграция

| ID | Задача | Зависит от | Статус |
|----|--------|------------|--------|
| T22 | `services/electronic_case.py`: `get_case_context()`, `get_checklist_status()` | T17 | 🔵 Planned |
| T23 | Инжект контекста в R1/R2/Coordinator; заменить `get_deal_profile()` в чате | T22 | 🔵 Planned |

---

## 🧪 DoD (Definition of Done)

### Phase 1
- [ ] Все 6 таблиц созданы в Supabase-проекте `electronic_case`
- [ ] Индексы на `inn`, `deal_id`, `chat_id` есть

### Phase 2
- [ ] Скрипт отрабатывает без ошибок на всех ~1000 сделках
- [ ] Незаполненные поля Bitrix → `NULL` (не ошибка)
- [ ] `synced_at` проставлен у всех записей

### Phase 3
- [ ] Смена стадии сделки в Bitrix → `cases.stage` обновляется в течение 10 секунд
- [ ] Дублирующие вебхуки не создают дублей в БД

### Phase 4
- [ ] `verified` документ копируется в Supabase Storage
- [ ] `rejected` документ не копируется, клиент получает Telegram-сообщение с причиной
- [ ] `checklist_completion` пересчитывается после каждой проверки

### Phase 5
- [ ] Агенты отвечают точной датой заседания (из `first_hearing_date`), а не выдумывают
- [ ] Агенты показывают конкретные ❌ документы из чеклиста, а не общий список
- [ ] `BitrixService.get_deal_profile()` больше не вызывается в `SupportService.answer()`
- [ ] При `NULL` полях агент пишет `[не заполнено в CRM]`, не галлюцинирует

---

## ⚠️ Риски и ограничения

- **МС заполняют минимум полей** — большинство полей в `cases` будут `NULL`. Агенты обязаны обрабатывать `NULL` gracefully, явно показывая `[не заполнено в CRM]`.
- **Вебхуки Bitrix** — могут приходить с задержкой или дублями. Нужна дедупликация по `bitrix_id` и идемпотентные upsert-операции.
- **GPT-4o-mini Vision** — ~$27/мес при текущей нагрузке. При росте базы > 2000 клиентов пересмотреть.
- **Папка клиента в Bitrix** — структура папки не стандартизирована между МС, фильтрация по `doc_type` потребует итерации после анализа реальных папок.

---

## 🔗 Связанные документы

- BR: [BR01_ai_manager_bfl.md](../1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md)
- Зависит от: S02 (мульти-агентный пайплайн), S03 (качество + эскалация)
- Блокирует: S05 (проактивные уведомления — потребует данные из `electronic_case`)
- Поля Bitrix: [docs/5. SUP-unsorted/Поля сделки Bitrix](../5.%20SUP-unsorted/Поля%20сделки%20Bitrix)
