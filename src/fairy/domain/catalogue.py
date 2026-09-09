"""The grounding directory — every fact the assistant is allowed to state, and
every constraint a customer-supplied value is validated against. One source of
truth: docs/adr/001-domain-and-scope.md documents the reasoning, this module is
the machine-readable copy of the same table.

``to_fact_lines()`` renders these as ``FACT: key = value`` lines, the exact
format ``fairy.llm.sim.SimClient`` scans a system prompt for — so grounding a
conversation is "include this text," not a separate retrieval system.
"""

from __future__ import annotations

MATERIALS = [
    "silver-plated copper wire",
    "gold-plated copper wire",
    "raw copper wire",
    "glass seed beads",
    "gemstone chip beads (rose quartz, amethyst, turquoise)",
    "freshwater pearls",
    "acrylic beads",
]

COLOR_PALETTE = [
    "lavender",
    "blush pink",
    "seafoam green",
    "cream",
    "gold",
    "silver",
    "sky blue",
    "lilac",
]

BUDGET_TIERS = {
    "small": "60-90 SAR (single bracelet or a pair of earrings)",
    "medium": "120-180 SAR (a necklace or a layered bracelet set)",
    "statement": "220-320 SAR (a multi-strand necklace or a large custom set)",
}

TURNAROUND_DAYS = "7-10 business days from confirmed order to ready-for-pickup"

DEFECT_POLICY = (
    "full refund if the piece is defective (wire snaps, a bead detaches under "
    "normal wear, a clasp fails) within 14 days of pickup — always reviewed by "
    "a person, never auto-approved"
)
DEFECT_WINDOW_DAYS = 14

PICKUP_LOCATION = "one studio, Riyadh"
PICKUP_HOURS = "Sunday-Thursday, 4pm-9pm"

MAX_COLOR_PREFERENCES = 2
MAX_INSPIRATION_NOTE_CHARS = 300

ORDER_STATUSES = ["pending_confirmation", "in_progress", "ready_for_pickup", "picked_up"]


def to_fact_lines() -> str:
    lines = [
        f"FACT: materials offered = {', '.join(MATERIALS)}",
        f"FACT: color palette = {', '.join(COLOR_PALETTE)}",
        *[f"FACT: price for a {tier} piece = {desc}" for tier, desc in BUDGET_TIERS.items()],
        f"FACT: turnaround time = {TURNAROUND_DAYS}",
        f"FACT: defect and refund policy = {DEFECT_POLICY}",
        f"FACT: pickup location = {PICKUP_LOCATION}",
        f"FACT: pickup hours = {PICKUP_HOURS}",
    ]
    return "\n".join(lines)
