import logging

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIService:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        self._model = settings.openai_model

    async def _complete(
        self, system: str, user: str, max_tokens: int = 200, temperature: float = 0.7
    ) -> str | None:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with self._session.post(API_URL, json=payload, headers=self._headers) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            logger.exception("OpenAI request failed")
            return None

    # ── 1. Main chat as Alina ──────────────────────────────────────────

    async def chat_as_alina(self, user_text: str, contact_name: str) -> str | None:
        name = contact_name or "Клиент"
        system = (
            f"Я — Алина, персональный менеджер по сопровождению процедуры банкротства "
            f'в ArbitrA. Я работаю с клиентом {name}. '
            f"Отвечай строго от первого лица — используй \"я\", \"мне\", \"могу\", \"помогу\". "
            f"Отвечай на русском, кратко (2-4 предложения). "
            f"Давай только фактическую информацию о процедуре банкротства. "
            f"Не давай юридических консультаций — предлагай связаться с юристом. "
            f'Никогда не пиши "как Алина" или "в роли Алины" — просто отвечай '
            f"естественно от первого лица."
        )
        return await self._complete(system, user_text, max_tokens=300)

    # ── 2. INN not found ───────────────────────────────────────────────

    async def inn_not_found(self) -> str | None:
        system = (
            "Я — Алина, менеджер по сопровождению банкротства в ArbitrA. "
            "Я проверила ИНН клиента и не нашла его в нашей системе. "
            'Напиши от первого лица 1-2 предложения: предложи перепроверить ИНН '
            'или связаться с менеджером. Используй слова "я", "нашла", "обращусь".'
        )
        return await self._complete(system, "ИНН не найден в системе", max_tokens=150)

    # ── 3. Phone mismatch ─────────────────────────────────────────────

    async def phone_mismatch(self) -> str | None:
        system = (
            "Я — Алина, менеджер ArbitrA. Телефон, которым клиент поделился, "
            "не совпадает с данными в нашей системе. Напиши от первого лица "
            "1-2 предложения: объясни ситуацию и предложи обратиться к менеджеру "
            'для обновления номера. Используй слова "я", "вижу", "помогу".'
        )
        return await self._complete(system, "Телефон не совпадает", max_tokens=150)

    # ── 4. No INN in text ─────────────────────────────────────────────

    async def no_inn_in_text(self, user_text: str, digit_count: int) -> str | None:
        system = (
            "Я — Алина, менеджер по сопровождению банкротства в ArbitrA. "
            "Клиент проходит авторизацию и должен ввести ИНН — 12-значный налоговый номер.\n\n"
            f"Сообщение клиента: {user_text}\n"
            f"Цифр найдено в сообщении: {digit_count}\n\n"
            'Отвечай строго от первого лица (используй "я", "вижу", "нашла"). '
            "1-3 предложения, по-русски, без markdown:\n"
            "1. Если цифр > 0 и не 12 — скажи сколько нашла и что нужно ровно 12.\n"
            "2. Если спрашивает что такое ИНН — объясни кратко.\n"
            "3. Если пишет не по теме — мягко верни к авторизации.\n"
            "4. Если растерян или раздражён — посочувствуй.\n"
            "Всегда заканчивай просьбой ввести 12-значный ИНН."
        )
        return await self._complete(system, user_text, max_tokens=200)

    # ── 5. Waiting for phone ──────────────────────────────────────────

    async def waiting_for_phone(self, user_text: str) -> str | None:
        system = (
            "Я — Алина, менеджер по сопровождению банкротства в ArbitrA. "
            "Я уже нашла дело клиента по ИНН и жду подтверждения личности через телефон.\n\n"
            f"Сообщение клиента: {user_text}\n\n"
            'Отвечай от первого лица (используй "я", "мне", "помогу"), кратко 1-2 предложения. '
            "Если клиент задаёт вопрос — ответить целесообразно. "
            "Если пишет не по теме — мягко объясни, что сначала нужно завершить верификацию. "
            "В конце ВСЕГДА добавляй: «Нажмите кнопку \U0001f4f1 Поделиться номером телефона ниже.»"
        )
        return await self._complete(system, user_text, max_tokens=200)
