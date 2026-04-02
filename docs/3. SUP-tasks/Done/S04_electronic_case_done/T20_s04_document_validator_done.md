Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

**Статус:** ✅ Выполнено
**Дата закрытия:** 2026-03-31

# T20_s04_document_validator — Модуль проверки документов

## Customer-facing инкремент

Клиент получает мгновенную обратную связь о загруженном документе: принят ли он, и если нет — почему, прямо в Telegram.

## Цель

Создать `services/document_validator.py` — асинхронный сервис трёхуровневой проверки документов из папки клиента в Bitrix. Проверка запускается при появлении нового файла (триггер из T19) и не блокирует чат.

## Результат выполнения

- `services/document_validator.py` — NEW: `DocumentValidator.process_deal_files()`, 3-уровневая проверка (формат → Vision → checklist), промпт с 18 типами документов
- Интеграция в `webhook_server.py` — `asyncio.create_task` после upsert (неблокирующий)
- `bot.py` — инициализация `DocumentValidator`, передача в webhook app
- `requirements.txt` — добавлены `PyMuPDF>=1.24.0`, `Pillow>=10.0.0`
- Исправления в ходе тестирования:
  - `disk.storage.getforcrm` не существует → заменён на поиск по имени папки в shared disk (id=19)
  - Сканирование всех подпапок → только `Неразобранное` (клиентские загрузки)
  - `checklist_completion` тип `integer` → `numeric(5,4)` в Supabase
  - `asyncio.create_task` глотал исключения → обёрнут в `try/except` с логом
  - Пересчёт `checklist_completion` теперь происходит всегда, даже если новых файлов нет

## Результаты теста (deal_id=275098, Аксенов Константин Анатольевич)

| Файл | Статус | doc_type |
|---|---|---|
| Аксенов паспорт.pdf | ✅ verified | passport |
| Инн Аксенов.pdf | ✅ verified | inn_certificate |
| Снилс Аксенов.pdf | ✅ verified | pension_certificate |
| Аксенов Анкета.pdf | ❌ rejected | нечитаем |
| Договор БФЛ.pdf | ❌ rejected | нечитаем |

`checklist_completion = 0.1667` (3/18 типов верифицировано)

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T17, T19
