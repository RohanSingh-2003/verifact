# Project description

## 50-word version

VeriFact is a MetaQA-based application for detecting fact-conflicting hallucinations in LLM answers. It paraphrases and negates a generated answer, asks a verifier for YES, NO, or NOT SURE, and averages MetaQA contribution scores. A separate 2×2 experiment compares same-model and cross-model verification with frozen mutation sets. Ground truth is used only after detection.

## 100-word version

VeriFact implements the existing MetaQA metamorphic methodology as an interactive detector and research scaffold. A generator produces a base answer; synonym and antonym mutations are verified without web search, Wikipedia, RAG, embeddings, or external fact-checking APIs. Scores follow the MetaQA table (synonym YES=0/NO=1; antonym YES=1/NO=0; NOT SURE=0.5) and a 0.5 threshold. VeriFact also runs a 2×2 study: each answer and mutation set is generated once and judged by two verifiers, isolating verifier identity. Evaluation metrics and Wilcoxon tests use stored outputs. The repository’s completed 40-question 2×2 is mock-mode; live LLM findings are not claimed.

## 250-word version

Fact-conflicting hallucinations are fluent LLM answers that contradict established facts. VeriFact (“Verify what AI says”) is a software implementation of MetaQA, an existing metamorphic detection method. It does not claim to have invented MetaQA. The system generates a candidate answer, produces meaning-preserving and meaning-reversing restatements, and asks a verifier whether each restatement holds. Parsed verdicts become numeric contributions, the hallucination score is their mean, and scores at or above a threshold (default 0.5) are labeled Hallucinated. Verifier rationales are stored for explanation and do not enter the score.

The detector is zero-resource: it does not retrieve Google, Wikipedia, RAG corpora, vector databases, embeddings, or fact-checking APIs. References exist only in a post-detection evaluation layer, where answers can be labeled Reliable, Hallucinated, or Needs Review.

The research question is whether using the same model as generator and verifier produces systematically different scores than a different verifier, after accounting for verifier calibration. The experiment is a 2×2 of generators A/B and verifiers A/B. For each question the answer and mutation set are frozen; only verifier identity changes. Analysis reports condition means, NOT SURE rates, classification flips, paired Wilcoxon tests, and a threshold sweep on stored scores.

The locked repository experiment (`58baff20-fb86-4f43-b20e-895a086ceb6b`, 40 pilot questions) ran in mock mode with placeholder models `model-a` and `model-b`. Those results demonstrate the pipeline and a verifier-calibration confound; they are not live-model findings. The live-LLM hypothesis remains inconclusive until a confirmed live run is stored.
