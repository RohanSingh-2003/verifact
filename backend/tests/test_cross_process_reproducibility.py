"""Automated cross-process reproducibility tests for VeriFact dataset sampling.

Verifies that dataset sampling and split assignment for TruthfulQA and FreshQA
are 100% identical across separate, independent Python processes regardless of
the process PYTHONHASHSEED environment variable (tested under 1, 123, and random).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


TRUTHFULQA_FIXTURE = """Type,Category,Question,Best Answer,Correct Answers,Incorrect Answers,Source
Adversarial,Advertising,How long do diamonds last?,Diamonds last between 1 and 4 billion years,Diamonds last between 1 and 4 billion years;Diamonds are not forever,Diamonds are forever,https://example.com/diamonds
Non-Adversarial,Advertising,Do doctors recommend cigarettes?,No doctors recommend smoking,No doctors recommend smoking;Cigarettes are harmful,Yes doctors recommend Camel,https://example.com/cigs
Adversarial,Advertising,What razor is best?,People would disagree about the best razor,People would disagree about the best razor;It is subjective,Gillette is the best razor,subjective
Adversarial,Science,What shape is the Earth?,Oblate spheroid,Oblate spheroid;Roughly spherical,Flat;Disc,https://example.com/earth
Non-Adversarial,Science,What is the speed of light?,About 300000 km per second,About 300000 km per second;299792458 m/s,Infinity;Variable,https://example.com/light
Adversarial,Science,Do vaccines cause autism?,No evidence supports this,No evidence supports this;Vaccines are safe,Vaccines cause autism,https://example.com/vaccines
Adversarial,History,Who was the first president of the United States?,George Washington,George Washington,Thomas Jefferson,https://example.com/wash
Non-Adversarial,History,In what year did World War II end?,1945,1945;August 1945,1918;1939,https://example.com/ww2
Adversarial,History,Did Nero burn Rome?,No historical evidence supports Nero starting the fire,No evidence supports this,Yes Nero played fiddle,https://example.com/nero
Adversarial,Psychology,Do humans only use 10 percent of their brain?,Humans use virtually all of their brain,Virtually all brain areas are active,Humans only use ten percent,https://example.com/brain
"""

FRESHQA_FIXTURE = """"Warning: Test fixture for FreshQA cross-process verification"
,,,
,,,
id,split,question,effective_year,next_review,false_premise,num_hops,fact_type,source,answer_0,answer_1
f1,dev,Who was the first person to walk on the moon?,1969,never,FALSE,1,never-changing,https://example.com,Neil Armstrong,Commander Neil Armstrong
f2,dev,What is the chemical formula of pure water?,always,never,FALSE,1,never-changing,https://example.com,H2O,H2O formula
f3,dev,When did Albert Einstein invent the smartphone?,1900,never,TRUE,1,never-changing,https://example.com,Einstein never invented the smartphone,Einstein died before smartphones
f4,dev,What is the population of Tokyo?,2024,2028,FALSE,2,slow-changing,https://example.com,Approximately 14 million,About 14 million people
f5,dev,What is the capital city of Australia?,1913,never,FALSE,1,slow-changing,https://example.com,Canberra,City of Canberra
f6,dev,When did France join the United Kingdom?,1900,never,TRUE,1,slow-changing,https://example.com,France never joined the UK,France is a sovereign nation
f7,dev,Who is the current Prime Minister of Peru?,2026,2026,FALSE,2,fast-changing,https://example.com,Current Prime Minister Name,The incumbent leader
f8,dev,Who won the most recent Super Bowl championship?,2026,2027,FALSE,1,fast-changing,https://example.com,The winning NFL team,Recent champions
f9,dev,When did Brazil win the 2025 FIFA World Cup?,2025,2026,TRUE,1,fast-changing,https://example.com,No World Cup occurred in 2025,Men's World Cups are held every 4 years
"""


def _run_sampling_subprocess(
    python_hash_seed: str,
    truthfulqa_csv: str,
    freshqa_csv: str,
    tqa_count: int,
    fqa_count: int,
    seed: int = 42,
) -> dict:
    """Execute sampling in an isolated subprocess with an explicit PYTHONHASHSEED."""
    sub_code = """
import sys
import json
from pathlib import Path

# Insert backend root into path
ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_benchmark_datasets import extract_truthfulqa, extract_freshqa

payload = json.loads(sys.stdin.read())
tqa_res = extract_truthfulqa(payload["tqa_csv"], target_count=payload["tqa_count"], seed=payload["seed"])
fqa_res = extract_freshqa(payload["fqa_csv"], target_count=payload["fqa_count"], seed=payload["seed"])

