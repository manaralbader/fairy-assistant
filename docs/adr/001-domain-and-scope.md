# ADR 001 — Domain and scope: Fairycore, a custom-jewelry commission assistant

- **Status:** proposed — pending owner sign-off on the invented numbers below
- **Date:** 2026-09-09
- **Applies to:** the whole repository

## Context

This project is the capstone for SDA-AIE-213 — LLM Application Engineering,
Track D (retail order support). The rubric requires a domain with read-only order
lookups, at least one action that changes something, and a reason to refuse —
plus a grounding directory that answers must be composed from.

Fairycore is a fictional handmade-jewelry studio (beaded and wire-wrapped
accessories) based in Riyadh, KSA, modeled loosely on a real small business the
project owner used to run. All customer names, order IDs, and specific figures
below are invented for this course and are not real business records.

## Decision

### What Fairycore sells

Custom beaded and wire-wrapped jewelry — bracelets, necklaces, earrings, rings —
made to order rather than picked from stock. A customer describes a general
color palette and, optionally, an inspiration reference; the artisan designs the
piece. The assistant deliberately does **not** collect bead-by-bead or
stitch-by-stitch instructions — that boundary is a guardrail, not just a UX
choice, mirroring the real business's creative-freedom policy.

### Grounding directory (the facts an answer may use, nothing else)

| Fact | Value |
|---|---|
| Materials | silver-plated copper wire, gold-plated copper wire, raw copper wire; glass seed beads, gemstone chip beads (rose quartz, amethyst, turquoise), freshwater pearls, acrylic beads |
| Color palette offered | lavender, blush pink, seafoam green, cream, gold, silver, sky blue, lilac |
| Price — small (single bracelet / earring pair) | 60–90 SAR |
| Price — medium (necklace / layered set) | 120–180 SAR |
| Price — statement piece | 220–320 SAR |
| Turnaround | 7–10 business days from confirmed order to ready-for-pickup |
| Order status values | `pending_confirmation` → `in_progress` → `ready_for_pickup` → `picked_up` |
| Defect policy | full refund if the piece is defective (wire snaps, bead detaches under normal wear, clasp fails) within 14 days of pickup — always reviewed by a human, never auto-approved |
| Not covered | damage from misuse, loss, wear reported after 14 days |
| Pickup location | one studio, Riyadh |
| Pickup hours | Sun–Thu, 4pm–9pm |
| Over-specification limit | up to 2 preferred colors, one optional material preference, an inspiration note capped at 300 characters |

*(Owner: flag anything above you want changed before it's locked into 40+ golden-set cases — it's cheap to fix now, expensive once test cases assume it.)*

### The three risk classes of tools

| Tool | Risk class | What it does |
|---|---|---|
| `check_order_status` | read-only | Look up an existing order by order ID + last 4 digits of the phone on file. No mutation. |
| `create_custom_order` | side-effecting, authorization-gated | Opens a new commission (color/material preference, inspiration note, budget tier). Requires a verified session — phone-number verification (simulated OTP), not a claim made in the conversation text. |
| `book_pickup_appointment` | side-effecting, authorization-gated | Reserves a pickup slot. Requires a verified session **and** the order being `ready_for_pickup`. |
| `escalate_to_human` | terminal | Hands off to the owner for: defect refunds, a customer who insists on over-specifying after being redirected, or anything out of scope. Ends the automated turn — the assistant does not resolve these itself. |

### Router (Module 1 pattern)

- **FAQ path** (single call, no tools): materials, prices, turnaround, defect
  policy, hours — answered only from the grounding directory above.
- **Service workflow path** (tools, bounded loop): check status, start a
  commission, book a pickup.
- **Escalation path**: defect refunds and anything a customer insists on outside
  the assistant's authority.

### Language

Arabic-majority with English supported — the studio's real customer base was in
KSA, and this also satisfies the course's Arabic-majority golden-set and
bilingual-guardrail requirements.

### What Fairycore explicitly does not do (scope boundary)

No returns for buyer's remorse (all pieces are personalized/made to order — the
real business's actual policy). No shipping — pickup only. No exact-specification
custom orders — the assistant protects the artisan's creative freedom by design,
not just by convention.

## Consequences

**Good.** Every number the assistant states is traceable to this one table, so a
grounding test can assert "the answer must match the directory" rather than
"the answer sounds plausible." The over-specification boundary gives Module 3 and
Module 4 a domain-native reason to exist, instead of a generic example bolted on.

**Costs.** The domain is narrower than a general retailer — no multi-item cart,
no shipping logistics. That is deliberate: Track D's rubric is scored on depth of
evidence per discipline, not catalogue breadth.
