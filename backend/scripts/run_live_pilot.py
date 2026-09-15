"""Run the live MetaQA evaluation and/or 2x2 experiment after explicit confirmation.

Example:
  py -3 scripts/run_live_pilot.py --confirm --stage all --max-questions 40
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.database.db import SessionLocal, init_db
from app.evaluation.evaluator import run_evaluation
from app.experiment.cost import estimate_evaluation_calls, estimate_experiment_calls
from app.llm.client import OpenAICompatibleClient
from app.schemas.experiment import ExperimentRunRequest
from app.services.experiment_service import run_experiment


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the confirmed live VeriFact pilot.")
    parser.add_argument("--confirm", action="store_true", help="Required for any live run larger than one question.")
    parser.add_argument("--stage", choices=["eval", "experiment", "all"], default="all")
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--dataset", default="pilot")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.live_ready:
        print("Live pilot did not run: LLM_MODE is not live or OPENAI_API_KEY is not configured.")
        return 2
    limit = args.max_questions or settings.max_questions
    mutations = settings.synonym_count + settings.antonym_count
    eval_est = estimate_evaluation_calls(questions=limit, mutations=mutations)
    exp_est = estimate_experiment_calls(questions=limit, mutations=mutations)
    print(f"Dataset: {args.dataset}")
    print(f"Models A/B: {settings.generator_model_a} / {settings.generator_model_b}")
    print(f"MAX_QUESTIONS: {limit}")
    print(f"Estimated evaluation calls: {eval_est['total_calls']}")
    print(f"Estimated 2x2 calls: {exp_est['total_calls']}")
    if limit > settings.live_unconfirmed_max_questions and not args.confirm:
        print("Refusing to launch. Pass --confirm after reviewing the estimated LLM calls.")
        return 2

    init_db()
    llm = OpenAICompatibleClient(settings)
    db = SessionLocal()
    try:
        if args.stage in {"eval", "all"}:
            evaluation = await run_evaluation(
                llm=llm,
                db=db,
                settings=settings,
                dataset=args.dataset,
                max_questions=limit,
                confirm_live_run=True,
                generator_model=settings.generator_model_a,
                verifier_model=settings.verifier_model_a,
            )
            db.commit()
            print(f"Evaluation completed id={evaluation.id} status={evaluation.status}")
        if args.stage in {"experiment", "all"}:
            generators, verifiers = settings.experiment_models()
            experiment = await run_experiment(
                llm=llm,
                db=db,
                settings=settings,
                payload=ExperimentRunRequest(
                    dataset=args.dataset,
                    generator_models=generators,
                    verifier_models=verifiers,
                    max_questions=limit,
                    confirm_live_run=True,
                ),
            )
            db.commit()
            print(f"Experiment completed id={experiment.id} status={experiment.status}")
    finally:
        db.close()
        await llm.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
