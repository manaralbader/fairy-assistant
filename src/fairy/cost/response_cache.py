"""A response cache with two tiers: exact match on the normalized question,
then a semantic tier for near-duplicate phrasing, thresholded on measured
Jaccard word-overlap (see scripts/measure_cache.py for the near-miss suite
that threshold was picked against — not a guessed constant).

Only ever used for the FAQ path (see fairy.router) — a side-effecting tool
call is never cached, because replaying a cached "order created" result for
a different customer would be a correctness bug, not an optimization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from fairy.guardrails.normalize import normalize


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", normalize(text)))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass
class _Entry:
    tokens: set[str]
    response_text: str


class ResponseCache:
    def __init__(self, semantic_threshold: float = 0.6) -> None:
        self.semantic_threshold = semantic_threshold
        self._store: dict[tuple[str, str], _Entry] = {}
        self.exact_hits = 0
        self.semantic_hits = 0
        self.misses = 0

    def get(self, user_text: str, language: str) -> str | None:
        key = (normalize(user_text), language)
        entry = self._store.get(key)
        if entry is not None:
            self.exact_hits += 1
            return entry.response_text

        query_tokens = _tokens(user_text)
        best_score, best_response = 0.0, None
        for (_, lang), candidate in self._store.items():
            if lang != language:
                continue
            score = _jaccard(query_tokens, candidate.tokens)
            if score > best_score:
                best_score, best_response = score, candidate.response_text
        if best_response is not None and best_score >= self.semantic_threshold:
            self.semantic_hits += 1
            return best_response

        self.misses += 1
        return None

    def set(self, user_text: str, language: str, response_text: str) -> None:
        key = (normalize(user_text), language)
        self._store[key] = _Entry(tokens=_tokens(user_text), response_text=response_text)
