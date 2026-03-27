import asyncio
import json
import logging
from typing import TYPE_CHECKING

import aiohttp

from services.supabase_support import SupportSupabaseService

if TYPE_CHECKING:
    from services.evaluator import EvaluatorService

logger = logging.getLogger(__name__)

FALLBACK_ALINA = (
    "Алина временно недоступна. Пожалуйста, повторите вопрос чуть позже "
    "или обратитесь к нашему специалисту @Lobster_21."
)

COMPANY_FACTS = """
ФАКТЫ О КОМПАНИИ «ЭКСПРЕСС-БАНКРОТ» (только эти факты — правда, не выдумывай других):
- Официальное название: ООО «Экспресс-Банкрот»
- Сайт: www.express-bankrot.ru
- Физические офисы: Краснодар, Воронеж, Барнаул. В других городах — только удалённая работа.
- Офиса в Ростове-на-Дону НЕТ (был ранее, закрыт).
- Время работы офисов: Пн-Пт с 9:00 до 18:00 по местному времени города.

ОФИСЫ И ТЕЛЕФОНЫ:
- Барнаул: ул. Деповская, д. 18. Тел.: +7 (3852) 29-92-02
- Воронеж: ул. Фридриха Энгельса, д. 25Б, офис 102, БЦ БиК. Тел.: +7 (473) 280-01-01
- Краснодар: ул. Кузнечная, д. 4А, 12 этаж, офис 5. Тел.: +7 (861) 205-64-64

- Связь с клиентами: через этот чат, менеджеры свяжутся при необходимости.
- Компания НЕ ведёт кассу клиента и НЕ распоряжается его деньгами.
- Всё взаимодействие с судом и финансовым управляющим — в рамках закона и только через документы.
ПРАВИЛО: если клиент спрашивает факт о компании, которого нет в этом блоке — не выдумывай. Скажи: «Этот вопрос лучше уточнить у нашего специалиста».
"""


