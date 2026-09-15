# Figures

Locked experiment for result plots: `58baff20-fb86-4f43-b20e-895a086ceb6b` (**DEMO / MOCK DATA**). Methodology figures do not depend on live LLM calls.

Figures 4–9 plot saved mock scores. They are labeled DEMO / MOCK DATA and must not be cited as live-model findings.

| Figure | Title | File |
| --- | --- | --- |
| Figure 1 | VeriFact System Architecture | [docs/architecture.png](architecture.png) |
| Figure 2 | MetaQA Detection Workflow / research flow | [docs/research_flow.png](research_flow.png) |
| Figure 3 | 2×2 Experimental Design | [docs/figures/fig3_2x2_design.png](figures/fig3_2x2_design.png) |
| Figure 4 | Mean Hallucination Score by Condition | [docs/figures/fig4_mean_scores.png](figures/fig4_mean_scores.png) |
| Figure 5 | Paired Same-vs-Cross Differences | [docs/figures/fig5_paired_differences.png](figures/fig5_paired_differences.png) |
| Figure 6 | Threshold vs F1 | [docs/figures/fig6_threshold_f1.png](figures/fig6_threshold_f1.png) |
| Figure 7 | Confusion Matrix | [docs/figures/fig8_confusion_matrix.png](figures/fig8_confusion_matrix.png) |
| Figure 8 | NOT SURE Rate | [docs/figures/fig9_not_sure.png](figures/fig9_not_sure.png) |
| Figure 9 | Classification Flip Rate | [docs/figures/fig10_flip_rate.png](figures/fig10_flip_rate.png) |

Additional stored figure (not in the numbered list above):

- Threshold vs precision/recall: [docs/figures/fig7_threshold_pr.png](figures/fig7_threshold_pr.png)

Copies of Figures 1–2 also live at `docs/figures/fig1_architecture.png` and `docs/figures/fig2_research_flow.png`.

A category-level score chart is omitted: every category in the locked run repeats the same 0/1 verifier split, already shown in Table 4 and `category_analysis.csv`.

Regenerate methodology and DEMO result figures (no LLM calls):

```bash
cd backend
.venv\Scripts\python.exe ..\docs\scripts\generate_research_figures.py
```
