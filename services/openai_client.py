import logging

import aiohttp

from config import settings

try:
    from aiohttp_socks import ProxyConnector
    _SOCKS_AVAILABLE = True
except ImportError:
    _SOCKS_AVAILABLE = False

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
        proxy = settings.openai_proxy
        # For SOCKS5 proxies use a dedicated session with ProxyConnector
        if proxy and proxy.startswith("socks") and _SOCKS_AVAILABLE:
            connector = ProxyConnector.from_url(proxy)
            self._openai_session: aiohttp.ClientSession = aiohttp.ClientSession(connector=connector)
            self._proxy = None
        else:
            self._openai_session = session
            self._proxy = proxy

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
            async with self._openai_session.post(
                API_URL, json=payload, headers=self._headers, proxy=self._proxy
            ) as resp:
                data = await resp.json()
                if "choices" not in data:
                    logger.error("OpenAI unexpected response (status=%s): %s", resp.status, data)
                    return None
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

    async def inn_not_found(self, escalate: bool = False) -> str | None:
        escalate_instruction = (
            " В конце ОБЯЗАТЕЛЬНО добавь: «Если у вас возникли трудности — напишите нам в поддержку @Lobster_21, и мы разберёмся.»"
            if escalate else ""
        )
        system = (
            "Я — Алина, менеджер по сопровождению банкротства в ArbitrA. "
            "Я проверила ИНН клиента и не нашла его в нашей системе. "
            'Напиши от первого лица 1-2 предложения: предложи перепроверить ИНН '
            f'или связаться с менеджером. Используй слова "я", "нашла", "обращусь".{escalate_instruction}'
        )
        return await self._complete(system, "ИНН не найден в системе", max_tokens=150)

    # ── 3. Phone mismatch ─────────────────────────────────────────────

    async def phone_mismatch(self) -> str | None:
        system = (
            "Я — Алина, менеджер ArbitrA. Телефон, которым клиент поделился, "
            "не совпадает с данными в нашей системе. Напиши от первого лица "
            "1-2 предложения: объясни ситуацию и предложи обратиться к менеджеру "
            'для обновления номера. Используй слова "я", "вижу", "помогу". '
            "В конце ОБЯЗАТЕЛЬНО добавь: «Напишите нам в поддержку @Lobster_21, и мы разберёмся с вашей проблемой.»"
        )
        return await self._complete(system, "Телефон не совпадает", max_tokens=150)

    # ── 4. No INN in text ─────────────────────────────────────────────

    async def no_inn_in_text(self, user_text: str, digit_count: int, escalate: bool = False) -> str | None:
        escalate_instruction = (
            " После просьбы ввести ИНН ОБЯЗАТЕЛЬНО добавь: «Если у вас возникли трудности — напишите нам в поддержку @Lobster_21, и мы разберёмся.»"
            if escalate else ""
        )
        system = (
            "Я — Алина, менеджер по сопровождению банкротства в ArbitrA. "
            "Клиент проходит авторизацию и должен ввести ИНН — 12-значный налоговый номер.\n\n"
            f"Сообщение клиента: {user_text}\n"
            f"Цифр найдено в сообщении: {digit_count}\n\n"
            'Отвечай строго от первого лица (используй "я", "вижу", "нашла"). '
            "1-3 предложения, по-русски, без markdown.\n\n"
            "Правила:\n"
            "1. Если цифр > 0 и не 12 — скажи сколько нашла и что нужно ровно 12.\n"
            "2. Если спрашивает что такое ИНН или где его найти — объясни: ИНН это 12-значный налоговый номер физлица, "
            "найти можно в личном кабинете nalog.ru, в паспортных данных госуслуг, или на странице ИНН на сайте ФНС.\n"
            "3. Если не понимает процесс авторизации — объясни кратко: сначала ИНН, потом подтверждение телефона.\n"
            "4. Если задаёт любой другой вопрос (про банкротство, документы, сроки, деньги и т.д.) — "
            "НЕ отвечай на него, скажи что ответишь на все вопросы сразу после входа в личный кабинет.\n"
            "5. Если растерян или раздражён — посочувствуй.\n"
            f"Всегда заканчивай просьбой ввести 12-значный ИНН.{escalate_instruction}"
        )
        return await self._complete(system, user_text, max_tokens=250)

    # ── 5. Waiting for phone ──────────────────────────────────────────

    async def waiting_for_phone(self, user_text: str) -> str | None:
        system = (
            "Я — Алина, менеджер по сопровождению банкротства в ArbitrA. "
            "Я уже нашла дело клиента по ИНН и жду подтверждения личности через телефон.\n\n"
            f"Сообщение клиента: {user_text}\n\n"
            'Отвечай от первого лица (используй "я", "мне", "помогу"), кратко 1-2 предложения. '
            "Правила:\n"
            "1. Если спрашивает зачем нужен телефон — объясни: это нужно для подтверждения личности, "
            "чтобы я была уверена что общаюсь именно с владельцем дела.\n"
            "2. Если не хочет делиться номером — объясни, что без подтверждения я не смогу открыть личный кабинет, "
            "это требование безопасности.\n"
            "3. Если задаёт любой другой вопрос (про банкротство, документы, сроки, деньги и т.д.) — "
            "НЕ отвечай на него, скажи что ответишь на все вопросы сразу после входа в личный кабинет.\n"
            "В конце ВСЕГДА добавляй: «Нажмите кнопку \U0001f4f1 Поделиться номером телефона ниже.»"
        )
        return await self._complete(system, user_text, max_tokens=250)
