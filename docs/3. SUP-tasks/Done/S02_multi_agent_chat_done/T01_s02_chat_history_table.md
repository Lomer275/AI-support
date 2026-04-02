Дата: 2026-03-20
Статус: ✅ done
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T01 — Создать таблицу `chat_history` в Supabase support

## Customer-facing инкремент

Подготовка инфраструктуры для памяти диалога — Алина сможет помнить предыдущие вопросы клиента в рамках сессии.

## Цель

Создать таблицу `chat_history` в Supabase-проекте `sgsxxmxybcysvbfsohau` (Support) с индексом для быстрой выборки последних сообщений.

## DDL

```sql
CREATE TABLE chat_history (
    id         bigserial PRIMARY KEY,
    chat_id    bigint      NOT NULL,
    role       text        NOT NULL CHECK (role IN ('user', 'assistant')),
    content    text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_history_chat_id_created
    ON chat_history (chat_id, created_at DESC);
```

## Как протестировать

1. Выполнить DDL в Supabase SQL Editor (проект `sgsxxmxybcysvbfsohau`)
2. Вставить тестовую строку: `INSERT INTO chat_history (chat_id, role, content) VALUES (123, 'user', 'тест')`
3. Проверить через `SELECT * FROM chat_history WHERE chat_id = 123`
4. Убедиться что RLS-политики позволяют чтение и запись через anon-ключ `SUPABASE_SUPPORT_ANON_KEY`

## Критерии приёмки

- [x] Таблица `chat_history` создана в проекте `sgsxxmxybcysvbfsohau`
- [x] Индекс `idx_chat_history_chat_id_created` существует
- [x] Anon-ключ может INSERT и SELECT из таблицы (RLS настроен или отключён)
