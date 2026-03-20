Дата: 2026-03-20
Статус: ⬜ pending
Спецификация: docs/2. SUP-specifications/S02_multi_agent_chat.md

# T06 — Обновить `config.py` и `.env`

## Customer-facing инкремент

Технический таск — добавить конфигурацию для нового Supabase-проекта и моделей агентов.

## Цель

Добавить 4 новые переменные в `config.py` и `.env`. `SUPABASE_SUPPORT_URL` и `SUPABASE_SUPPORT_ANON_KEY` уже добавлены в `.env` — нужно только подключить их в `config.py`.

## Изменения в коде

- `config.py`:
  - В датакласс `Settings` добавить поля:
    ```python
    supabase_support_url: str
    supabase_support_anon_key: str
    openai_model_support: str
    openai_model_coordinator: str
    ```
  - В `from_env()` добавить:
    ```python
    supabase_support_url=os.environ["SUPABASE_SUPPORT_URL"],
    supabase_support_anon_key=os.environ["SUPABASE_SUPPORT_ANON_KEY"],
    openai_model_support=os.getenv("OPENAI_MODEL_SUPPORT", "gpt-4o-mini"),
    openai_model_coordinator=os.getenv("OPENAI_MODEL_COORDINATOR", "gpt-4o"),
    ```
- `.env` — добавить (частично уже сделано):
  ```
  OPENAI_MODEL_SUPPORT=gpt-4o-mini
  OPENAI_MODEL_COORDINATOR=gpt-4o
  ```

## Как протестировать

1. Запустить `python -c "from config import settings; print(settings.supabase_support_url)"`
2. Убедиться что выводится `https://sgsxxmxybcysvbfsohau.supabase.co`

## Критерии приёмки

- [ ] `settings.supabase_support_url` и `settings.supabase_support_anon_key` доступны
- [ ] `settings.openai_model_support` и `settings.openai_model_coordinator` доступны с дефолтами
- [ ] При отсутствии `SUPABASE_SUPPORT_URL` в `.env` — бот падает с `KeyError` при старте (намеренно)
