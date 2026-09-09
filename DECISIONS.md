# Decisions

The architecture decision records live in [`docs/adr/`](docs/adr/). This page is
the index, plus the one section a review board always asks for: what did we
change our mind about?

| ADR | Decision | Status |
|---|---|---|
| [001](docs/adr/001-domain-and-scope.md) | Domain and scope: Fairycore, a custom-jewelry commission assistant | proposed |
| [002](docs/adr/002-the-default-backend.md) | The default backend is a simulator, and every artefact says so | accepted |

## Routing recommendation (Module 6)

Route FAQ and read-only traffic to the open-weight tier by default; escalate
to commercial only where the guard's groundedness check fires (see
`fairy.guardrails.pipeline.check_output`). Evidence: both tiers score 100%
on the golden set's safety stratum and 100%/94%+ on quality slices
(BENCHMARKS.md), the open-weight tier is ~5x cheaper per conversation and
~2x lower latency at measured throughput, and self-hosting clears its
break-even well below the throughput actually measured for this tier. If
real traffic ever pushed the open-weight tier's benign pass rate below the
committed baseline, the regression gate (`scripts/demo_regression_gate.py`)
is what would catch it — not a manual spot-check.

## Trade-offs we reversed

### `create_custom_order` asking for a phone number, reversed

**First decision.** `CreateCustomOrderArgs` included a `contact_phone` field —
seemed reasonable, an order needs a phone number attached to it.

**What happened.** Running the real pass-rate measurement
(`scripts/measure_tool_extraction.py`) against realistic commission requests,
every single case failed — 0% pass, in both languages, before any tier-based
degradation was even involved. The cause: the simulated extractor had no
reliable way to know the customer's *own* phone number from free text, so it
fell back to a placeholder that never matched the authorized session's phone,
and the handler correctly rejected the mismatch.

**What we did not do.** Patch the simulator to fabricate a plausible-looking
phone number so the numbers would look better. That would have hidden a real
design problem behind a better-looking metric — exactly the anti-pattern this
project is trying not to be.

**Second decision.** Removed `contact_phone` from the schema entirely. The
session is already authenticated by the time this tool can run
(`session.require_authorized()`); asking the model to also *supply* a phone
number was a redundant identity claim living in the token stream — precisely
the anti-pattern Module 3 warns about, just in a field the model fills in
rather than a prompt injection. The order's phone now comes directly from
`session.phone`, never from model-controlled arguments.

**Result.** Pass rates became meaningful and measurable: 89% first-attempt on
the commercial tier (both languages), dropping to 56%/78% on the open-weight
tier and recovering to 89% after one repair turn — see
`scripts/measure_tool_extraction.py`. The one case per language that never
passes, even after repair, is the deliberately over-length inspiration note —
proof the 300-character over-specification guard is a hard schema limit, not
a hint the model can talk its way around.
