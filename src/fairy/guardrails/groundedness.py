"""Stage 4: groundedness. A deterministic safety net independent of whatever
answered the question: scan the response for anything money-shaped, and if
that exact amount doesn't appear verbatim in the facts the assistant was
actually given, treat it as an invented figure. This is what stops a
plausible-sounding wrong price from ever reaching a customer, regardless of
which backend produced it.
"""

from __future__ import annotations

import re

MONEY_PATTERN = re.compile(r"\d+(?:-\d+)?\s*(?:SAR|sar|ريال)")


def check_groundedness(response_text: str, facts: dict[str, str]) -> list[str]:
    known_text = " ".join(facts.values())
    unsupported = []
    for match in MONEY_PATTERN.finditer(response_text or ""):
        amount = match.group(0)
        if amount not in known_text:
            unsupported.append(amount)
    return unsupported
