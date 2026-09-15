"""LLM call estimates. Exact counts, not marketing approximations."""

from __future__ import annotations


def estimate_experiment_calls(
    *,
    questions: int,
    generators: int = 2,
    verifiers: int = 2,
    mutations: int = 10,
    trials: int = 1,
) -> dict:
    per_generator = 2 + mutations * verifiers  # answer + mutation batch + each mutation × verifier
    per_question = per_generator * generators
    total = per_question * questions * trials
    return {
        "questions": questions,
        "generators": generators,
        "verifiers": verifiers,
        "mutations": mutations,
        "trials": trials,
        "calls_per_generator": per_generator,
        "calls_per_question": per_question,
        "total_calls": total,
        "notes": (
            "Each generator: 1 answer + 1 mutation-generation call + "
            f"{mutations} verifications per verifier × {verifiers} verifiers."
        ),
    }


def estimate_evaluation_calls(*, questions: int, mutations: int = 10) -> dict:
    per_question = 2 + mutations
    return {
        "questions": questions,
        "mutations": mutations,
        "calls_per_question": per_question,
        "total_calls": per_question * questions,
    }
