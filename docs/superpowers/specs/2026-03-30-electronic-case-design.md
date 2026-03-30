# S04 — Электронное дело

**Версия:** 1.0
**Дата:** 2026-03-30
**Статус:** Draft

## Цель

Создать единый источник контекста для ИИ-агентов — полный профиль клиента с документами, платёжной историей, статусом процедуры банкротства и переписками. Устранить зависимость агентов от Bitrix во время чата, снизить стоимость запросов, устранить галлюцинации из-за отсутствия данных.

**Область работы ИИ-менеджера:** от стадии "Исковое заявление" до "Списание долгов".

---

## Архитектурное решение

Новый отдельный Supabase-проект `electronic_case`. Данные синхронизируются из Bitrix через вебхуки (push). Разовая начальная синхронизация всех активных сделок.

Агенты читают только из `electronic_case` — Bitrix из цепочки чата уходит.

```
Bitrix24 ──(webhook onCrmDealUpdate)──► webhook_server.py ──► electronic_case Supabase
                                                                      │
                                              ┌───────────────────────┤
                                              ▼                       ▼
                                   ElectronicCaseService      DocumentValidator
                                              │
                                              ▼
                                    R1 / R2 / Coordinator agents
```

---

## База данных

### `cases` — профиль клиента (1 строка = 1 активная сделка)

```sql
inn                     TEXT PRIMARY KEY
deal_id                 TEXT            -- Bitrix deal ID
chat_id                 TEXT            -- Telegram chat_id
stage                   TEXT            -- текущая стадия воронки
stage_updated_at        TIMESTAMPTZ

-- Личные данные
full_name               TEXT
phone                   TEXT
birth_date              DATE
city                    TEXT            -- город прописки (для суда)

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
paid_to_date            NUMERIC         -- оплачено по договору на текущую дату
payment_schedule        JSONB           -- [{amount, date}, ...] до 13 платежей

-- Судебная процедура
court_region            TEXT
filing_planned_date     TIMESTAMPTZ
filing_actual_date      DATE
first_hearing_date      DATE
last_hearing_date       DATE
suspended_date          DATE            -- оставлено без движения
au_docs_sent_date       DATE
arbitration_manager     TEXT            -- ФИО арбитражного управляющего
court_expenses_paid     BOOLEAN
folder_url              TEXT            -- ссылка на папку клиента в Bitrix

-- Риски (JSONB)
risk_flags              JSONB
-- {
--   transactions_3y: bool,     сделки за 3 года
--   was_ip: bool,              был ИП
--   has_llc_shares: bool,      доли в ООО
--   has_guarantor: bool,       поручитель
--   alimony_debt: bool,        долг по алиментам
--   has_court_orders: bool,    судебные приказы
--   gray_income: bool,         серый доход
--   property_transfer: bool    имущество на родственников
-- }

-- Служебные
checklist_completion    INT             -- % заполненности чеклиста документов
created_at              TIMESTAMPTZ
synced_at               TIMESTAMPTZ     -- последняя синхронизация с Bitrix
```

### `property` — имущество клиента

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
preservation_strategy TEXT  -- стратегия сохранения
```

### `debts` — долговые обязательства

```sql
id                  UUID PRIMARY KEY
inn                 TEXT REFERENCES cases(inn)
creditor_name       TEXT
amount              NUMERIC
overdue_days        INT
has_enforcement     BOOLEAN             -- исполнительное производство
fssp_restrictions   JSONB               -- {card_arrest, income_garnishment}
```

### `payments` — история платежей

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
doc_type            TEXT    -- passport / snils / 2ndfl / contract / payment_schedule
                            -- property_docs / receipt_deposit / receipt_publication
                            -- court_act / au_report / ...
file_name           TEXT
bitrix_file_id      TEXT    -- ссылка на оригинал в Bitrix
storage_path        TEXT    -- путь в Supabase Storage (только после валидации)
checklist_item      TEXT    -- номер пункта в чеклисте
source              TEXT    -- bitrix_folder / kad_arbitr / efrsb / manual
status              TEXT    -- pending / verified / rejected / not_applicable
rejection_reason    TEXT
verified_at         TIMESTAMPTZ
uploaded_at         TIMESTAMPTZ
```

**Какие документы из папки Bitrix загружаются:**
- ✅ Квитанции оплаты (депозит суда, публикация, ежемесячные платежи)
- ✅ Договор с клиентом
- ✅ График платежей
- ✅ Документы по имуществу
- ❌ Личные документы (паспорт, СНИЛС, 2-НДФЛ — агенту не нужны)

**Документы из `smart_process_kad_arbitr`** (уже существует):
- Судебные акты с kad.arbitr.ru, ЕФРСБ и аналогичных источников остаются в существующей таблице
- Фильтрация ненужных документов — отдельная задача при реализации

### `communications` — переписки

```sql
id              UUID PRIMARY KEY
inn             TEXT REFERENCES cases(inn)
source          TEXT    -- bitrix_comment / open_lines
content         TEXT
author_type     TEXT    -- manager / lawyer / operator / client
author_name     TEXT
created_at      TIMESTAMPTZ
bitrix_id       TEXT    -- внешний ID для дедупликации
```

**Источники:**
- Комментарии МС/юриста из карточки сделки Bitrix
- Чат с оператором через Open Lines (ImConnector)

---

## Синхронизация

### Начальная (1 раз)

