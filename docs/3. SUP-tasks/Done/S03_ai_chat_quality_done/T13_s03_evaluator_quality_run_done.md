Дата: 2026-03-27
Статус: ✅ Выполнено
Дата закрытия: 2026-03-27
Спецификация: docs/2. SUP-specifications/S03_ai_chat_quality.md

# T13 — Система оценки качества ответов (EvaluatorService + quality_run.py)

## Customer-facing инкремент

Команда может запустить одну команду и получить объективный отчёт о качестве ответов ИИ по 20+ вопросам из базы — без ручного тестирования каждого сценария.

## Цель

Создать `EvaluatorService` — агент-судья на GPT, оценивающий каждый ответ по 4 критериям. Создать CLI-скрипт `scripts/quality_run.py`, который прогоняет N вопросов из `questions.md` через `SupportService` и сохраняет результаты в JSON.

## Изменения в коде

- `services/evaluator.py` (новый файл):
  - Класс `EvaluatorService` с методом `evaluate(question, answer, client_context) -> dict | None`
  - Промпт: оценить ответ по 4 критериям (1–5 баллов каждый): specificity, accuracy, tone, completeness
  - Возвращает JSON: `{"specificity": N, "accuracy": N, "tone": N, "completeness": N, "total": N, "comment": "..."}`
  - Использует `OPENAI_MODEL_COORDINATOR` (gpt-4o) как судью, temperature=0.2
  - Возвращает `None` при ошибке (не падает)

- `scripts/quality_run.py` (новый файл):
  - CLI: `python scripts/quality_run.py --limit 20 --output results.json`
  - Читает вопросы из `docs/5. SUP-unsorted/questions.md`
  - Для каждого вопроса: вызывает `SupportService.answer()` с `chat_id=-999` и пустым `inn`
  - Передаёт Q+A в `EvaluatorService.evaluate()`
  - Сохраняет в JSON: вопрос, ответ, оценки, итоговый балл
  - В конце выводит среднее по всем критериям в stdout
  - При ошибках OpenAI — логирует и продолжает (не падает)

## Как протестировать

1. Запустить: `python scripts/quality_run.py --limit 5 --output test_results.json`
2. Проверить: скрипт отработал без исключений, файл `test_results.json` создан
3. Открыть файл и проверить: у каждого вопроса есть 4 оценки + комментарий судьи
4. Проверить итоговую статистику в stdout

## Критерии приёмки

1. ✅ `services/evaluator.py` существует, `EvaluatorService.evaluate()` возвращает корректный JSON
2. ✅ `scripts/quality_run.py` запускается без ошибок
3. ✅ Результаты содержат все 4 критерия для каждого вопроса
4. ✅ При недоступности OpenAI скрипт не падает — логирует ошибку и продолжает
5. ✅ Итоговый JSON валиден и содержит среднюю оценку по всем вопросам
