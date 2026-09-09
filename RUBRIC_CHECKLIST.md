# Rubric checklist

Working copy of the capstone rubric, turned into checkboxes, so progress is
visible at a glance instead of buried in commit messages. Updated as each phase
lands — a box only gets checked once the evidence for it exists in this repo
(a cell, a test, a file), never on intention.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done, with evidence

---

## 1 · Architecture and the model boundary — 15 pts

- [ ] Router-first design: FAQ single-call, service workflow with tools, escalation to a human
- [~] Every model call goes through one `LLMClient` boundary — the contract (`interfaces.py`) and two implementations (`sim.py`, `openai_compat.py`) exist; nothing calls it yet because the router doesn't exist
- [~] `assert` cell in the notebook proving no provider SDK import exists outside one adapter section — proven locally as `tests/test_architecture.py::test_no_provider_sdk_outside_the_adapter`; porting it into a notebook cell is pending until the notebook exists
- [~] Two live backends (one commercial, one open-weight), switchable by config only — **by design decision (ADR 002), the default and graded run uses a rule-based simulator with two distinct tiers, not real network calls** (no cost, no key, reproducible). The real adapter (`openai_compat.py`) is fully implemented and unit-tested against a mocked HTTP layer, and `config.py` proves route selection is env-var-only (`tests/test_config.py`) — so the *architecture* claim is proven; it is not claiming two real providers were exercised live
- [~] A scripted fault (rate-limit + outage) with the fallback transcript captured as notebook output — the retry/fallback mechanism (`resilient.py`) is built and unit-tested (3 passing cases: retry-then-recover, retry-then-fallback, no-fallback-raises); capturing the transcript as notebook output is pending
- [x] One ADR recording the pattern and model choices — [ADR 001](docs/adr/001-domain-and-scope.md) (domain/scope) and [ADR 002](docs/adr/002-the-default-backend.md) (why the default backend is a simulator, what stays real, what's simulated); concrete model choices recorded in `.env.example`

## 2 · Structured outputs and function calling — 15 pts

- [x] One validated request object (commission / status query / appointment), extracted via validate → retry → repair — `CreateCustomOrderArgs` (`tools/schemas.py`), the repair path is the bounded loop feeding a validation error back as a tool result (`tools/loop.py`)
- [x] Pass rates measured and split by language (ar / en) — `scripts/measure_tool_extraction.py`, real, rerunnable: commercial tier 89%/89% (en/ar), open-weight 56%→89% / 78%→89% (first attempt → after repair); the one case per language that never passes is the deliberate over-300-char over-specification test, proving that guard is a hard limit, not a hint
- [x] At least 3 tools spanning risk classes: read-only, side-effecting + auth-gated, terminal — 4 tools in `tools/registry.py`: `check_order_status` (read-only), `create_custom_order` + `book_pickup_appointment` (side-effecting, auth-gated), `escalate_to_human` (terminal)
- [x] Authorization lives in `session.authorize()`, never in the prompt text — `tools/session.py`; `tests/test_tools.py::test_side_effecting_tool_blocked_without_an_authorized_session_even_with_valid_arguments` proves *valid* arguments still get rejected without a verified session
- [x] A bounded tool loop — `tools/loop.py::run_tool_loop`; `test_bounded_loop_stops_a_model_that_never_gives_up` proves it stops a model that keeps calling the same tool forever
- [~] Negative tool-safety cases as green `assert` cells — 7 negative/edge cases pass locally in `tests/test_tools.py`; porting them into notebook `assert` cells is pending until the notebook exists
- [x] Every tool call logged with risk class + loop iteration — every `run_tool_loop` call returns `.log`, asserted directly in tests

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
