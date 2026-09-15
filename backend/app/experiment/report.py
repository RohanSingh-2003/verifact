"""Populate results_summary.md from stored experiment data only."""

from __future__ import annotations

import json
from pathlib import Path

from app.database.models import Experiment
from app.experiment.analysis import format_p_value


def write_results_summary(experiment: Experiment, path: Path) -> Path:
    try:
        summary = json.loads(experiment.summary_stats_json or "{}")
    except json.JSONDecodeError:
        summary = {}
    try:
        config = json.loads(experiment.config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    demo = experiment.llm_mode == "mock"
    means = {item.get("label"): item for item in summary.get("condition_summaries", [])}
    blocks = summary.get("self_verification", [])
    lines = [
        "# VeriFact results summary",
        "",
        "This file is generated from stored experiment data. It is not a substitute for the raw traces.",
        "",
        "### Dataset",
        f"- Name: {experiment.dataset_ref}",
        f"- Version: {experiment.dataset_version}",
        f"- Questions used: {summary.get('question_count', 0)}",
        "",
        "### Models",
        f"- Generators: {', '.join(json.loads(experiment.generator_models_json or '[]'))}",
        f"- Verifiers: {', '.join(json.loads(experiment.verifier_models_json or '[]'))}",
        f"- Mode: {'DEMO / MOCK DATA' if demo else 'LIVE EXPERIMENT'}",
        "",
        "### Experimental setup",
        f"- Mutations: {experiment.synonym_count} synonym + {experiment.antonym_count} antonym",
        f"- Threshold: {experiment.threshold}",
        f"- Trials: {experiment.trials}",
        f"- Temperature: {config.get('llm', {}).get('temperature', 0)}",
        f"- Mutation reuse valid: {summary.get('mutation_reuse_valid')}",
        "",
        "### MetaQA evaluation",
        "Baseline detector metrics are stored on the separate evaluation run, not in this 2×2 experiment file.",
        "",
        "### 2×2 experiment",
    ]
    for label in ["A → A", "A → B", "B → A", "B → B"]:
        item = means.get(label) or {}
        if item:
            lines.append(
                f"- {label}: mean={item.get('mean_score')} n={item.get('n')} "
                f"Reliable%={item.get('reliable_rate')} Hallucinated%={item.get('hallucinated_rate')}"
            )
    lines += ["", "### Statistical results"]
    for block in blocks:
        lines.append(
            f"- Generator {block.get('generator_model')}: same={block.get('same_model_mean')} "
            f"cross={block.get('cross_model_mean')} difference={block.get('self_verification_score_difference')} "
            f"flip_rate={block.get('classification_flip_rate')} "
            f"{format_p_value(block.get('wilcoxon', {}).get('p_value'))} "
            f"effect_size={block.get('wilcoxon', {}).get('effect_size')} "
            f"significant={block.get('significant')} exploratory={block.get('exploratory')}"
        )
    lines += [
        "",
        "### Classification flips",
        f"- Overall flip rate: {summary.get('classification_flip_rate')}",
        "",
        "### Category analysis",
    ]
    for row in summary.get("category_analysis") or []:
        lines.append(
            f"- {row.get('category')} / {row.get('generator_model')}: n={row.get('n')} "
            f"difference={row.get('score_difference')} flip_rate={row.get('flip_rate')}"
        )
    if not summary.get("category_analysis"):
        lines.append("- No category rows were available.")
    lines += [
        "",
        "### Limitations",
        "- Results apply only to the selected models, dataset, prompts, and mutation configuration.",
        "- They do not establish a universal self-verification bias.",
        "- Ground-truth matching is applied after detection and may mark items Needs Review.",
        "- See docs/limitations.md.",
        "",
        "### Key finding",
        summary.get("key_finding") or "No finding text was stored.",
        "",
    ]
    if demo:
        lines.insert(4, "**DEMO / MOCK DATA — not a live-model research result.**")
        lines.insert(5, "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
