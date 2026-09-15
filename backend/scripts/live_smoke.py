"""Single-question live smoke test for Model A and Model B.

Does not run the 40-question pilot. Requires LLM_MODE=live and a real API key.
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
from app.llm.client import OpenAICompatibleClient
from app.llm.instrumented import InstrumentedLLMClient
from app.metaqa.detector import generate_answer
from app.metaqa.mutation import generate_mutations
from app.metaqa.verifier import verify_mutation


QUESTION = "What is the capital of France?"


async def main() -> int:
    settings = get_settings()
    if not settings.live_ready:
        print("Live smoke test did not run: LLM_MODE is not live or OPENAI_API_KEY is not configured.")
        print("Set LLM_MODE=live and a real OPENAI_API_KEY in backend/.env, then rerun.")
        return 2
    models = settings.experiment_models()
    model_a, model_b = models[0]
    llm = InstrumentedLLMClient(OpenAICompatibleClient(settings))
    print(f"Testing Model A generate: {model_a}")
    answer_a = await generate_answer(llm, QUESTION, model_a)
    print(f"A answer: {answer_a.text[:200]}")
    print(f"Testing Model B generate: {model_b}")
    answer_b = await generate_answer(llm, QUESTION, model_b)
    print(f"B answer: {answer_b.text[:200]}")
    mutations = await generate_mutations(
        llm,
        model=model_a,
        question=QUESTION,
        answer=answer_a.text,
        synonym_count=1,
        antonym_count=1,
    )
    statement = mutations[0].mutated_text
    print(f"Testing Model A verify: {model_a}")
    result_a = await verify_mutation(llm, model=model_a, question=QUESTION, answer=answer_a.text, statement=statement)
    print(f"A verdict: {result_a.verdict.value}")
    print(f"Testing Model B verify: {model_b}")
    result_b = await verify_mutation(llm, model=model_b, question=QUESTION, answer=answer_a.text, statement=statement)
    print(f"B verdict: {result_b.verdict.value}")
    print(f"LLM calls: {llm.stats()}")
    print("Smoke test completed. Mutation set was not regenerated between verifiers.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate both live models with one question.")
    parser.parse_args()
    raise SystemExit(asyncio.run(main()))
