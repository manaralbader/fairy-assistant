# Fairycore Assistant

A bilingual (Arabic-majority, English-supported) customer assistant for
**Fairycore**, a fictional handmade-jewelry commission studio in Riyadh, KSA —
built as the capstone project for **SDA-AIE-213 — LLM Application Engineering**.

**Programme:** LLM Application Engineering, cohort 6–9 September 2026.

**Author:** Manar Albader

## What this is

Fairycore sells custom beaded and wire-wrapped jewelry made to order: a customer
describes a color palette and, optionally, an inspiration reference, and the
assistant either answers a factual question, runs a bounded action (checks an
order, opens a new commission, books a pickup slot), or hands off to a human —
never inventing a fact that isn't in [the grounding directory](docs/adr/001-domain-and-scope.md).

Track chosen: **D — Retail order support**. Domain design and the full rubric
mapping live in [`docs/adr/001-domain-and-scope.md`](docs/adr/001-domain-and-scope.md).
The decision log is [`DECISIONS.md`](DECISIONS.md).

## How to open and run it

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/manaralbader/fairy-assistant/blob/main/notebooks/capstone.ipynb)

The whole submission is **one Colab notebook** —
[`notebooks/capstone.ipynb`](notebooks/capstone.ipynb) — with no setup required:

1. Click the badge above (or open the notebook in Colab directly).
2. **Runtime → Run all.**
3. By default it runs against a built-in local simulator (no API key, no
   network) so a stranger can run the whole thing with nothing else installed.
   Optionally, add real keys per [`.env.example`](.env.example) to switch the
   same code onto a real backend (Google Gemini / Groq, both free-tier,
   neither requires a card) — no code change, see `fairy/llm/config.py`.

## Repository layout

```
notebooks/    the capstone notebook (the deliverable)
src/fairy/    the application code the notebook imports (client boundary,
              tools, prompts, guardrails, router, meter, cache)
data/         the grounding directory (catalogue, policies) and its seeds
eval/         golden set, judge, regression gate, run artefacts (gitignored)
docs/adr/     architecture decision records
tests/        architecture and unit tests, runnable locally and inline in the notebook
```

## Results

- **Evaluation:** 50-case golden set, 100% (commercial) / 98% (open-weight),
  safety stratum 100% on both — [`EVALUATION_REPORT.md`](EVALUATION_REPORT.md)
- **Benchmarks:** guard rate, tool pass rates, cost before/after —
  [`BENCHMARKS.md`](BENCHMARKS.md)
- **Decisions:** architecture, model/routing choice, one reversed trade-off —
  [`DECISIONS.md`](DECISIONS.md)

No extension attempted — mandatory scope only.
