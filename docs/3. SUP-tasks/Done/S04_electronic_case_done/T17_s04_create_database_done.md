Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

**Статус:** ✅ Выполнено
**Дата закрытия:** 2026-03-30

# T17_s04_create_database — Создать Supabase-проект и схему БД

## Customer-facing инкремент

ИИ-агент может получить данные клиента из единой базы одним запросом — без обращений в Bitrix.

## Цель

Создать новый Supabase-проект `electronic_case` со всеми таблицами, индексами и RLS-политиками. Это фундамент для всех остальных задач S04.

## Scope

- Создать новый Supabase-проект (вручную через UI или Supabase CLI)
- Создать 6 таблиц: `cases`, `property`, `debts`, `payments`, `documents`, `communications`
- Создать индексы: на `inn`, `deal_id`, `chat_id`, `source`, `status`
- Добавить переменные окружения в `.env`:
  - `SUPABASE_CASES_URL`
  - `SUPABASE_CASES_ANON_KEY`
- Добавить `SUPABASE_CASES_URL` и `SUPABASE_CASES_ANON_KEY` в `docker-compose.yml`

## Out of scope

- Наполнение данными (это T18)
- Подключение сервиса к боту (это T22)
- RLS политики сложнее anon read/write (достаточно для внутреннего сервиса)

## Схема таблиц

Полная схема описана в спецификации S04, секция "Модели данных".

Ключевые индексы:
```sql
CREATE INDEX idx_cases_deal_id ON cases(deal_id);
CREATE INDEX idx_cases_chat_id ON cases(chat_id);
CREATE INDEX idx_documents_inn ON documents(inn);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_communications_inn ON communications(inn);
```

## Как протестировать

1. Открыть Supabase-проект `electronic_case` в UI
2. Убедиться что все 6 таблиц присутствуют
3. Выполнить тестовую вставку:
   ```sql
   INSERT INTO cases (inn, full_name, stage) VALUES ('123456789012', 'Тест Тестович', 'Исковое');
   SELECT * FROM cases WHERE inn = '123456789012';
   ```
4. Убедиться что запись вернулась корректно
5. Удалить тестовую запись
6. Проверить что `python bot.py` стартует без ошибок с новыми переменными окружения

## Критерии приёмки

1. Все 6 таблиц созданы и доступны
2. Все индексы созданы
3. Переменные `SUPABASE_CASES_URL` и `SUPABASE_CASES_ANON_KEY` добавлены в `.env` и `docker-compose.yml`
4. Тестовая вставка/чтение работают без ошибок
5. Бот стартует без ошибок

## Связанные документы

- Спека: [S04_electronic_case.md](../../../2.%20SUP-specifications/S04_electronic_case.md)
- BR: [BR01_ai_manager_bfl.md](../../../1.%20SUP-business%20requirements/BR01_ai_manager_bfl.md)
