Дата: 2026-03-20
Статус: ✅ done
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T07 — Обновить `bot.py`: инициализация `SupportSupabaseService` и `SupportService`

## Customer-facing инкремент

Технический таск — подключить новые сервисы к боту.

## Цель

Добавить в `bot.py` инициализацию `SupportSupabaseService` и `SupportService` по образцу существующих сервисов (shared `aiohttp.ClientSession`).

## Изменения в коде

- `bot.py`:
  ```python
  from services.supabase_support import SupportSupabaseService
  from services.support import SupportService

  # В функции main(), после инициализации существующих сервисов:
  supabase_support = SupportSupabaseService(http_session)
  support_svc = SupportService(
      session=http_session,
      supabase_support=supabase_support,
  )
  dp["support_svc"] = support_svc
  ```

## Как протестировать

1. Запустить `python bot.py`
2. Убедиться что бот стартует без ошибок
3. Проверить логи — нет `ImportError` или `AttributeError`

## Критерии приёмки

- [ ] Бот стартует без ошибок
- [ ] `dp["support_svc"]` доступен в хэндлерах
- [ ] `SupportSupabaseService` и `SupportService` используют общий `http_session`
