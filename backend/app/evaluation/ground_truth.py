
"""Ground-truth labeling, kept entirely outside the MetaQA detector.



The detector never receives reference answers, aliases, or evaluation labels.

This module only compares an already-generated base answer to dataset fields.



Priority:

1. Explicit needs_review flag → excluded from automatic P/R/F1

2. Manually stored ground_truth_label → used as actual label

3. Normalized reference/alias matching as a fallback



Normalized matching is not claimed to be perfect semantic evaluation.

Ambiguous cases are marked Needs Review and excluded from metrics.

"""



from __future__ import annotations
from typing import Literal



import re



from app.evaluation.schemas import DatasetExample, GroundTruthDecision, GroundTruthSource

from app.metaqa.scoring import Classification



_PUNCT = re.compile(r"[^\w\s+-]", re.UNICODE)

_SPACE = re.compile(r"\s+")

_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+")

_DECIMAL = re.compile(r"(?<=\d)\.(?=\d)")

_UNCERTAIN = re.compile(

    r"\b(i do not know|i don't know|not sure|unknown|cannot answer|no idea|n/?a)\b",

    re.IGNORECASE,

)





def normalize_answer(value: str) -> str:

    text = value.replace("\u2019", "'").casefold().strip()

    text = text.replace(",", "")

    text = _DECIMAL.sub("DECIMAL", text)

    text = _PUNCT.sub(" ", text)

    text = text.replace("DECIMAL", ".")

    text = _SPACE.sub(" ", text).strip()

    text = _LEADING_ARTICLE.sub("", text)

    return text





def answers_equivalent(generated: str, reference: str) -> bool:

    gen = normalize_answer(generated)

    ref = normalize_answer(reference)

    if not gen or not ref:

        return False

    if gen == ref:

        return True

    gen_tokens = gen.split()

    if _is_numeric_ref(ref):

        return ref in gen_tokens

    if _too_weak_token(ref) or _too_weak_token(gen):

        return False

    return ref in gen or gen in ref





def _is_numeric_ref(value: str) -> bool:

    compact = value.replace(" ", "").replace(".", "")

    return compact.isdigit()





def _too_weak_token(value: str) -> bool:

    if value.isdigit():

        return False

    return len(value) < 2





def match_reference(generated: str, example: DatasetExample) -> bool | None:

    """Return True (correct), False (incorrect), or None (ambiguous)."""

    generated_clean = generated.strip()

    if not generated_clean:

        return None

    if _UNCERTAIN.search(generated_clean):

        return None

    candidates = [example.reference_answer, *example.aliases]

    usable = [item for item in candidates if normalize_answer(item)]

    if not usable:

        return None

    if any(answers_equivalent(generated_clean, item) for item in usable):

        return True

    return False





def resolve_ground_truth(

    generated_answer: str,

    example: DatasetExample,

    *,

    mode: Literal["formal", "legacy"] = "legacy",

    adjudicated_label: Classification | str | None = None,

) -> GroundTruthDecision:

    # 1. Definitive human-adjudicated label takes precedence over stale needs_review flag
    if adjudicated_label is not None:
        raw_adj = (
            adjudicated_label.value
            if isinstance(adjudicated_label, Classification)
            else str(adjudicated_label).strip().capitalize()
        )
        if raw_adj in {Classification.RELIABLE.value, Classification.HALLUCINATED.value}:
            return GroundTruthDecision(
                label=Classification(raw_adj),
                source=GroundTruthSource.ADJUDICATED,
                notes="Definitive human-adjudicated ground truth label.",
            )
        # If adjudication explicitly marks it as unresolvable / needs review
        return GroundTruthDecision(
            label=None,
            source=GroundTruthSource.NEEDS_REVIEW,
            notes="Human adjudication flagged this example as requiring review / unresolvable.",
        )

    # 2. Explicit needs_review flag
    if example.needs_review:
        return GroundTruthDecision(
            label=None,
            source=GroundTruthSource.NEEDS_REVIEW,
            notes="Dataset flagged this example for manual review.",
        )



    # 3. Explicit validated dataset ground truth label

    if example.ground_truth_label is not None:

        return GroundTruthDecision(

            label=example.ground_truth_label,

            source=GroundTruthSource.MANUAL,

            notes="Using validated label of generated-answer correctness.",

        )



    # 4. Formal benchmark mode requires explicit validated labels

    if mode == "formal":

        return GroundTruthDecision(

            label=None,

            source=GroundTruthSource.UNVALIDATED,

            notes="Formal benchmark mode requires an explicit validated ground-truth label. Unvalidated example excluded from decisive metrics.",

        )



    # 5. Legacy pilot mode fallback: normalized reference/alias matching

    matched = match_reference(generated_answer, example)

    if matched is None:

        return GroundTruthDecision(

            label=None,

            source=GroundTruthSource.NEEDS_REVIEW,

            matched=None,

            notes="Reference match was ambiguous; excluded from automatic metrics.",

        )

    return GroundTruthDecision(

        label=Classification.RELIABLE if matched else Classification.HALLUCINATED,

        source=GroundTruthSource.REFERENCE_MATCH,

        matched=matched,

        notes="Fallback normalized reference match (legacy pilot mode); not validated for formal benchmark claims.",

    )

