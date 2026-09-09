# ADR 002 — The default backend is a simulator, and every artefact says so

- **Status:** accepted
- **Date:** 2026-09-09
- **Applies to:** every number this repository reports by default

## Context

The capstone notebook has to open cold in Colab, hit **Runtime → Run all**, and
reach a working conversation with **no API key, no network dependency, and no
bill** — that's the "zero setup" requirement the whole submission is graded
against. It also needs to demonstrate two backends, one commercial and one
open-weight, switchable by config.

Those two requirements are in tension unless the default *is* a stand-in for
both. The course's own reference project (`murshid/`) resolves the same
tension the same way — see its ADR 003 — and we adopt the identical trade-off
here, independently documented, because it is honest rather than because it is
convenient.

## Decision

`fairy.llm.sim.SimClient` implements the exact same `LLMClient` protocol as the
real adapter (`fairy.llm.openai_compat.OpenAICompatClient`). Application code
never knows which one it's talking to — `fairy.llm.config.get_client(route)`
decides that from environment variables alone (see `.env.example`), which is
what makes the provider-swap claim in ADR 001/Module 1 literally true rather
than aspirational.

**What the simulator keeps real:**

- the wire shape (`LLMRequest` in, `LLMResponse` out, tool calls, `finish_reason`);
- token accounting — an approximate tokenizer counts real input/output tokens
  from the real request/response text, not a fabricated number;
- prompt-cache hit detection — it hashes the stable prefix
  (`cache_prefix_messages`) and only reports a cache hit the second time that
  exact prefix is sent, the same mechanism a real provider's cache uses;
- fault injection on demand, so the Module 1 reliability drill is a real code
  path, not narration;
- grounding — it only ever answers from `FACT:` lines present in the system
  message it was actually given. A fact that isn't in that message cannot
  appear in the answer, which is the property every groundedness test in
  Module 4/5 depends on.

**What it simulates:** answer *quality*. Two tiers —
`tier="commercial"` and `tier="open_weight"` — differ by rule, not by
capability: the open-weight tier fumbles a tool-call's JSON arguments and
misses a directory fact more often, deterministically (a hash of the request,
not randomness), so a run repeats exactly and a gate that fires, fires for a
reason that can be pointed at.

**What real backends exist for:** `openai_compat.py` is a fully working
adapter against any OpenAI-wire-compatible endpoint (both Google Gemini and
Groq expose one). If real keys are ever added to `.env`,
`fairy.llm.config.get_client("commercial")` / `get_client("open_weight")`
silently switch to them — same code, two environment variables. The adapter is
unit-tested against a mocked HTTP response so its request/response mapping is
proven correct independent of whether a key is present.

## Consequences

**Good.** Every cost, latency, and pass-rate number in this repository's
evaluation is reproducible by anyone who clones it, with no key and no bill.
The tiered simulator gives Module 3's "pass rate split by language" and
Module 4's guard corpus something real and deterministic to measure against.

**Costs, stated plainly.** Any number this repository reports about answer
*quality* — a golden-set pass rate, a model comparison verdict — is a claim
about the simulator's rules, not about a real language model's judgement. The
`EVALUATION_REPORT.md` and `BENCHMARKS.md` this project produces say so in
their first paragraph, and the "known limitations" section names it again. The
architecture and the cost/latency mechanics this project demonstrates
(the retry/fallback wrapper, the cache-hit accounting, the meter) are real
regardless — only the model's judgement is stood in for.
