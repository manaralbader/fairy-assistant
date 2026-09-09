"""Fairycore Assistant — a bilingual custom-jewelry commission assistant.

Capstone project, SDA-AIE-213 — LLM Application Engineering. By default every
model call in this package runs against an in-process, rule-based simulator
(see ``fairy.llm.sim``) rather than a real provider, so the notebook works with
no API key, no network, and no bill. See docs/adr/002-the-default-backend.md
for exactly what that trades away and what it keeps real.
"""

__version__ = "0.1.0"
