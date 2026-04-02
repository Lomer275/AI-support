Дата: 2026-03-30
Статус: draft
Спецификация: docs/2. SUP-specifications/S04_electronic_case.md

**Статус:** ✅ Выполнено
**Дата закрытия:** 2026-03-31

# T19_s04_webhooks_sync — Постоянная синхронизация через вебхуки Bitrix

## Customer-facing инкремент

ИИ-агент всегда видит актуальную стадию дела клиента — смена стадии в Bitrix отражается в базе в течение нескольких секунд.

## Цель

Расширить существующий `webhook_server.py` обработчиком события `onCrmDealUpdate` от Bitrix. При изменении сделки — обновлять соответствующие поля в `electronic_case`.

## Scope

- Добавить обработчик `onCrmDealUpdate` в `webhook_server.py`
- Обновлять `cases`: `stage`, `stage_updated_at` и все поля которые могли измениться
- При получении нового файла в сделке — создавать запись в `documents` со статусом `pending` и запускать `DocumentValidator` (T20)
- При новом комментарии в сделке — добавлять запись в `communications`
- Идемпотентность: повторный вебхук с теми же данными не создаёт дублей (проверка по `bitrix_id`)
- Логировать каждое обновление: `[WEBHOOK] deal_id=123, field=STAGE_ID, value=...`

## Out of scope

- Обработка событий закрытия/удаления сделок
- Синхронизация `property` и `debts` по вебхукам (только при начальной синхронизации T18; эти данные меняются редко)
- Вебхуки от других сущностей Bitrix (контакты, задачи)

## Результат выполнения

- `services/cases_mapper.py` — NEW: общий маппинг (`build_case_row`, `upsert_case`, `insert_communication`, enum-карты), переиспользуется sync-скриптом и webhook-сервером
- `webhook_server.py` — новый маршрут `POST /bitrix/crm-deal-update`, handler `_handle_crm_deal_update`, batch-запрос deal+contact
- `config.py` — добавлены `supabase_cases_url`, `supabase_cases_anon_key`
- `bot.py` — передаёт cases-параметры в `create_webhook_app`
- Вебхук зарегистрирован в Bitrix: `ONCRMDEALUPDATE` → `https://ai.express-bankrot.ru/bitrix/crm-deal-update`
- Traefik-маршрут добавлен в `/root/clean-traefik-n8n/traefik_data/dynamic_conf/ai-support.yml`
- Тест пройден: изменение deal_id=275098 → upsert в Supabase за 2 секунды

## Связанные документы

- Спека: [S04_electronic_case.md](../../2.%20SUP-specifications/S04_electronic_case.md)
- Зависит от: T17
