"""Reliability wrapper: retries a retryable failure on the primary route, then
falls back to a second, fully independent client if the primary keeps failing.

This is what the Module 1 fault drill exercises — a rate-limit storm and an
outage, scripted with :class:`~fairy.llm.fake.FakeClient`, replayed through this
wrapper, with the resulting ``.log`` captured as notebook output. Nothing about
this class is provider-specific; it only ever calls the ``LLMClient`` protocol,
so it works identically whether the primary is real, simulated, or scripted.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from fairy.llm.interfaces import LLMClient, LLMError, LLMRequest, LLMResponse, StreamChunk


class ResilientClient:
    def __init__(
        self,
        primary: LLMClient,
        fallback: LLMClient | None = None,
        *,
        max_retries: int = 2,
        backoff_base_s: float = 0.5,
        sleep_fn: Any = time.sleep,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self._sleep = sleep_fn
        self.log: list[dict] = []

    def _record(self, **event: Any) -> None:
        self.log.append(event)

    def complete(self, request: LLMRequest) -> LLMResponse:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.primary.complete(request)
                self._record(attempt=attempt, backend="primary", outcome="ok", route=response.route)
                return response
            except LLMError as err:
                self._record(
                    attempt=attempt,
                    backend="primary",
                    outcome="error",
                    status=err.status,
                    retryable=err.retryable,
                )
                if err.retryable and attempt <= self.max_retries:
                    delay = err.retry_after if err.retry_after is not None else self.backoff_base_s * attempt
                    self._sleep(delay)
                    continue
                break

        if self.fallback is None:
            raise LLMError("primary exhausted and no fallback configured", retryable=False)

        response = self.fallback.complete(request)
        self._record(attempt=attempt, backend="fallback", outcome="ok", route=response.route)
        return response

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        try:
            yield from self.primary.stream(request)
            self._record(backend="primary", outcome="ok", mode="stream")
            return
        except LLMError as err:
            self._record(backend="primary", outcome="error", mode="stream", status=err.status)
            if self.fallback is None:
                raise
        yield from self.fallback.stream(request)
        self._record(backend="fallback", outcome="ok", mode="stream")
