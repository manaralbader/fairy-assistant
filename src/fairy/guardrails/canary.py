"""One fixed token, planted in every rendered system prompt (see
``fairy.prompts.registry``) with an instruction never to repeat it. If a
response ever contains it, the system prompt itself has leaked — that's a
different failure than a hallucinated fact or a blocked attack, and it gets
its own stage so it's never confused with either.
"""

from __future__ import annotations

CANARY = "FAIRY-CANARY-7f3a9c"


def check_canary_leak(response_text: str) -> bool:
    return CANARY in (response_text or "")
