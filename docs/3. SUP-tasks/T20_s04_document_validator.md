Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

# T20_s04_document_validator — Модуль проверки документов

## Customer-facing инкремент

Клиент получает мгновенную обратную связь о загруженном документе: принят ли он, и если нет — почему, прямо в Telegram.

## Цель

Создать `services/document_validator.py` — асинхронный сервис трёхуровневой проверки документов из папки клиента в Bitrix. Проверка запускается при появлении нового файла (триггер из T19) и не блокирует чат.

## Scope

- Новый файл `services/document_validator.py`
- **Уровень 1 — Фильтр:** по типу и имени файла определить, нужен ли документ в базу. Релевантны: квитанции, договор, график платежей, документы по имуществу. Нерелевантны: системные файлы, технические вложения.
- **Уровень 2 — Vision:** отправить файл в GPT-4o-mini Vision с промптом "Определи тип документа. Ожидается: {expected_type}". Результат: `matched` / `wrong_type` / `unreadable`
- **Уровень 3 — Чеклист:** пересчитать `cases.checklist_completion` (%) после каждой проверки
- Обновить статус в `documents`: `verified` / `rejected` / `not_applicable`
- При `verified` — сохранить метаданные файла (`bitrix_file_id`, `file_name`); физическую копию пока не делать (решение по Storage откладывается)
- Вызывать уведомление клиента при `rejected` (реализуется в T21)
- Использовать `OPENAI_MODEL` (или отдельную переменную `OPENAI_MODEL_VALIDATOR=gpt-4o-mini`)

## Out of scope

- Копирование файлов в Supabase Storage (решение отложено)
- Проверка юридической корректности содержимого документов
- Проверка документов из `smart_process_kad_arbitr` (судебные акты)
- Синхронная проверка (только async, не блокирует чат)

## Технические детали

```python
class DocumentValidator:

    async def validate(self, inn: str, file_id: str, expected_type: str) -> str:
        """Возвращает: 'verified' | 'rejected' | 'not_applicable'"""
        # 1. Фильтр по типу файла
        # 2. Скачать файл из Bitrix по file_id
        # 3. Отправить в GPT-4o-mini Vision
        # 4. Обновить documents.status
        # 5. Пересчитать cases.checklist_completion
        # 6. Если rejected → вернуть статус (T21 отправит уведомление)
```

Промпт для Vision:
```
Ты проверяешь документ клиента для процедуры банкротства.
Ожидаемый тип: {expected_type}.
Определи:
1. Это тот документ? (matched/wrong_type)
2. Документ читаем? (readable/unreadable)
Ответь JSON: {"match": "matched|wrong_type", "readable": true|false, "reason": "..."}
```

## Как протестировать

1. Загрузить тестовый файл в папку любой сделки в Bitrix
2. Убедиться что вебхук T19 создал запись в `documents` со статусом `pending`
3. Вручную вызвать `DocumentValidator.validate()` с этим `file_id`
4. Проверить что статус в `documents` обновился
5. Загрузить заведомо неверный документ (например, фото природы вместо квитанции)
6. Убедиться что статус `rejected` и `rejection_reason` заполнен
7. Проверить что `cases.checklist_completion` пересчитался

## Критерии приёмки

1. Валидный документ → статус `verified`, `rejection_reason = NULL`
2. Неверный тип → статус `rejected`, `rejection_reason` заполнен понятным текстом
3. Нечитаемый файл → статус `rejected`, причина "нечитаемо"
4. `cases.checklist_completion` пересчитывается после каждой проверки
5. Проверка асинхронная — не блокирует ответы бота в чате
6. Исключения (недоступен OpenAI, недоступен Bitrix) логируются, статус документа остаётся `pending`

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T17, T19