Скрипт `scripts/sync_bitrix_to_cases.py`:

1. Тянет все активные сделки (`CATEGORY_ID=4`, `STAGE_SEMANTIC_ID=P`)
2. Для каждой сделки — batch-запрос: сделка + контакт + задача чеклиста
3. Заполняет все таблицы; незаполненные поля Bitrix → `NULL` (не ошибка)
4. ~1000 сделок, разовый запуск

### Постоянная (вебхуки)

Расширение существующего `webhook_server.py` (порт 8080):

| Событие Bitrix | Действие |
|---|---|
| `onCrmDealUpdate` — смена стадии | `cases.stage` + `stage_updated_at` |
| `onCrmDealUpdate` — поле изменилось | соответствующее поле в `cases` |
| Задача обновлена (чеклист) | `documents.status` |
| Файл добавлен в папку | запуск `DocumentValidator` |
| Комментарий добавлен | `communications` |

---

## Модуль проверки документов

`services/document_validator.py` — асинхронный, не блокирует чат.

### 3 уровня проверки

**Уровень 1 — Нужен ли документ?**
Фильтр по типу файла. Квитанции, договор, имущество, судебные акты → проходят. Системные/технические файлы Bitrix → отклоняются без сохранения.

**Уровень 2 — Тот ли это документ?** (GPT-4o-mini Vision)
```
Загрузить файл из Bitrix → отправить в OpenAI:
"Определи тип документа. Ожидается: {expected_type}."
Результат: matched / wrong_type / unreadable
```

**Уровень 3 — Полнота чеклиста**
После каждой проверки пересчитывает `cases.checklist_completion` (%).

### Результаты

| Статус | Действие |
|---|---|
| `verified` | Копия → Supabase Storage, чеклист ✅ |
| `wrong_type` | Только метаданные, файл не копируется, уведомление клиенту |
| `unreadable` | Только метаданные, уведомление "нечитаемо, пересними" |
| `not_applicable` | МС пометил причину → документ исключён из чеклиста |

### Уведомление клиенту при отклонении
```
Триггер: status IN (wrong_type, unreadable)
→ bot.py → Telegram:
"[Имя], документ '[название]' не принят: {причина}. Загрузите заново."
```

### Стоимость
- GPT-4o-mini Vision: ~$0.0003/документ
- ~$27/мес при 1000 активных клиентах и ~100 новых/мес
- Supabase Pro (новый проект): $25/мес

---

## Интеграция с ИИ-агентами

### Новый сервис `services/electronic_case.py`

```python
class ElectronicCaseService:

    async def get_case_context(self, inn: str) -> str:
        """Форматированный контекст для всех агентов. Один SELECT."""

    async def get_checklist_status(self, inn: str) -> str:
        """Статус документов: что сдано, что нет, что не применимо."""
```

### Формат контекста для агентов

```
[ЭЛЕКТРОННОЕ ДЕЛО КЛИЕНТА]
Клиент: Иванов Иван Иванович
Стадия: Исковое заявление (с 15.03.2026)
Арбитражный управляющий: Петров А.В.
Регион суда: Краснодарский край
Дата подачи иска: 10.03.2026
Первое заседание: 25.04.2026

Долги: 1 250 000 ₽, кредиторов: 3
Имущество: автомобиль (стратегия: сохранение через ДКП)
Ежемесячный платёж по договору: 8 000 ₽, следующий: 01.04.2026
Оплачено по договору: 32 000 ₽

Документы (18/34 — 53%):
✅ Паспорт, СНИЛС, ИНН, 2-НДФЛ, договор, квитанция депозита
❌ Справка из ПФР, Выписка ЕГРН, квитанция публикации
⚪ Свидетельство о браке [не применимо — не в браке]

[Не заполнено в CRM: официальный доход, состав семьи]
```

### Приоритет источников

`ElectronicCaseService` — основной источник для агентов.
`BitrixService.get_deal_profile()` — резервный, только если `electronic_case` пуст.
Bitrix из цепочки чата постепенно уходит.

### Что улучшается для клиентов

| Вопрос клиента | До | После |
|---|---|---|
| "Когда моё заседание?" | Галлюцинация | `first_hearing_date` из дела |
| "Какие документы ещё нужны?" | Общий список | Конкретные ❌ из чеклиста |
| "Сколько я уже заплатил?" | Не знал | `paid_to_date` из дела |
| "Кто мой управляющий?" | Мог выдумать | `arbitration_manager` из дела |
| "Какой статус моего дела?" | Общие фразы | Точная стадия + дата перехода |

---

## Что остаётся без изменений

- `smart_process_kad_arbitr` — судебные документы с kad.arbitr.ru / ЕФРСБ (существующая таблица, агенты читают как раньше, добавить только фильтрацию ненужных документов)
- `chat_history` — история чата (без изменений)
- `SupportSupabaseService` — без изменений
- Операторы работают в Bitrix как раньше, в `electronic_case` не ходят

---

## Ограничения

- Данные актуальны насколько быстро Bitrix присылает вебхуки (обычно секунды)
- МС заполняют минимум полей → многие поля будут `NULL`; агенты обрабатывают `NULL` без паники, явно показывают "[не заполнено в CRM]"
- Модуль проверки документов не проверяет юридическую корректность содержимого — это задача юриста
- Поддерживается только 12-значный ИНН физлица (как и в боте)
