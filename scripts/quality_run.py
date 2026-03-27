"""Quality evaluation script for Alina AI responses.

Usage:
    # Anonymous run (no client context — specificity will be low by design):
    python scripts/quality_run.py --output results.json

    # With real client INN — fetches judicial docs + Bitrix deal profile:
    python scripts/quality_run.py --inn 123456789012 --output results_real.json

    # Limit questions for a quick smoke test:
    python scripts/quality_run.py --limit 5 --output test_results.json

Each question runs with its own unique negative chat_id so histories don't
bleed between questions.
"""

import argparse
import asyncio
import json
import logging
import pathlib
import re
import sys

# Allow running from project root
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import aiohttp

from config import settings
from services.bitrix import BitrixService
from services.evaluator import EvaluatorService
from services.support import SupportService
from services.supabase_support import SupportSupabaseService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("quality_run")

QUESTIONS_FILE = (
    pathlib.Path(__file__).parent.parent / "docs" / "5. SUP-unsorted" / "questions.md"
)

# Base for synthetic chat_ids — each question gets its own to prevent history bleed.
# Negative range won't collide with real Telegram user IDs (always positive).
EVAL_CHAT_ID_BASE = -10000


def load_questions(limit: int) -> list[str]:
    """Parse numbered questions from questions.md."""
    lines = QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
    questions = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Match lines starting with a number and dot/period: "1. text" or "1) text"
        m = re.match(r"^\d+[.)]\s+(.+)", line)
        if m:
            questions.append(m.group(1).strip())
        if len(questions) >= limit:
            break
    return questions


async def resolve_client(
    session: aiohttp.ClientSession, inn: str
) -> tuple[str, str, str]:
    """Return (inn, contact_name, deal_profile) for a given INN.

    Falls back gracefully if Bitrix is unavailable.
    """
    bitrix = BitrixService(session)
    try:
        result = await bitrix.search_by_inn(inn)
    except Exception:
        logger.exception("Bitrix search_by_inn failed for inn=%s", inn)
        result = None

    if not result:
        logger.warning("INN %s not found in Bitrix — running without deal profile", inn)
        return inn, "Клиент", ""

    contact_name = result.get("contact_name", "Клиент")
    deal_id = result.get("deal_id", "")

    deal_profile = ""
    if deal_id:
        try:
            deal_profile = await bitrix.get_deal_profile(deal_id)
        except Exception:
            logger.exception("get_deal_profile failed for deal_id=%s", deal_id)

    logger.info(
        "Client resolved: %s | deal_id=%s | profile_len=%d",
        contact_name,
        deal_id,
        len(deal_profile),
    )
    return inn, contact_name, deal_profile


async def run(limit: int, output_path: pathlib.Path, inn: str) -> None:
    questions = load_questions(limit)
    if not questions:
        logger.error("No questions found in %s", QUESTIONS_FILE)
        sys.exit(1)
    logger.info("Loaded %d questions", len(questions))

    async with aiohttp.ClientSession() as session:
        supabase_support = SupportSupabaseService(
            session=session,
            url=settings.supabase_support_url,
            anon_key=settings.supabase_support_anon_key,
        )
        support_svc = SupportService(
            http_session=session,
            supabase_support=supabase_support,
            openai_api_key=settings.openai_api_key,
            model_support=settings.openai_model_support,
            model_coordinator=settings.openai_model_coordinator,
            openai_proxy=settings.openai_proxy,
        )
        evaluator = EvaluatorService(
            http_session=session,
            openai_api_key=settings.openai_api_key,
            model=settings.openai_model_coordinator,
            openai_proxy=settings.openai_proxy,
        )

        # Resolve client context once — reused across all questions
        resolved_inn, contact_name, deal_profile = await resolve_client(session, inn)
        if resolved_inn:
            logger.info("Running with client context (inn=%s, name=%s)", resolved_inn, contact_name)
        else:
            logger.info("Running without client context (anonymous mode)")

        results = []
        for i, question in enumerate(questions, 1):
            # Each question gets its own isolated chat_id — no history bleed
            chat_id = EVAL_CHAT_ID_BASE - i
            logger.info("[%d/%d] %s", i, len(questions), question[:80])

            try:
                answer = await support_svc.answer(
                    chat_id=chat_id,
                    inn=resolved_inn,
                    question=question,
                    contact_name=contact_name,
                    deal_profile=deal_profile,
                )
            except Exception:
                logger.exception("SupportService.answer failed for question %d", i)
                answer = ""

            scores = None
            if answer:
                try:
                    scores = await evaluator.evaluate(
                        question=question,
                        answer=answer,
                        client_context=deal_profile,
                    )
                except Exception:
                    logger.exception("EvaluatorService.evaluate failed for question %d", i)

            results.append(
                {
                    "index": i,
                    "question": question,
                    "answer": answer,
                    "scores": scores,
                }
            )

        # Compute summary statistics
        valid_scores = [r["scores"] for r in results if r["scores"]]
        summary: dict = {
            "total_questions": len(results),
            "evaluated": len(valid_scores),
            "inn": resolved_inn or "anonymous",
            "contact_name": contact_name,
        }
        if valid_scores:
            for key in ("specificity", "accuracy", "tone", "completeness", "total"):
                vals = [s[key] for s in valid_scores if key in s]
                if vals:
                    summary[f"avg_{key}"] = round(sum(vals) / len(vals), 2)

        output = {"summary": summary, "results": results}
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Results saved to %s", output_path)

        # Print summary to stdout
        print("\n=== Quality Run Summary ===")
        print(f"Client: {contact_name} (inn={resolved_inn or 'anonymous'})")
        print(f"Questions evaluated: {summary['evaluated']} / {summary['total_questions']}")
        for key in ("specificity", "accuracy", "tone", "completeness", "total"):
            avg_key = f"avg_{key}"
            if avg_key in summary:
                print(f"  {key}: {summary[avg_key]:.2f} / 5")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Alina AI response quality")
    parser.add_argument("--limit", type=int, default=92, help="Number of questions to evaluate")
    parser.add_argument("--output", type=str, default="results.json", help="Output JSON file path")
    parser.add_argument(
        "--inn", type=str, default="",
        help="Real client INN to fetch judicial docs + Bitrix deal profile (optional)"
    )
    args = parser.parse_args()

    output_path = pathlib.Path(args.output)
    asyncio.run(run(args.limit, output_path, args.inn))


if __name__ == "__main__":
    main()