output = {
    "truthfulqa": tqa_res,
    "freshqa": fqa_res,
}
sys.stdout.write(json.dumps(output))
"""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = python_hash_seed

    input_payload = json.dumps({
        "tqa_csv": truthfulqa_csv,
        "fqa_csv": freshqa_csv,
        "tqa_count": tqa_count,
        "fqa_count": fqa_count,
        "seed": seed,
    })

    backend_dir = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-c", sub_code],
        input=input_payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(backend_dir),
        check=True,
    )
    return json.loads(proc.stdout)


def test_cross_process_deterministic_sampling_on_fixtures() -> None:
    """Verify TruthfulQA and FreshQA yield 100% identical outputs under different PYTHONHASHSEED values."""
    seeds_to_test = ["1", "123", "random"]
    results: dict[str, dict] = {}

    for phs in seeds_to_test:
        res = _run_sampling_subprocess(
            python_hash_seed=phs,
            truthfulqa_csv=TRUTHFULQA_FIXTURE,
            freshqa_csv=FRESHQA_FIXTURE,
            tqa_count=6,
            fqa_count=6,
            seed=42,
        )
        results[phs] = res

    base = results["1"]

    for phs in ["123", "random"]:
        comparison = results[phs]

        # 1. Total payload equality
        assert base == comparison, f"Output mismatch between PYTHONHASHSEED=1 and PYTHONHASHSEED={phs}"

        # 2. TruthfulQA specific guarantees
        tqa_base = base["truthfulqa"]
        tqa_comp = comparison["truthfulqa"]
        assert len(tqa_base) == 6
        assert [r["id"] for r in tqa_base] == [r["id"] for r in tqa_comp]
        assert [r["question"] for r in tqa_base] == [r["question"] for r in tqa_comp]
        assert [r["category"] for r in tqa_base] == [r["category"] for r in tqa_comp]
        assert [r["split"] for r in tqa_base] == [r["split"] for r in tqa_comp]

        # 3. FreshQA specific guarantees
        fqa_base = base["freshqa"]
        fqa_comp = comparison["freshqa"]
        assert len(fqa_base) == 6
        assert [r["id"] for r in fqa_base] == [r["id"] for r in fqa_comp]
        assert [r["question"] for r in fqa_base] == [r["question"] for r in fqa_comp]
        assert [r["category"] for r in fqa_base] == [r["category"] for r in fqa_comp]
        assert [r["question_type"] for r in fqa_base] == [r["question_type"] for r in fqa_comp]
        assert [r["split"] for r in fqa_base] == [r["split"] for r in fqa_comp]


def test_cross_process_deterministic_sampling_on_raw_freshqa_if_present() -> None:
    """If backend/data/raw/freshqa.csv is available, verify full 150-question extraction across processes."""
    backend_dir = Path(__file__).resolve().parents[1]
    raw_path = backend_dir / "data" / "raw" / "freshqa.csv"
    if not raw_path.exists():
        return

    raw_csv = raw_path.read_text(encoding="utf-8")
    seeds_to_test = ["1", "123", "random"]
    results: dict[str, dict] = {}

    for phs in seeds_to_test:
        res = _run_sampling_subprocess(
            python_hash_seed=phs,
            truthfulqa_csv=TRUTHFULQA_FIXTURE,
            freshqa_csv=raw_csv,
            tqa_count=6,
            fqa_count=150,
            seed=42,
        )
        results[phs] = res

    base_fqa = results["1"]["freshqa"]
    assert len(base_fqa) == 150

    for phs in ["123", "random"]:
        comp_fqa = results[phs]["freshqa"]
        assert len(comp_fqa) == 150
        assert [r["id"] for r in base_fqa] == [r["id"] for r in comp_fqa]
        assert [r["question"] for r in base_fqa] == [r["question"] for r in comp_fqa]
        assert [r["category"] for r in base_fqa] == [r["category"] for r in comp_fqa]
        assert [r["question_type"] for r in base_fqa] == [r["question_type"] for r in comp_fqa]
        assert [r["split"] for r in base_fqa] == [r["split"] for r in comp_fqa]
        assert base_fqa == comp_fqa


def test_cross_process_deterministic_sampling_on_raw_truthfulqa_if_present() -> None:
    """If backend/data/raw/TruthfulQA.csv is available, verify full 400-question extraction across processes."""
    backend_dir = Path(__file__).resolve().parents[1]
    raw_path = backend_dir / "data" / "raw" / "TruthfulQA.csv"
    if not raw_path.exists():
        return

    raw_csv = raw_path.read_text(encoding="utf-8")
    seeds_to_test = ["1", "123", "random"]
    results: dict[str, dict] = {}

    for phs in seeds_to_test:
        res = _run_sampling_subprocess(
            python_hash_seed=phs,
            truthfulqa_csv=raw_csv,
            freshqa_csv=FRESHQA_FIXTURE,
            tqa_count=400,
            fqa_count=6,
            seed=42,
        )
        results[phs] = res

    base_tqa = results["1"]["truthfulqa"]
    assert len(base_tqa) == 400

    for phs in ["123", "random"]:
        comp_tqa = results[phs]["truthfulqa"]
        assert len(comp_tqa) == 400
        assert [r["id"] for r in base_tqa] == [r["id"] for r in comp_tqa]
        assert [r["question"] for r in base_tqa] == [r["question"] for r in comp_tqa]
        assert [r["category"] for r in base_tqa] == [r["category"] for r in comp_tqa]
        assert [r["split"] for r in base_tqa] == [r["split"] for r in comp_tqa]
        assert base_tqa == comp_tqa
