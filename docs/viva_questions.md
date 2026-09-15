# Viva / defense questions

Concise answers. Frozen 2×2 is **mock** unless a live run is stored.

1. **What is an LLM hallucination?**  
A fluent output that is not faithful to facts, instructions, or context. VeriFact focuses on **fact-conflicting** answers.

2. **What is a fact-conflicting hallucination?**  
An answer that contradicts an established fact (wrong person, place, date, or quantity).

3. **What is MetaQA?**  
An existing metamorphic detection methodology: mutate the answer, verify, score, classify. VeriFact implements it; it did not invent it.

4. **What is metamorphic testing here?**  
Relations that should hold without a full oracle: paraphrases should agree; negations should not.

5. **Why synonym mutations?**  
Meaning-preserving restatements. Expected verifier verdict: YES.

6. **Why antonym mutations?**  
Meaning-reversing restatements. Expected verdict: NO.

7. **What does the verifier do?**  
Labels each mutated statement YES, NO, or NOT SURE. It is not told mutation type or expected label.

8. **Why NOT SURE?**  
Indecision or unparseable output maps to 0.5 and is reported as a rate. It is not treated as a third classification of the answer.

9. **How does the threshold work?**  
Score ≥ 0.5 → Hallucinated, else Reliable. Sweeps on stored scores do not change the default 0.5.

10. **What does zero-resource mean?**  
No Google, Wikipedia, RAG, embeddings, or fact-checking APIs in the detector.

11. **What is same-model verification?**  
The verifier model string equals the generator (A→A or B→B).

12. **What is cross-model verification?**  
A different verifier (A→B or B→A).

13. **Why a 2×2?**  
To see generator effects, verifier effects, and pairing without collapsing to one contrast.

14. **What is the main confound?**  
Verifier calibration (strictness). Averaging only the diagonal vs off-diagonal mixes pairing with who the verifier is.

15. **Why Wilcoxon?**  
Paired score differences; non-parametric; alpha 0.05. We say “no statistically significant difference was detected,” not “there is no difference.”

16. **Where is ground truth used?**  
After detection, to label the generated answer. It is not in MetaQA prompts.

17. **What are precision, recall, and F1 here?**  
Positive class = Hallucinated. Needs Review items are excluded from automatic P/R/F1.

18. **What did the locked experiment find?**  
Mock 40-question 2×2: scores 0 vs 1 by verifier identity; hypothesis **inconclusive** for live LLMs.

19. **Architecture?**  
React + Vite + TypeScript UI; FastAPI; SQLite traces; generator/verifier LLM client.

20. **Why SQLite?**  
Local, auditable traces for a research prototype. Not a claim of production scale.

21. **API design?**  
`POST /api/detect`, run history, `/api/experiments/*`, `/api/evaluations/*`, `/api/settings` without secrets.

22. **How would this scale?**  
Batching, more concurrency, a stronger store, and live cost controls already exist as confirm gates. The MetaQA table would stay the same.

23. **Why freeze mutation sets?**  
So verifier identity is the intended paired difference.

24. **Do rationales affect the score?**  
No.

25. **Is VeriFact production-ready?**  
No. It is a research-oriented application / research prototype.