class SupportService:
    def __init__(
        self,
        http_session: aiohttp.ClientSession,
        supabase_support: SupportSupabaseService,
        openai_api_key: str,
        model_support: str,
        model_coordinator: str,
        openai_proxy: str | None = None,
        evaluator: "EvaluatorService | None" = None,
    ):
        self._session = http_session
        self._supabase = supabase_support
        self._api_key = openai_api_key
        self._model_support = model_support
        self._model_coordinator = model_coordinator
        self._proxy = openai_proxy
        self._openai_url = "https://api.openai.com/v1/chat/completions"
        self._evaluator = evaluator

    # Retry if accuracy OR completeness is clearly poor (≤3).
    # Specificity is excluded — it's low by design without client data.
    # Tone is excluded — rarely the root cause of a bad answer.
    _RETRY_THRESHOLD = 3.5

    def _should_retry(self, scores: dict) -> bool:
        return (
            scores.get("accuracy", 5) < self._RETRY_THRESHOLD
            or scores.get("completeness", 5) < self._RETRY_THRESHOLD
        )

    # ------------------------------------------------------------------
    # Base OpenAI call
    # ------------------------------------------------------------------

    async def _complete(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 500,
        temperature: float = 0.8,
    ) -> str | None:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
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
                    logger.error("OpenAI HTTP %s: %s", resp.status, text[:300])
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("OpenAI _complete failed")
            return None

    # ------------------------------------------------------------------
    # R1 round
    # ------------------------------------------------------------------

    async def _r1_lawyer(
        self, client_context: str, question: str, history: list[dict]
    ) -> str | None:
        history_text = ""
        if history:
            lines = [f"{m['role'].upper()}: {m['content']}" for m in history]
            history_text = (
                "\n\nИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С КЛИЕНТОМ (учитывай — не запрашивай повторно то, что клиент уже сообщал):\n"
                + "\n".join(lines)
            )
        system = (
            f"{COMPANY_FACTS}\n\n"
            "Ты — ИИ-юрист по банкротству физических лиц в компании «Экспресс-Банкрот».\n"
            "Ты работаешь ТОЛЬКО для внутренних коллег. Клиент твой текст НЕ видит.\n\n"
            f"***КОНТЕКСТ:*** {client_context}{history_text}\n"
            f"***ВОПРОС:*** {question}\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Коротко описать ситуацию клиента простым русским языком (2–4 предложения):\n"
            "   - кто клиент (если есть ФИО),\n"
            "   - на какой стадии его дело (до подачи, подано заявление, введена процедура, торги, завершение и т.п.),\n"
            "   - какие ключевые события уже произошли (даты, определения суда, торги, публикации).\n"
            "2. Выделить ключевые юридически значимые факты:\n"
            "   - суммы долгов, наличие залогового/ипотечного имущества, сделки, кредиторы,\n"
            "   - даты важных событий (признание банкротом, введение процедуры, заседания, торги),\n"
            "   - существенные ограничения или риски по делу.\n"
            "3. Дать предварительное юридическое мнение по вопросу клиента:\n"
            "   - какие нормы применимы (127-ФЗ и смежные, можно без номера статьи),\n"
            "   - что по закону точно можно / точно нельзя,\n"
            "   - какие реальные последствия для клиента возможны по его вопросу.\n"
            "4. Если вопрос клиента описывает гипотетический сценарий, противоречащий его реальной ситуации "
            "(например, «а если меня не признают?», а клиент уже признан банкротом) — отметь это явно "
            "и сформулируй ответ применительно к его реальному положению, а не к гипотезе.\n"
            "   ВАЖНО по датам: НЕ называй конкретную дату завершения процедуры, если она не указана явно. "
            "Даты заседаний, торгов, публикаций из контекста — НЕ являются датой завершения дела.\n\n"
            "5. Оценить, относится ли вопрос клиента к теме банкротства физлица и сопровождения:\n"
            "   - Считать «по теме» всё, что связано с: долгами, кредитами, МФО, имуществом, торгами, судом, "
            "прожиточным минимумом, картами, доходами, выездом за границу, семьёй, работой, кредитной историей, "
            "документами по делу, сроками процедур.\n"
            "   - Считать «вне темы» или требующим живого специалиста: оплату/возврат наших услуг, условия договора "
            "с компанией, личные жалобы, запись на приём/звонок, технические проблемы, чисто налоговые вопросы без "
            "связи с банкротством, развод/наследство/имущество без банкротства.\n"
            "5. В конце дать рекомендацию по переключателю (`switcher`) для финального агента:\n"
            "   - `false` — ИИ вполне может ответить сам (типичные вопросы из FAQ про процедуру и её последствия, "
            "сроки, имущество, прожиточный минимум и т.п.).\n"
            "   - `true` — нужен живой специалист (деньги/договор с компанией, жалоба/конфликт, просьба связаться, "
            "просьба записать к юристу, сложные процессуальные действия «как именно подать/оспорить» вне типовых "
            "сценариев, вопросы про контакты/действия финансового управляющего).\n\n"
            "ФОРМАТ ВЫХОДА:\n"
            "Свободный структурированный текст с подзаголовками:\n"
            "- «Ситуация клиента»\n"
            "- «Ключевые факты и риски»\n"
            "- «Юридическое мнение»\n"
            "- (опционально) «Вывод»\n\n"
            "В САМОМ КОНЦЕ — ОТДЕЛЬНОЙ СТРОКОЙ:\n"
            "«РЕКОМЕНДАЦИЯ SWITCHER ЮРИСТ R1: true/false. Причина: …»"
        )
        return await self._complete(system, question, self._model_support)

    async def _r1_manager(
        self, client_context: str, question: str, r1_lawyer: str, history: list[dict]
    ) -> str | None:
        history_text = ""
        if history:
            lines = [f"{m['role'].upper()}: {m['content']}" for m in history]
            history_text = (
                "\n\nИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С КЛИЕНТОМ (учитывай при оценке эмоционального состояния — не запрашивай повторно то, что клиент уже сообщал):\n"
                + "\n".join(lines)
            )
        system = (
            f"{COMPANY_FACTS}\n\n"
            "Ты — ИИ-менеджер по сопровождению клиентов «Экспресс-Банкрот».\n"
            "Ты НЕ отвечаешь клиенту напрямую, ты помогаешь финальному агенту говорить по-человечески.\n\n"
            f"***КОНТЕКСТ:*** {client_context}{history_text}\n"
            f"***ВОПРОС:*** {question}\n"
            f"*** МНЕНИЕ ЮРИСТА R1:***  {r1_lawyer}\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Определить эмоциональное состояние клиента (1–3 фразы):\n"
            "   - страх, тревога, злость, недоверие, усталость, стыд, отчаяние, надежда и т.п.,\n"
            "   - чего он боится больше всего в своём вопросе.\n"
            "2. Сформулировать 3–7 ключевых тезисов, которые ОБЯЗАТЕЛЬНО нужно донести клиенту, чтобы:\n"
            "   - снизить тревожность,\n"
            "   - вернуть ощущение, что процесс под контролем,\n"
            "   - дать ему опору (дата, этап, понятный план).\n"
            "   Особый акцент: при вопросах про сроки («когда завершится», «успеете ли», «а если срок пропустите») — "
            "базовое сообщение должно звучать уверенно: мы контролируем сроки, есть понятный ориентир, всё идёт штатно.\n"
            "3. Отдельным блоком написать:\n"
            "   - Чего лучше НЕ говорить (чтобы не усилить тревогу и не создать ложных ожиданий).\n"
            "   - Какой тон использовать (спокойный, уверенный, мягкий/чуть более прямой и т.п.).\n"
            "4. Дать рекомендацию по `switcher` для финального агента:\n"
            "   - `false` — если вопрос можно закрыть ИИ в рамках стандартного сопровождения.\n"
            "   - `true` — если клиент явно просит живого контакта или выражает жёсткую жалобу/конфликт.\n\n"
            "ВАЖНО:\n"
            "- Описывать «страшные» сценарии можно только как ВНУТРЕННЮЮ заметку «Чего нельзя говорить клиенту».\n\n"
            "ФОРМАТ ВЫХОДА:\n"
            "- «Эмоциональное состояние»\n"
            "- «Что важно сказать клиенту»\n"
            "- «Чего лучше не говорить»\n"
            "- «Рекомендации по тону»\n\n"
            "В САМОМ КОНЦЕ:\n"
            "«РЕКОМЕНДАЦИЯ SWITCHER МЕНЕДЖЕР R1: true/false. Причина: …»"
        )
        return await self._complete(system, question, self._model_support)

    async def _r1_sales(self, client_context: str, question: str) -> str | None:
        system = (
            f"{COMPANY_FACTS}\n\n"
            "Ты — ИИ-куратор процесса и рисков компании «Экспресс-Банкрот».\n"
            "Фокус: этап процедуры, сроки, действия сторон и риски коммуникации.\n"
            "Клиент твой текст НЕ видит, это служебная аналитика.\n\n"
            f"***КОНТЕКСТ:*** {client_context}\n"
            f"***ВОПРОС:*** {question}\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Определи текущий этап дела.\n"
            "2. Кратко опиши действия клиента и компании.\n"
            "3. Выдели риски коммуникации.\n"
            "4. Дай рекомендации финальному Координатору.\n"
            "5. Рекомендация по `switcher`: false — информационный вопрос, true — оплата/договор/запись/претензии.\n\n"
            "ФОРМАТ ВЫХОДА:\n"
            "- «Этап и сроки»\n"
            "- «Действия клиента»\n"
            "- «Действия компании»\n"
            "- «Риски коммуникации»\n"
            "- «Рекомендации финальному Координатору»\n\n"
            "В САМОМ КОНЦЕ:\n"
            "«РЕКОМЕНДАЦИЯ SWITCHER КУРАТОР R1: true/false. Причина: …»"
        )
        return await self._complete(system, question, self._model_support)

    # ------------------------------------------------------------------
    # R2 round
    # ------------------------------------------------------------------

    async def _r2_lawyer(
        self,
        client_context: str,
        question: str,
        r1_lawyer: str,
        r1_manager: str,
        r1_sales: str,
    ) -> str | None:
        system = (
            f"{COMPANY_FACTS}\n\n"
            "Ты — тот же ИИ-юрист по банкротству, но на втором раунде обсуждения.\n"
            "Сейчас нужно перепроверить и уточнить своё мнение R1 с учётом коллег.\n\n"
            f"***КОНТЕКСТ:*** {client_context}\n"
            f"***ВОПРОС:*** {question}\n"
            f"***МНЕНИЯ:*** {r1_lawyer} | {r1_manager} | {r1_sales}\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Кратко перечисли, что ты меняешь или уточняешь в своей позиции R1 (3–7 пунктов).\n"
            "2. Сформулируй «Юридическое ядро» ответа: что можно, что нельзя, реальные последствия.\n"
            "3. Финальная юридическая рекомендация по `switcher`.\n\n"
            "ФОРМАТ ВЫХОДА:\n"
            "- «Что я изменил в позиции»\n"
            "- «Юридическое ядро ответа»\n"
            "- «ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ ЮРИСТА ПО SWITCHER R2: true/false. Причина: …»"
        )
        return await self._complete(system, question, self._model_support)

    async def _r2_manager(
        self,
        client_context: str,
        question: str,
        r1_lawyer: str,
        r1_manager: str,
        r1_sales: str,
        r2_lawyer: str,
    ) -> str | None:
        system = (
            f"{COMPANY_FACTS}\n\n"
            "Ты — ИИ-менеджер сопровождения «Экспресс-Банкрот» на втором раунде.\n"
            "Сейчас нужно собрать из всех мнений то, что реально нужно сказать клиенту.\n\n"
            f"***КОНТЕКСТ:*** {client_context}\n"
            f"***ВОПРОС:*** {question}\n"
            f"***МНЕНИЯ:*** {r1_lawyer} | {r1_manager} | {r1_sales} | {r2_lawyer}\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Сформулировать 3–7 ключевых фраз для финального Координатора.\n"
            "2. Блок «Как объяснить ситуацию простым языком» (2–4 предложения).\n"
            "3. Блок «Как снизить тревожность».\n"
            "4. «Чего лучше не говорить клиенту».\n"
            "5. Финальная рекомендация по `switcher`.\n\n"
            "ФОРМАТ ВЫХОДА:\n"
            "- «Ключевые фразы для ответа»\n"
            "- «Как объяснить ситуацию простым языком»\n"
            "- «Как снизить тревожность»\n"
            "- «Чего лучше не говорить клиенту»\n"
            "- «ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ МЕНЕДЖЕРА ПО SWITCHER R2: true/false. Причина: …»"
        )
        return await self._complete(system, question, self._model_support)

    async def _r2_sales(
        self,
        client_context: str,
        question: str,
        r1_lawyer: str,
        r1_manager: str,
        r1_sales: str,
        r2_lawyer: str,
        r2_manager: str,
    ) -> str | None:
        system = (
            f"{COMPANY_FACTS}\n\n"
            "Ты — ИИ-куратор процесса и рисков «Экспресс-Банкрот» на втором раунде.\n"
            "Задача: посмотреть на ситуацию глазами операционного и репутационного риска.\n\n"
            f"***КОНТЕКСТ:*** {client_context}\n"
            f"***ВОПРОС:*** {question}\n"
            f"***МНЕНИЯ:*** {r1_lawyer} | {r1_manager} | {r1_sales} | {r2_lawyer} | {r2_manager}\n\n"
            "ТВОЯ ЗАДАЧА:\n"
            "1. Выделить рискованные формулировки и обещания.\n"
            "2. Отметить «страшные» сценарии только для внутреннего понимания.\n"
            "3. Определить, когда нужен живой специалист.\n"
            "4. Сформулировать краткие рекомендации финальному Координатору.\n"
            "5. Финальная рекомендация по `switcher`.\n\n"
            "ФОРМАТ ВЫХОДА:\n"
            "- «Рискованные обещания и формулировки»\n"
            "- «Только для внутреннего учёта (не говорить клиенту)»\n"
            "- «Когда нужен живой специалист»\n"
            "- «Рекомендации финальному Координатору»\n"
            "- «ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ КУРАТОРА ПО SWITCHER R2: true/false. Причина: …»"
        )
        return await self._complete(system, question, self._model_support)

    # ------------------------------------------------------------------
    # Prepare discussion
    # ------------------------------------------------------------------

    def _prepare_discussion(
        self,
        question: str,
        r1_lawyer: str,
        r1_manager: str,
        r1_sales: str,
        r2_lawyer: str,
        r2_manager: str,
        r2_sales: str,
        client_context: str,
    ) -> str:
        return (
            f"ВОПРОС КЛИЕНТА:\n{question}\n\n"
            f"=== РАУНД 1 ===\n"
            f"ЮРИСТ R1: {r1_lawyer}\n"
            f"МЕНЕДЖЕР R1: {r1_manager}\n"
            f"КУРАТОР R1: {r1_sales}\n\n"
            f"=== РАУНД 2 (КОРРЕКТИРОВКИ) ===\n"
            f"ЮРИСТ R2: {r2_lawyer}\n"
            f"МЕНЕДЖЕР R2: {r2_manager}\n"
            f"КУРАТОР R2: {r2_sales}\n\n"
            f"=== КОНТЕКСТ КЛИЕНТА ===\n{client_context}"
        )

    # ------------------------------------------------------------------
    # Coordinator (added in T05)
    # ------------------------------------------------------------------

    async def _coordinator(
        self, full_discussion: str, question: str, history: list[dict], eval_feedback: str = ""
    ) -> str | None:
        history_text = ""
        if history:
            lines = [f"{m['role'].upper()}: {m['content']}" for m in history]
            history_text = (
                "\n\nИСТОРИЯ ПРЕДЫДУЩЕГО ДИАЛОГА С КЛИЕНТОМ (для контекста):\n"
                + "\n".join(lines)
            )

        system = (
            f"{COMPANY_FACTS}\n\n"
            "Ты — финальный ИИ-менеджер сопровождения клиентов компании «Экспресс-Банкрот».\n"
            "Клиент видит ТОЛЬКО твой ответ. Всё, что написали другие агенты, — это внутренняя дискуссия.\n\n"
            "ТЕБЕ ПЕРЕДАНО:\n"
            "Полная внутренняя дискуссия команды (юрист R1+R2, менеджер R1+R2, куратор R1+R2) "
            "и контекст клиента в одном тексте:\n\n"
            f"{full_discussion}\n\n"
            "А также исходный вопрос клиента:\n\n"
            f"{question}"
            f"{history_text}\n\n"
            "---\n\n"
            "1) ФОРМАТ ОТВЕТА (СТРОГО JSON!)\n\n"
            "Ты ВСЕГДА отвечаешь строго в формате JSON без любого текста до или после, без ```json и т.п.:\n\n"
            '{"answer": "здесь твой ответ клиенту БЕЗ СМАЙЛИКОВ", "switcher": "true" или "false", "escalation_type": "none" или "conflict" или "request"}\n\n'
            'Если "switcher": "true" — выбери escalation_type:\n'
            '- "conflict" — при агрессии, угрозах, требовании вернуть деньги → answer: "Понимаю вашу озабоченность. Я передаю ваш запрос специалисту — он свяжется с вами в ближайшее время."\n'
            '- "request" — при просьбе связаться, вопросе про оплату/договор → answer: "Этот вопрос требует участия специалиста — я передала запрос, вам скоро ответят."\n\n'
            "---\n\n"
            "2) ЛОГИКА SWITCHER\n\n"
            "switcher=\"false\" (отвечаем сами) если вопрос касается: долгов, кредитов, МФО, статуса дела, "
            "этапа, сроков, заседаний, торгов, имущества, прожиточного минимума, карт, зарплаты, выезда за границу, "
            "последствий для работы/семьи/кредитной истории, документов, типичных страхов (коллекторы и т.п.).\n\n"
            "switcher=\"true\" если: клиент просит позвонить/записать/связаться, вопрос про оплату/возврат/договор "
            "с компанией, технические проблемы, жёсткая жалоба, вопросы про действия/контакты фин.управляющего, "
            "вопросы вне темы банкротства.\n\n"
            "---\n\n"
            "3) ОСОБЫЙ СЛУЧАЙ «ЧТО С МОИМ ДЕЛОМ?»\n\n"
            'Используй {"answer": "Уточните, пожалуйста, что именно вас интересует?", "switcher": "false"} '
            "ТОЛЬКО если вопрос — чистый общий (без слов про сроки/завершение).\n\n"
            "---\n\n"
            "4) ВОПРОСЫ О СРОКАХ: дай опору на дату, покажи что идёт по плану и есть контроль. "
            "Не нагнетай worst-case без прямого вопроса.\n\n"
            "---\n\n"
            "5) ЗАПРЕТ НА ВЫДУМАННЫЕ ДАТЫ: НИКОГДА не называй конкретную дату завершения процедуры, "
            "если она явно не указана в client_context именно как дата завершения/списания долгов. "
            "Даты из судебных документов (заседания, публикации, торги) — это НЕ дата завершения. "
            "Если точная дата неизвестна — скажи: «ориентировочно в течение нескольких месяцев» или «уточним с командой».\n\n"
            "---\n\n"
            "6) ГИПОТЕТИЧЕСКИЙ ВОПРОС vs РЕАЛЬНАЯ СИТУАЦИЯ: если клиент спрашивает о сценарии, "
            "который противоречит его реальному положению (например, «а если меня не признают?» — а он уже признан), "
            "мягко уточни его реальную ситуацию и ответь применительно к ней, а не к гипотезе.\n\n"
            "---\n\n"
            "7) КОНКРЕТНОСТЬ ОТВЕТА: отвечай ПРЯМО на заданный вопрос. Если вопрос требует конкретного "
            "ответа (число, дата, действие) — дай его. Фраза «мы контролируем процесс» без конкретики "
            "засчитывается как уход от ответа. Используй факты из client_context.\n\n"
            "---\n\n"
            "8) ПРОВЕРКА ДАТ: прошедшие даты — прошедшее время, будущие — будущее.\n\n"
            "---\n\n"
            "9) ФИНАНСОВЫЙ/АРБИТРАЖНЫЙ УПРАВЛЯЮЩИЙ: НЕЛЬЗЯ говорить «все вопросы через управляющего». "
            "Слова «управляющий», «финансовый управляющий», «арбитражный управляющий» — запрещены, "
            "кроме единственного исключения: если клиент прямо спросил ФИО и оно есть в контексте.\n\n"
            "---\n\n"
            "10) ТОН: 2–4 предложения, спокойный, поддерживающий, без смайликов и жёстких гарантий.\n\n"
            "---\n\n"
            "И ВСЕГДА возвращай РОВНО ОДИН JSON-объект без какого-либо текста вокруг."
            + (
                f"\n\n---\n\n⚠️ ПОВТОРНАЯ ПОПЫТКА — ПРЕДЫДУЩИЙ ОТВЕТ БЫЛ ОЦЕНЁН КАК НЕДОСТАТОЧНЫЙ:\n"
                f"{eval_feedback}\n"
                "Учти эти замечания и дай улучшенный ответ."
                if eval_feedback else ""
            )
        )
        return await self._complete(
            system,
            question,
            self._model_coordinator,
            max_tokens=400,
            temperature=0.6,
        )

    def _parse_coordinator_output(self, raw: str) -> dict:
        if not raw:
            return {"answer": None, "switcher": "false"}
        cleaned = raw.strip()
        # Strip ```json ... ``` wrappers if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            logger.warning("Coordinator returned invalid JSON: %s", raw[:200])
            return {"answer": None, "switcher": "false"}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def answer(
        self,
        chat_id: int,
        inn: str,
        question: str,
        contact_name: str,
        deal_profile: str = "",
    ) -> tuple[str, str, str]:
        """Return (answer_text, switcher, escalation_type).

        switcher: "true" | "false"
        escalation_type: "none" | "conflict" | "request"
        """
        history = await self._supabase.get_chat_history(chat_id)
        judicial_docs = await self._supabase.search_client_by_inn(inn)

        if deal_profile:
            client_context = f"{deal_profile}\n\n{judicial_docs}"
        else:
            client_context = judicial_docs

        # r1_lawyer and r1_sales are independent — run in parallel
        r1_lawyer, r1_sales = await asyncio.gather(
            self._r1_lawyer(client_context, question, history),
            self._r1_sales(client_context, question),
        )
        if r1_lawyer is None:
            raise RuntimeError("r1_lawyer returned None")
        if r1_sales is None:
            raise RuntimeError("r1_sales returned None")

        r1_manager = await self._r1_manager(client_context, question, r1_lawyer, history)
        if r1_manager is None:
            raise RuntimeError("r1_manager returned None")

        r2_lawyer = await self._r2_lawyer(client_context, question, r1_lawyer, r1_manager, r1_sales)
        if r2_lawyer is None:
            raise RuntimeError("r2_lawyer returned None")

        r2_manager = await self._r2_manager(client_context, question, r1_lawyer, r1_manager, r1_sales, r2_lawyer)
        if r2_manager is None:
            raise RuntimeError("r2_manager returned None")

        r2_sales = await self._r2_sales(client_context, question, r1_lawyer, r1_manager, r1_sales, r2_lawyer, r2_manager)
        if r2_sales is None:
            raise RuntimeError("r2_sales returned None")

        full_discussion = self._prepare_discussion(
            question, r1_lawyer, r1_manager, r1_sales,
            r2_lawyer, r2_manager, r2_sales, client_context,
        )

        raw = await self._coordinator(full_discussion, question, history)
        result = self._parse_coordinator_output(raw)

        # Inline quality gate — retry coordinator once if evaluator flags poor quality.
        # Skip retry for escalation answers (switcher=true): they're short by design.
        if self._evaluator and result.get("switcher") != "true":
            first_answer = result.get("answer") or ""
            try:
                scores = await self._evaluator.evaluate(
                    question=question,
                    answer=first_answer,
                    client_context=client_context,
                )
            except Exception:
                logger.exception("Inline evaluator failed — skipping retry")
                scores = None

            if scores and self._should_retry(scores):
                logger.info(
                    "Quality retry triggered — accuracy=%.1f completeness=%.1f | %s",
                    scores.get("accuracy", 0),
                    scores.get("completeness", 0),
                    scores.get("comment", "")[:120],
                )
                feedback = (
                    f"accuracy={scores.get('accuracy')}/5, "
                    f"completeness={scores.get('completeness')}/5, "
                    f"tone={scores.get('tone')}/5.\n"
                    f"Комментарий: {scores.get('comment', '')}"
                )
                raw = await self._coordinator(full_discussion, question, history, eval_feedback=feedback)
                result = self._parse_coordinator_output(raw)

        final_answer = result.get("answer") or FALLBACK_ALINA

        await self._supabase.save_chat_message(chat_id, "user", question)
        await self._supabase.save_chat_message(chat_id, "assistant", final_answer)

        switcher = result.get("switcher", "false")
        escalation_type = result.get("escalation_type", "none")
        return final_answer, switcher, escalation_type
