# Evaluation Report

> **Every number below comes from a command in this repository, and every
> command works with no API key.** By default (see
> [ADR 002](docs/adr/002-the-default-backend.md)), both backends are two
> rule-based quality tiers of one in-process simulator — real token
> accounting, real prompt-cache hit detection, real fault injection, real
> grounding, and a real bounded tool loop; what's simulated is answer
> *quality*. Regenerate any number here with:
>
> ```bash
> python scripts/run_eval.py commercial
> python scripts/run_eval.py open_weight
> python scripts/run_guard_eval.py
> python scripts/calibrate_judge.py
> python scripts/demo_regression_gate.py
> ```

## Golden set

50 cases, [`eval/golden/golden_set.jsonl`](eval/golden/golden_set.jsonl):
Arabic-majority (31 ar / 19 en), safety oversampled (8/50 = 16% adversarial,
far above a realistic attack rate), every intent/language/difficulty/risk
value at ≥ 8 cases. Every expectation is deterministic (a route, a tool
name, a tool outcome, or a specific fact substring) — nothing here is graded
by the judge.

## Results, by backend tier

| Slice | commercial | open_weight |
|---|---|---|
| **overall** | **50/50 (100%)** | **49/50 (98%)** |
| intent: faq | 18/18 | 17/18 |
| intent: order_status | 8/8 | 8/8 |
| intent: appointment | 8/8 | 8/8 |
| intent: new_order | 8/8 | 8/8 |
| intent: escalation | 8/8 | 8/8 |
| language: ar | 31/31 | 30/31 |
| language: en | 19/19 | 19/19 |
| difficulty: easy | 26/26 | 25/26 |
| difficulty: medium | 13/13 | 13/13 |
| difficulty: hard | 11/11 | 11/11 |
| **risk: adversarial (safety)** | **8/8 (100%)** | **8/8 (100%)** |
| risk: benign | 42/42 | 41/42 |

**Safety stratum is 100% on both tiers.** The one open-weight miss
(`faq-06`, a fact the tier's higher `miss_rate` deterministically drops) is
a quality slip, never a safety one — the two are independent by design.

## Judge calibration

The default backend is a simulator, so an LLM-as-judge grading a rule-based
answer with a second rule-based process would be circular theatre if treated
as a real quality signal. The judge in
[`src/fairy/eval/judge.py`](src/fairy/eval/judge.py) is instead a
deterministic groundedness/shape check — calibrated against a real
human-labeled subset ([`eval/judge/human_labels.jsonl`](eval/judge/human_labels.jsonl),
57 cases, drawn from real router outputs plus deliberately-added ungrounded
and empty responses so both classes are actually represented) rather than
against a simplified copy of itself.

**Cohen's κ = 0.79** (confusion matrix: tp=47, tn=7, fp=3, fn=0).

The judge went through two real, documented failed attempts before this:
a pure word-overlap version scored **κ = -0.11** (worse than chance) because
an Arabic question answered from an English-only fact value, or a generic
"I've flagged this for a person" confirmation, shares no words with the
question at all despite being a good answer. A second version fixed that by
recognizing this system's own confirmation-template shapes, but a
hallucinated answer could still coincidentally share an ordinary word with
the question ("Do you offer engraving?" / "...we can likely arrange it" both
contain "offer") — exactly backwards, since word overlap should never excuse
an ungrounded guess. The current version checks whether the response
actually contains a real fact value instead, which fixed it.

The 3 remaining disagreements are genuine and named, not hidden: `os-01`,
`os-05`, and `ap-01` are cases a human flagged for tone (a raw
`"in_progress"`-style enum value reaching a customer, or a confirmation
missing a warmer opening phrase) that the judge's content/groundedness check
was never designed to catch. That gap is real and is listed below, not
smoothed over.

## Regression gate

[`eval/baseline.json`](eval/baseline.json) is the tracked baseline (a clean
commercial-tier run, all slices at 100%). `scripts/demo_regression_gate.py`
runs the harness twice — once clean, once against the seeded regression
(`strict_grounding=False`, standing in for
[`answer_faq/v2.md`](src/fairy/prompts/library/answer_faq/v2.md), a prompt
version whose changelog documents that it quietly drops the don't-know
instruction; see [ADR 002](docs/adr/002-the-default-backend.md) for why the
"prompt change" is expressed as a matching simulator flag rather than actual
prose the simulator would read):

- **clean run: 50/50 (100%), gate PASS.**
- **degraded run: 48/50 (96%), gate FAIL** — specifically on `intent=faq`
  (100% → 89%), not spread evenly across every slice. `risk=adversarial`
  stays untouched at 100% throughout, because this regression is about
  grounding discipline, not a guard bypass. Reading the *slice* is what
  catches this: the 4-point overall drop looks minor; the 11-point faq-slice
  drop is what a gate should actually block on.

## Known limitations

- **Grounded FAQ answers are English-only regardless of question language.**
  Arabic questions are correctly *matched* to the right fact (via bilingual
  keyword aliases in `fairy/llm/sim.py`) — routing and grounding work in
  Arabic — but the fact *value* returned is the same English text either
  way. Translating `fairy/domain/catalogue.py`'s fact values is real,
  scoped future work, not done here.
- **The judge is blind to tone/politeness**, by design — it checks content
  and groundedness, not phrasing. `os-01`, `os-05`, and `ap-01` above are the
  named, real cases this misses.
- **Order IDs restart at `FC-1000` for every fresh `OrderStore`.** Each test
  case gets an isolated in-memory store (`fairy.tools.store.demo_store()`),
  which is correct for testing but means the counter would need a persistent
  store to avoid collisions across a real, continuously-running session —
  out of scope for a notebook-scale demo.
- **The router's intent classifier is keyword-based**, not semantic. It
  cannot distinguish "what's your defect policy?" (FAQ) from "my piece is
  defective, refund me" (escalation) if both happen to use the word "عيب" /
  "defective" — the golden set's FAQ policy questions were deliberately
  phrased to avoid this collision rather than the classifier resolving it.
- **Quality numbers are simulated** (ADR 002). Every mechanic — routing,
  tool validation, the guard wall, the regression gate — is real code
  exercising real logic; only the model's *judgement* is stood in for by
  two deterministic rule-based tiers.
