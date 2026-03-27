import json
import logging

import aiohttp

logger = logging.getLogger(__name__)

EVALUATOR_SYSTEM = """Ты — эксперт по оценке качества ответов AI-ассистента «Алина» для сервиса банкротства физических лиц «Экспресс-Банкрот».

Оцени ответ ассистента по 4 критериям, выставив каждому оценку от 1 до 5:

1. **specificity** (конкретность) — использует ли ответ данные клиента или только общие фразы?
   5 — ответ конкретен, учитывает контекст клиента
   1 — полностью общие фразы, нет ничего о ситуации клиента

2. **accuracy** (точность) — нет ли в ответе галлюцинаций, ложных фактов о компании или законодательстве?
   5 — всё точно, нет придуманных фактов
   1 — есть явные ошибки или выдуманные факты

3. **tone** (тон) — спокойный, поддерживающий, без тревоги и давления?
   5 — мягко, по-человечески, клиент чувствует поддержку
   1 — формально, холодно, тревожно или грубо

4. **completeness** (полнота) — закрывает ли ответ вопрос клиента или уходит в сторону?
   5 — вопрос полностью раскрыт
   1 — ответ не по теме или обрывается на полуслове

Верни ТОЛЬКО валидный JSON без markdown-блоков:
{"specificity": N, "accuracy": N, "tone": N, "completeness": N, "total": N, "comment": "краткий вывод судьи"}

Поле "total" — среднее арифметическое четырёх оценок, округлённое до одного знака после запятой."""


class EvaluatorService:
    def __init__(
        self,
        http_session: aiohttp.ClientSession,
        openai_api_key: str,
        model: str,
        openai_proxy: str | None = None,
    ):
        self._session = http_session
        self._api_key = openai_api_key
        self._model = model
        self._proxy = openai_proxy
        self._openai_url = "https://api.openai.com/v1/chat/completions"

    async def evaluate(
        self, question: str, answer: str, client_context: str = ""
    ) -> dict | None:
        """Evaluate an AI answer on 4 criteria. Returns dict or None on failure."""
        context_block = ""
        if client_context:
            context_block = f"\n\nКОНТЕКСТ КЛИЕНТА:\n{client_context}"

        user_msg = (
            f"ВОПРОС КЛИЕНТА:\n{question}"
            f"{context_block}"
            f"\n\nОТВЕТ АЛИНЫ:\n{answer}"
        )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": EVALUATOR_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 300,
            "temperature": 0.2,
        }
        kwargs = {}
        if self._proxy:
            kwargs["proxy"] = self._proxy

        try:
            async with self._session.post(
                self._openai_url, json=payload, headers=headers, **kwargs
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    logger.error("EvaluatorService HTTP %s: %s", resp.status, text[:300])
                    return None
                data = await resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
        except Exception:
            logger.exception("EvaluatorService evaluate failed")
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("EvaluatorService: invalid JSON from model: %s", raw[:200])
            return None
