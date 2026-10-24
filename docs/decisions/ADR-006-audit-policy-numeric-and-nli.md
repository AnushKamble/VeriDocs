# ADR-006: Audit Policy, Deterministic Numeric Validation, and NLI Classification

## Context
A major failure mode in GenAI systems for finance is relying solely on text entailment (NLI) to verify quantitative data. General-domain NLI models (like DeBERTa) frequently miss:
- Off-by-one or off-by-a-thousand scale differences ($1,200 vs $1,200,000).
- Accounting parenthetical negative signs ($ (45) million vs $ 45 million).
- Fiscal year vs calendar year mismatches (FY2022 vs FY2023).
- Percentage point differences vs percentage changes (+5% vs +5 percentage points).

Conversely, deterministic code can accurately verify arithmetic, units, and signs, but cannot verify narrative descriptions (e.g., "The decline was driven by macroeconomic headwinds in Europe").

## Decision
We implement a two-tier audit hierarchy:

### Tier 1: Deterministic Numeric Audit (First & Authoritative for Numbers)
Before any NLI model is invoked on a numeric claim:
1. Extract candidate numbers, units, periods, and metrics from the claim.
2. Resolve cited source chunk IDs to stored table cells and narrative excerpts.
3. Compare normalized values, signs, and units using Python `decimal.Decimal`.
4. If an allowable deterministic calculation is specified (difference, percent change, ratio, percentage-point change), execute it using safe arithmetic with zero-denominator checks.
5. **Precedence**: If a numeric mismatch, sign error, or scale error is discovered, the claim status is definitively marked `NUMERIC_MISMATCH`. It CANNOT be overridden by an NLI entailment score.
6. **Fail-Closed on Ambiguity**: If unit scaling or reporting periods cannot be unambiguously matched, the audit status is set to `INCONCLUSIVE` / `NEEDS_REVIEW`.

### Tier 2: Natural Language Inference (NLI) Cross-Encoder
For narrative claims and validated numeric statements:
1. Model: `cross-encoder/nli-deberta-v3-small`.
2. Premise: Verbatim cited chunk text. Hypothesis: Atomic claim text.
3. Output labels: `[contradiction, entailment, neutral]`. Output logits are converted via softmax to probability scores.
4. **Calibration Protocol**: Thresholds for support ($\tau_{\text{support}}$) and contradiction ($\tau_{\text{contradict}}$) are selected exclusively on a labeled development calibration set (`benchmarks/claim_audit_calibration.jsonl`) and frozen before testing.
5. **No Probability Claim**: Softmax scores are reported as model signals, never as objective probabilities that the financial statement is true in reality.

### Response Policy and Abstention
- `SUPPORTED`: Valid citations + numeric check passed + NLI entailment $\ge \tau_{\text{support}}$.
- `CONTRADICTED`: NLI contradiction $\ge \tau_{\text{contradict}}$.
- `NUMERIC_MISMATCH`: Figure, period, sign, or unit conflicts with cited table cell.
- `INVALID_CITATION`: Citation ID missing or not retrieved.
- `INSUFFICIENT_EVIDENCE`: Below support threshold or neutral.
- `CONFLICTING_EVIDENCE`: Sources retrieved disagree.
- `AUDITOR_UNAVAILABLE`: NLI model or dependency could not run.
- **Abstention Policy**: When the retrieved evidence provides insufficient basis for answering, the system explicitly abstains rather than inventing answers.
