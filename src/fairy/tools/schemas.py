"""The validated request object for every tool. A model's tool-call arguments
are just a JSON string until one of these parses and validates them — that
validation is the wall between "the model suggested this" and "this actually
happens." Nothing here talks to the model or to storage; it only defines shape
and constraints.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from fairy.domain.catalogue import (
    BUDGET_TIERS,
    COLOR_PALETTE,
    MAX_COLOR_PREFERENCES,
    MAX_INSPIRATION_NOTE_CHARS,
)

PHONE_LAST4 = re.compile(r"^\d{4}$")
ORDER_ID = re.compile(r"^FC-\d{4,}$")


class CheckOrderStatusArgs(BaseModel):
    """Read-only. No authenticated session required — just enough to prove the
    asker has legitimate access to *this one* order."""

    order_id: str
    phone_last4: str

    @field_validator("order_id")
    @classmethod
    def _order_id_shape(cls, v: str) -> str:
        if not ORDER_ID.match(v):
            raise ValueError("order_id must look like FC-1234")
        return v

    @field_validator("phone_last4")
    @classmethod
    def _phone_last4_shape(cls, v: str) -> str:
        if not PHONE_LAST4.match(v):
            raise ValueError("phone_last4 must be exactly 4 digits")
        return v


class CreateCustomOrderArgs(BaseModel):
    """Side-effecting. Deliberately narrow: this is the schema-level half of
    the 'we collect a vibe, not a spec' boundary from ADR 001 — a customer
    cannot hand over more than two colors or a long prescriptive note, because
    the object that would carry more than that cannot validate.

    Deliberately does NOT include a phone number: whose order this is comes
    from the authenticated ``Session``, never from a value the model could be
    talked into repeating back differently — see ``fairy.tools.registry``."""

    color_preference: list[str] = Field(..., min_length=1, max_length=MAX_COLOR_PREFERENCES)
    material_preference: str | None = None
    inspiration_note: str = Field("", max_length=MAX_INSPIRATION_NOTE_CHARS)
    budget_tier: Literal["small", "medium", "statement"]

    @field_validator("color_preference")
    @classmethod
    def _colors_from_palette(cls, v: list[str]) -> list[str]:
        unknown = [c for c in v if c not in COLOR_PALETTE]
        if unknown:
            raise ValueError(f"not in the palette: {unknown} — choose from {COLOR_PALETTE}")
        return v

    @field_validator("budget_tier")
    @classmethod
    def _tier_exists(cls, v: str) -> str:
        if v not in BUDGET_TIERS:
            raise ValueError(f"unknown budget tier: {v}")
        return v


class BookPickupAppointmentArgs(BaseModel):
    """Side-effecting. ``order_id`` must already be ``ready_for_pickup`` —
    enforced by the tool, not by this schema, because it depends on stored
    state this object doesn't have access to."""

    order_id: str
    date: str  # ISO 8601, e.g. "2026-09-20"
    time_slot: str  # e.g. "16:00-17:00", must fall inside pickup hours

    @field_validator("order_id")
    @classmethod
    def _order_id_shape(cls, v: str) -> str:
        if not ORDER_ID.match(v):
            raise ValueError("order_id must look like FC-1234")
        return v

    @field_validator("date")
    @classmethod
    def _date_shape(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("date must be YYYY-MM-DD")
        return v


class EscalateToHumanArgs(BaseModel):
    """Terminal. Ends the automated turn — the assistant never resolves a
    defect refund or an insisted-on over-specification itself."""

    reason: Literal["defect_refund", "over_specification_insisted", "other"]
    order_id: str | None = None
    details: str = Field(..., max_length=1000)
