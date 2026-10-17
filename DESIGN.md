# VeriFact — Design System & Visual Specification

**Document Version**: 1.0.0 (Release Freeze)
**Implementation Source**: `frontend/src/index.css` · Tailwind CSS v4 · `frontend/src/theme/`

---

## 1. Visual Philosophy & Design Principles

VeriFact is an analytical research tool and interactive evaluation studio. Its user interface is designed to evoke **quiet confidence, scientific clarity, and visual comfort**.

### Core Tenets
1. **Calm & Desaturated Surfaces**: Avoid overly saturated, harsh, or neon colors. The interface uses muted, earthy neutrals with tailored tonal contrast that avoids eye fatigue during extended research sessions.
2. **Strict Semantic Integrity**: Color carries meaning. Green indicates reliability and supported evidence; red/rose indicates hallucination or contradiction; amber indicates uncertainty or warnings; neutral stone indicates unassessed or informational context.
3. **Restraint over Decoration**: No unnecessary gradients, glassmorphism, glowing borders, or decorative clutter. Every visual element (card, badge, border, gauge) serves an informational purpose.
4. **Accessible Mathematical Presentation**: Equations and fractions are formatted using clean HTML/CSS stacked components, accompanied by plain-English explanations so non-mathematicians can interpret results immediately.
5. **Seamless Theme Equivalence**: Dark mode is not an afterthought; both Light and Dark themes are calibrated for equal legibility, contrast, and hierarchy.

---

## 2. Theme Architecture & Tokens

The design system is implemented via CSS custom properties mapped to Tailwind CSS v4 `@theme` tokens in `frontend/src/index.css`.

### 2.1 Color Tokens Specification

| Token | Light Mode Value | Dark Mode Value | Semantic Role |
|---|---|---|---|
| `--color-canvas` | `#f7f5f1` | `#121110` | App background, page canvas |
| `--color-surface` | `#ffffff` | `#1a1816` | Panel containers, cards, elevated elements |
| `--color-surface-muted` | `#f1eee8` | `#24211e` | Table headers, secondary card wells, pill backgrounds |
| `--color-ink` | `#1c1917` | `#f2efe8` | Primary text headings, body text, strong emphasis |
| `--color-ink-secondary` | `#57534e` | `#b0a89e` | Secondary body text, descriptions, labels |
| `--color-ink-muted` | `#8a847a` | `#857e74` | Timestamps, metadata, disabled captions |
| `--color-line` | `#e7e3db` | `#2c2925` | Standard structural borders, dividers |
| `--color-line-strong` | `#d6d1c8` | `#3a3530` | Focused borders, active tabs, card outlines |
| `--color-accent` | `#2f6f5e` | `#6ba894` | Primary brand accent, interactive elements |
| `--color-accent-hover` | `#255a4c` | `#7fbaa6` | Hover states on accent elements |
| `--color-accent-soft` | `#e8f2ee` | `#1d2f29` | Light tint for active tabs and accent highlights |
| `--color-reliable` | `#2d6a4f` | `#6bb592` | Success, supported claims, low hallucination |
| `--color-reliable-soft` | `#e8f3ec` | `#1a2c24` | Background tint for reliable badges and cards |
| `--color-uncertain` | `#a16207` | `#d4a84b` | Insufficient evidence, conflicting verdicts |
| `--color-uncertain-soft` | `#f8f0dc` | `#2f2714` | Background tint for warning/uncertain badges |
| `--color-hallucinated` | `#9a4036` | `#d08a80` | Contradicted claims, hallucinated verdicts |
| `--color-hallucinated-soft` | `#f6e8e6` | `#2f1e1c` | Background tint for error/hallucination badges |

### 2.2 Elevation & Geometry

| Token | Value | Purpose |
|---|---|---|
| `--radius-sm` | `8px` | Badges, buttons, nested cards, code blocks |
| `--radius-md` | `12px` | Primary panels, top-level containers |
| `--shadow-card` | `0 1px 2px rgba(28, 25, 23, 0.05)` (light) / `rgba(0, 0, 0, 0.35)` (dark) | Subtle card elevation |
| `--shadow-float` | `0 10px 24px rgba(28, 25, 23, 0.1)` (light) / `rgba(0, 0, 0, 0.45)` (dark) | Floating tooltips, dropdowns |

### 2.3 Typography

