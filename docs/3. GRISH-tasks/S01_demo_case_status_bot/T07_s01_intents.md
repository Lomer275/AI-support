Дата: 2026-04-03
Статус: draft
Спецификация: docs/2. GRISH-specifications/S01_demo_case_status_bot.md

# T07_s01_intents — Интенты greeting/gratitude/off_topic и фоллбэки

## Customer-facing инкремент

Бот корректно реагирует на приветствие, благодарность и нерелевантные вопросы. При технических ошибках не падает — возвращает понятный фоллбэк.

## Цель

Добавить обработку интентов `greeting`, `gratitude`, `off_topic` и `fallback` в `text.py`. Убедиться что все фоллбэки (`FALLBACK_ALEVTINA`, `CASE_NOT_FOUND_MSG`) работают корректно.

## Контекст

T02 и T03 готовы. T04 и T05 уже реализуют ветки `case_status` и `next_steps`. T07 дописывает оставшиеся ветки в тот же блок `if/elif` в `text.py`. T06 реализует историю параллельно — T07 не затрагивает логику истории.

## Scope

- `demo_bot/handlers/text.py` — добавить ветки в блок обработки `result["intent"]`:

```python
elif result["intent"] == "greeting":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)

elif result["intent"] == "gratitude":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)

elif result["intent"] == "off_topic":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)

else:  # "fallback" или неизвестный intent
    await message.answer(FALLBACK_ALEVTINA)
```

Все четыре интента просто отправляют `result["answer"]`. Различие в содержании — на стороне GPT (системный промпт T03).

`CASE_NOT_FOUND_MSG` уже добавлен в T04 (поток при отсутствии дела). T07 только проверяет что он работает корректно.

## Out of scope

- Содержание ответов для каждого интента — за это отвечает промпт (T03) и тюнинг (T08)
- Кеш `case_context` — T04
- История диалога — T06

## Технические детали

**Итоговый блок обработки интентов в text.py (authorized branch):**
```python
result = await alevtina_svc.handle(message.text, history, case_context)

if result["intent"] == "case_status":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)
elif result["intent"] == "next_steps":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)
elif result["intent"] == "greeting":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)
elif result["intent"] == "gratitude":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)
elif result["intent"] == "off_topic":
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)
else:
    await message.answer(FALLBACK_ALEVTINA)
```

Можно упростить до:
```python
if result["intent"] in ("case_status", "next_steps", "greeting", "gratitude", "off_topic"):
    await message.answer(result["answer"], parse_mode=ParseMode.HTML)
else:
    await message.answer(FALLBACK_ALEVTINA)
```

Оба варианта допустимы. Выбор за разработчиком.

**Текст для интентов (из промпта, Часть 1):**
- `greeting` → поздоровайся и предложи спросить о деле или шагах
- `gratitude` → «Рада помочь! Если появятся вопросы — я здесь.»
- `off_topic` → «Я специализируюсь только на вашем деле и следующих шагах.»

## Как протестировать

### 1. Приветствие

1. Написать «Привет»
2. Проверить: ответ — приветствие с предложением спросить о деле, `intent == "greeting"`

### 2. Благодарность

1. Написать «Спасибо»
2. Проверить: ответ — «Рада помочь!...», `intent == "gratitude"`

### 3. Нерелевантный вопрос

1. Написать «Расскажи анекдот»
2. Проверить: ответ — «Я специализируюсь только на вашем деле...», `intent == "off_topic"`, ответ НЕ заканчивается вопросом

### 4. Фоллбэк при недоступном OpenAI

1. Временно передать невалидный API-ключ
2. Написать любое сообщение
3. Проверить: получен `FALLBACK_ALEVTINA`, бот не упал

## Критерии приёмки

1. `greeting` → приветственный ответ с предложением задать вопрос
2. `gratitude` → «Рада помочь!...»
3. `off_topic` → redirect без вопроса в конце
4. `fallback` (любая ошибка) → `FALLBACK_ALEVTINA` без краша
5. Ни один из ответов не заканчивается вопросом к клиенту

## Правила завершения задачи

**После акцепта задачи AI выполняет автоматически:**

1. **Обновить файл задачи:**
   - Статус → `✅ accepted`
   - Добавить дату завершения

2. **Переместить файл:**
   - Из: `docs/3. GRISH-tasks/S01_demo_case_status_bot/T07_s01_intents.md`
   - В: `docs/3. GRISH-tasks/Done/S01_demo_case_status_bot_done/T07_s01_intents_done.md`

3. **Обновить спецификацию:**
   - Статус T07 → `✅ done`

4. **Обновить GRISH-HANDOFF.md:**
   - Отметить T07 как выполненную
