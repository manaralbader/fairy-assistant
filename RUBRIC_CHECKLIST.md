# Rubric checklist

Working copy of the capstone rubric, turned into checkboxes, so progress is
visible at a glance instead of buried in commit messages. Updated as each phase
lands — a box only gets checked once the evidence for it exists in this repo
(a cell, a test, a file), never on intention.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done, with evidence

---

## 1 · Architecture and the model boundary — 15 pts

- [ ] Router-first design: FAQ single-call, service workflow with tools, escalation to a human
- [ ] Every model call goes through one `LLMClient` boundary
- [ ] `assert` cell in the notebook proving no provider SDK import exists outside one adapter section
- [ ] Two live backends (one commercial, one open-weight), switchable by config only
- [ ] A scripted fault (rate-limit + outage) with the fallback transcript captured as notebook output
- [ ] One ADR recording the pattern and model choices

## 2 · Structured outputs and function calling — 15 pts

- [ ] One validated request object (commission / status query / appointment), extracted via validate → retry → repair
- [ ] Pass rates measured and split by language (ar / en)
- [ ] At least 3 tools spanning risk classes: read-only, side-effecting + auth-gated, terminal
- [ ] Authorization lives in `session.authorize()`, never in the prompt text
- [ ] A bounded tool loop
- [ ] Negative tool-safety cases as green `assert` cells
- [ ] Every tool call logged with risk class + loop iteration

## 3 · Prompt pipeline and guardrails — 15 pts

- [ ] Every prompt is a versioned file with a changelog, zero inline prompt text in Python
- [ ] Five-stage guardrail pipeline, each stage demonstrated alone
- [ ] Attack corpus ≥ 30 cases, bilingual
- [ ] ≥ 95% blocked, **reported next to** 0% false positives on a same-size legitimate corpus (both numbers, always paired)
- [ ] Patterns matched against normalized text (handles zero-width separators, Arabic normalization)
- [ ] Canary intact; refusals bilingual and never echo the payload

## 4 · Evaluation harness — 20 pts

- [ ] Golden set ≥ 40 cases, stratified by intent/language/difficulty/risk, Arabic-majority, safety oversampled, every stratum ≥ 8 cases
- [ ] Harness runs the real pipeline functions, not a simplified copy
- [ ] Deterministic asserts carry every safety claim
- [ ] Judge calibrated to Cohen's κ ≥ 0.6, evidence included
- [ ] Safety stratum at 100%
- [ ] Regression-gate function demonstrated: run clean once, run against a seeded degraded prompt once, both captured
- [ ] Evaluation Report generated from real runs, including known limitations

## 5 · Cost and latency engineering — 15 pts

- [ ] Meter covers 100% of model calls (guards + router included)
- [ ] Prompt-cache hit rate proven via `usage.cached_input_tokens`, ≥ 65% of input tokens cached
- [ ] Response cache with a key covering everything that changes an answer
- [ ] Semantic cache tier thresholded on measured data, zero wrong hits on a near-miss suite
- [ ] Before/after cost table, ≥ 60% reduction, **eval verdict next to every step**

## 6 · Model comparison and recommendation — 10 pts

- [ ] Both backends run over our own golden set, reported by slice (not one number)
- [ ] Cost and latency reported alongside quality
- [ ] Self-host break-even computed from throughput we measured ourselves
- [ ] Routing recommendation follows from the evidence, recorded in DECISIONS.md

## 7 · The application, complete — 10 pts

- [ ] Fresh Colab run (Runtime → Run all) reaches a working bilingual conversation, zero setup
- [ ] Grounded answer, tool-completed action, refused attack, and graceful fault fallback all shown as real cells

---

## Deliverables

- [ ] Repository URL with full incremental history (this repo)
- [ ] `EVALUATION_REPORT.md` (or notebook section) — overall + sliced results, judge calibration, safety status, known limitations
- [ ] `BENCHMARKS.md` (or notebook section) — provider comparison, tool pass rates, guard rates (paired), before/after cost
- [ ] `DECISIONS.md` + ADRs — pattern/model/routing choice, break-even, **one reversed trade-off and why**

## The four capping flags (never let these happen)

- [ ] Golden cases edited to make a failure pass
- [ ] Guard numbers reported without the false-positive pair
- [ ] A cost saving with no eval verdict beside it
- [ ] A judge gating anything with no calibration evidence

## Before submit

- [ ] Full name in the README
- [ ] All test cells green, safety stratum 100%
- [ ] No provider SDK import outside the adapter section, no unbounded `max_tokens`, no inline prompt text
- [ ] Both backends actually run, switched by config, shown
- [ ] Fault-drill transcript captured as real output
- [ ] Guard numbers reported in pairs
- [ ] Judge calibration evidence with κ stated
- [ ] Regression gate demonstrated blocking the seeded change, slice table shown
- [ ] Every cost row carries its eval verdict
- [ ] Break-even quotes both comparisons
- [ ] Known-limitations section, honest
- [ ] Colab runtime restarted and run fresh top to bottom before submitting
- [ ] No API key in the notebook or in git history
- [ ] No `TODO` / placeholder text left anywhere
- [ ] Track and chosen extension stated explicitly
- [ ] README covers project description + how to run, `.gitignore` excludes secrets, programme name + cohort dates stated

---

## Status as of this commit

Scaffold only: repo structure, domain design ADR, README, decision log. None of
the 7 graded sections have code yet — this commit satisfies a slice of the
**GitHub & documentation requirements** (repo structure, initial README,
`.gitignore`, decision-log skeleton) and nothing else. Everything above is
unchecked on purpose.