- **Font Family**: `"Inter", ui-sans-serif, system-ui, -apple-system, sans-serif`
- **Monospace**: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace` (for model IDs, code tokens, UUIDs, and mathematical symbols)
- **Hierarchy**:
  - Page Title: `text-[1.7rem] font-semibold tracking-tight`
  - Section Header: `text-sm font-semibold tracking-tight`
  - Body: `text-xs leading-relaxed`
  - Microcopy / Captions: `text-[10px]` or `text-[11px]`

---

## 3. Semantic Color Applications

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SEMANTIC PALETTE ROLES                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   [RELIABLE / SUPPORTED]                                               │
│   ● Text: #2d6a4f (light) / #6bb592 (dark)                             │
│   ● Soft BG: #e8f3ec (light) / #1a2c24 (dark)                          │
│   Applied to: Supported claims (1.0), MetaQA Reliable, Agreement       │
│                                                                        │
│   [UNCERTAIN / INSUFFICIENT EVIDENCE]                                  │
│   ● Text: #a16207 (light) / #d4a84b (dark)                             │
│   ● Soft BG: #f8f0dc (light) / #2f2714 (dark)                          │
│   Applied to: Insufficient evidence (0.5), Disagreements, Not Sure     │
│                                                                        │
│   [HALLUCINATED / CONTRADICTED]                                        │
│   ● Text: #9a4036 (light) / #d08a80 (dark)                             │
│   ● Soft BG: #f6e8e6 (light) / #2f1e1c (dark)                          │
│   Applied to: Contradicted claims (0.0), MetaQA Hallucinated (Score≥0.5)│
│                                                                        │
│   [NEUTRAL / UNASSESSED]                                               │
│   ● Text: #57534e (light) / #b0a89e (dark)                             │
│   ● Soft BG: #f1eee8 (light) / #24211e (dark)                          │
│   Applied to: Not Assessed (no source found), Information, Metadata    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Source-Quality Tier Card Styling

In Web Evidence, source tiers are differentiated by subtle tonal palettes that avoid neon highlights:

| Tier | Tier Name | Light Mode Styling | Dark Mode Styling | Visual Character |
|---|---|---|---|---|
| **Tier 1** | **Primary & Official** | `#2d6350` / `bg-emerald-500/10` | `#7fbaa6` / `bg-emerald-500/15` | Muted Forest Sage |
| **Tier 2** | **Academic & Research** | `#325b7a` / `bg-sky-500/10` | `#8cb8d8` / `bg-sky-500/15` | Slate Steel Blue |
| **Tier 3** | **Reputable News & Fact-Check** | `#5a4e75` / `bg-indigo-500/10` | `#afa5cf` / `bg-indigo-500/15` | Dusky Lavender / Plum |
| **Tier 4** | **Reference & Encyclopedias** | `#6e5833` / `bg-amber-500/10` | `#cfbd9a` / `bg-amber-500/15` | Warm Parchment / Sand |
| **Tier 5** | **General Web** | `#5c5750` / `bg-stone-500/10` | `#a69f93` / `bg-stone-500/15` | Warm Stone |
| **Tier 6** | **Low Priority** | `#7d776e` / `bg-stone-400/10` | `#888176` / `bg-stone-400/15` | Soft Granite Ash |

All tier cards use subtle containers with `border border-line/70 bg-surface/80 p-3.5 space-y-2` and rounded corners (`var(--radius-sm)`).

---

## 5. Component Patterns & Guidelines

### 5.1 Status Badges & Pills
```tsx
// Example: Reliable / Configured Badge
<span className="inline-flex items-center gap-1 rounded-full bg-reliable-soft px-2.5 py-0.5 text-[11px] font-semibold text-reliable">
  <CheckCircle2 className="h-3 w-3" />
  Configured
</span>

// Example: Hallucinated / Contradicted Badge
<span className="inline-flex items-center gap-1 rounded-full bg-hallucinated-soft px-2.5 py-0.5 text-[11px] font-semibold text-hallucinated">
  Contradicted
</span>

// Example: Not Assessed Badge
<span className="inline-flex items-center rounded-full bg-surface-muted px-2.5 py-0.5 text-[11px] font-medium text-ink-secondary border border-line/60">
  Not assessed (excluded)
</span>
```

### 5.2 Educational Accordions (`MethodOverview.tsx`)
- Accordion cards use `border border-line/70 bg-surface hover:border-line-strong transition-colors`.
- Headers include clean typography with an expandable chevron that rotates $180^\circ$ upon expansion.
- Content is organized in numbered steps with soft bullet points.

### 5.3 Mathematical Formula Rendering
- **No LaTeX Entities**: Do not write raw LaTeX commands like `&frac12;` or `&Biggl;`.
- **Accessible Stacked Fractions**: Implement stacked HTML fractions using flexbox columns:
  ```tsx
  <span className="inline-flex flex-col items-center leading-none px-1">
    <span className="border-b border-ink/40 pb-0.5">1</span>
    <span className="pt-0.5">2</span>
  </span>
  ```
- **Plain-English Annotations**: Always pair formulas with readable breakdown cards and explanatory lists.

---

## 6. Page-Specific Design Conventions

| Page | Primary Focus | Key Visual Elements |
|---|---|---|
| **Detect (`/`)** | Studio for question submission and comprehensive analysis | Three green informational side-dots, clean multiline question input, interactive progress stepper, answer card with model latency, score cards, independent verdict badges, collapsible mutation rows, web claims breakdown. |
| **MetaQA (`/metaqa`)** | Educational theory and metamorphic methodology | Interactive 4-step horizontal workflow diagram, accessible Eq. 5 stacked fraction formula, 3 explanatory bullet points, clear threshold cutoff indicator ($\theta = 0.50$). |
| **Web Analysis (`/web-analysis`)** | External grounding methodology | Prominent Consistency Score banner, 4-card contribution grid, 6-tier domain authority hierarchy, multi-branch pipeline convergence diagram, research considerations box. |
| **History (`/history`)** | Auditing persisted evaluations | Responsive table/list view, clear score pills, date timestamps, detail drawer for inspecting full analysis records. |
| **Settings (`/settings`)** | System configuration and appearance | Theme selector (Light / Dark / System), clean section headers **without decorative icons**, model configuration status badges, SQLite database connectivity indicator, paper citation links. |

---

## 7. Responsive Behavior & Accessibility

- **Mobile Viewports ($< 640\text{px}$)**: Grids collapse from 2–3 columns to single-column vertical stacks. Formulas wrap gracefully without horizontal scrollbars.
- **Keyboard Navigation**: All buttons, radio toggles, inputs, and accordion triggers include visible focus rings (`focus-visible:ring-2 focus-visible:ring-accent`).
- **Contrast Ratios**: Body text meets a minimum contrast ratio of **4.5:1** against backgrounds, and large text meets **3:1** under both light and dark themes.
