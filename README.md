# Fairycore Assistant

A bilingual (Arabic-majority, English-supported) customer assistant for
**Fairycore**, a fictional handmade-jewelry commission studio in Riyadh, KSA —
built as the capstone project for **SDA-AIE-213 — LLM Application Engineering**.

> TODO: programme name + cohort dates — e.g. "SDAIA Academy, SDA-AIE-213, cohort
> <dates>". Fill in before submission.

**Author:** TODO — full name (submissions without a name are not graded)

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

The whole submission is **one Colab notebook** —
[`notebooks/capstone.ipynb`](notebooks/capstone.ipynb) — with no setup required:

1. Open the notebook in Google Colab (badge/link goes here once the notebook exists).
2. **Runtime → Run all.**
3. By default it runs against a built-in local simulator (no API key, no
   network) so a stranger can run the whole thing with nothing else installed.
   Optionally, set `OPENAI_API_KEY` / another provider key as a Colab secret to
   switch the same code onto a real backend — see the setup cell.

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

## Status

Work in progress — this README will grow a results summary, benchmarks table,
and evaluation report links as each module's discipline is built and evidenced.
