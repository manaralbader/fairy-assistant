"""Route resolution: the one place that decides which concrete ``LLMClient``
a route name maps to. This is what makes the provider-swap claim literal —
every caller asks for a route by name (``"commercial"``, ``"open_weight"``),
never for a class, so changing ``.env`` is the entire migration.
"""

from __future__ import annotations

import os

from fairy.llm.interfaces import LLMClient
from fairy.llm.sim import SimClient

ROUTE_TO_TIER = {"commercial": "commercial", "open_weight": "open_weight"}


def get_client(route: str, *, env: dict | None = None) -> LLMClient:
    """``route`` is ``"commercial"`` or ``"open_weight"``. If the matching
    ``FAIRY_<ROUTE>_API_KEY`` is set in the environment, this returns a real
    ``OpenAICompatClient`` against it. Otherwise it returns the simulator's
    matching quality tier — same call, same return type, no branch anywhere
    else in the codebase has to know which one it got."""
    if route not in ROUTE_TO_TIER:
        raise ValueError(f"unknown route: {route!r} — choose one of {sorted(ROUTE_TO_TIER)}")

    environ = env if env is not None else os.environ
    prefix = f"FAIRY_{route.upper()}"
    api_key = environ.get(f"{prefix}_API_KEY")

    if not api_key:
        return SimClient(tier=ROUTE_TO_TIER[route])

    # imported lazily: the openai package (and the SDK import it performs)
    # is only needed when a real key is actually configured.
    from fairy.llm.openai_compat import OpenAICompatClient

    base_url = environ.get(f"{prefix}_BASE_URL")
    model = environ.get(f"{prefix}_MODEL")
    if not base_url or not model:
        raise RuntimeError(
            f"{prefix}_API_KEY is set but {prefix}_BASE_URL / {prefix}_MODEL are not — "
            "see .env.example"
        )
    return OpenAICompatClient(api_key=api_key, base_url=base_url, model=model, route=route)
