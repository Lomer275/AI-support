Дата: 2026-04-03
Статус: draft
Спецификация: docs/2. GRISH-specifications/S01_demo_case_status_bot.md

# T02_s01_auth — Авторизация

## Customer-facing инкремент

Клиент вводит ИНН → бот ищет дело в Bitrix24 → запрашивает телефон кнопкой → верифицирует → переходит в `authorized` с приветственным сообщением. Все отказы обработаны с корректными текстами.

## Цель

Реализовать полный флоу авторизации: три состояния (`waiting_inn`, `waiting_phone`, `authorized`), хэндлеры `/start`, текстовых сообщений и контакта, счётчик ошибок ИНН.

## Контекст

Каркас (T01) готов: `DemoSupabaseService`, `DemoSessionMiddleware`, `messages.py`, `keyboards.py` существуют. Авторизация переиспользует `BitrixService.search_by_inn()` и `normalize_phone()` из `utils.py` корня.

## Scope

- `demo_bot/handlers/start.py` — хэндлер команды `/start`:
  - Если `state != 'authorized'`: сбросить сессию (`update_session(chat_id, state='waiting_inn', inn=None, deal_id=None, error_count=0, context_data={})`), отправить «Введите ваш ИНН (12 цифр)»
  - Если `state == 'authorized'`: отправить «Чем могу помочь? Спросите о вашем деле или следующих шагах» — сессию не трогать
- `demo_bot/handlers/contact.py` — хэндлер `F.contact`:
  - Только в состоянии `waiting_phone`
  - Нормализовать телефон: `normalize_phone(contact.phone_number)`
  - Сравнить с `session["bitrix_phone"]`
  - Совпадает: `update_session(chat_id, state='authorized')`, убрать клавиатуру, отправить `WELCOME_AUTHORIZED.format(first_name=...)`
  - Не совпадает: отправить `PHONE_MISMATCH`, убрать клавиатуру, сбросить сессию в `waiting_inn`
- `demo_bot/handlers/text.py` — роутинг текстовых сообщений по состоянию:
  - `waiting_inn`: извлечь ИНН через `extract_inn(text)`:
    - 12 цифр найдены → `BitrixService.search_by_inn(inn)`:
      - Найдено: сохранить `inn`, `deal_id`, `contact_id`, `bitrix_phone`, установить `state='waiting_phone'`, отправить запрос телефона с `phone_share_keyboard()`
      - Не найдено: инкрементировать `error_count`, отправить `INN_NOT_FOUND_1` (если `error_count==1`) или `INN_NOT_FOUND_2` (если `≥2`)
      - Bitrix exception: отправить `INN_BITRIX_ERROR`, счётчик не трогать
    - 12 цифр не найдены: отправить «Введите ИНН — 12 цифр» (без инкремента счётчика)
  - `waiting_phone`: пользователь написал текст вместо нажатия кнопки → отправить `PHONE_USE_BUTTON`
  - `authorized`: передать управление хэндлеру диалога (T04–T07) — в этой задаче заглушка: «Отвечу через секунду...»

## Out of scope

- GPT-вызов и классификация намерений — T03
- Диалоговые ответы (`case_status`, `next_steps` и др.) — T04–T07
- Кеширование `case_context` — T04

## Технические детали

**Порядок регистрации хэндлеров** в `demo_bot/handlers/__init__.py`:
```python
dp.include_router(start_router)    # /start
dp.include_router(contact_router)  # F.contact (только waiting_phone)
dp.include_router(text_router)     # текстовые сообщения
```

**Фильтрация состояний** — через `DemoSessionMiddleware`: состояние доступно в `data["demo_session"]["state"]`. Хэндлеры не используют Aiogram FSM — проверяют `state` вручную.

**extract_inn** — из `utils.py`: возвращает 12-значный ИНН или None. 10-значный ИНН юрлиц не поддерживается.

**normalize_phone** — из `utils.py`: берёт последние 10 цифр, убирает +7/8.

**BitrixService** — инициализируется в `bot.py` и инжектируется через `workflow_data` аналогично основному боту. В `text.py` доступен как `data["bitrix"]`.

**error_count** — хранится в `demo_bot_sessions`. Инкрементируется только при «ИНН не найден». Bitrix-исключение не инкрементирует. Сбрасывается при `/start` или успешной авторизации.

## Как протестировать

### 1. Успешная авторизация

1. Написать боту `/start`
2. Ввести корректный 12-значный ИНН клиента из Bitrix24
3. Нажать кнопку «Поделиться номером» (совпадающий телефон)
4. Проверить:
   - `state` в `demo_bot_sessions` = `authorized`
   - Пришло приветственное сообщение с именем клиента
   - Клавиатура убрана

### 2. ИНН не найден — счётчик

1. Ввести несуществующий ИНН — получить `INN_NOT_FOUND_1` (без @Lobster_21)
2. Ввести ещё раз — получить `INN_NOT_FOUND_2` (с @Lobster_21)
3. Проверить `error_count` в БД: 1 и 2 соответственно

### 3. Телефон не совпал

1. Пройти до шага «Поделиться номером»
2. Поделиться телефоном, который не совпадает с Bitrix
3. Проверить: получен `PHONE_MISMATCH`, сессия сброшена в `waiting_inn`

### 4. `/start` для авторизованного

1. Пройти авторизацию полностью
2. Написать `/start`
3. Проверить: получено «Чем могу помочь?», `state` остался `authorized`

### 5. Текст в состоянии `waiting_phone`

1. Дойти до шага телефона
2. Написать любой текст вместо нажатия кнопки
3. Проверить: получен `PHONE_USE_BUTTON`

## Критерии приёмки

1. Полный флоу ИНН → телефон → `authorized` проходит без ошибок
2. `error_count` инкрементируется только при «не найдено», не при Bitrix-исключении
3. `PHONE_MISMATCH` сбрасывает сессию в `waiting_inn`
4. `/start` для авторизованного не сбрасывает сессию
5. Текст в `waiting_phone` возвращает `PHONE_USE_BUTTON`
6. После авторизации клавиатура убрана, `WELCOME_AUTHORIZED` содержит имя клиента

## Правила завершения задачи

**После акцепта задачи AI выполняет автоматически:**

1. **Обновить файл задачи:**
   - Статус → `✅ accepted`
   - Добавить дату завершения

2. **Переместить файл:**
   - Из: `docs/3. GRISH-tasks/S01_demo_case_status_bot/T02_s01_auth.md`
   - В: `docs/3. GRISH-tasks/Done/S01_demo_case_status_bot_done/T02_s01_auth_done.md`

3. **Обновить спецификацию:**
   - Статус T02 → `✅ done`

4. **Обновить GRISH-HANDOFF.md:**
   - Отметить T02 как выполненную
