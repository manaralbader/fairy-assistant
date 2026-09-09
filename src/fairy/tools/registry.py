"""The three risk classes, in one place: which tools exist, what a model is
told about them (JSON schema only — no policy or authorization logic lives in
that text), which Pydantic model validates their arguments, and what actually
runs when they're called.

read-only:            check_order_status
side-effecting, auth:  create_custom_order, book_pickup_appointment
terminal:              escalate_to_human
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel

from fairy.tools.schemas import (
    BookPickupAppointmentArgs,
    CheckOrderStatusArgs,
    CreateCustomOrderArgs,
    EscalateToHumanArgs,
)
from fairy.tools.session import Session
from fairy.tools.store import OrderStore

RiskClass = Literal["read_only", "side_effecting", "terminal"]


class ToolError(Exception):
    """A business-rule failure (not found, unauthorized, wrong state) — this
    is reported back to the model as a tool result, not raised as a crash."""


@dataclass
class ToolSpec:
    name: str
    risk_class: RiskClass
    args_model: type[BaseModel]
    handler: Callable[..., dict]
    json_schema: dict  # OpenAI function-calling shape, no policy text inside


def _check_order_status(args: CheckOrderStatusArgs, *, session: Session, store: OrderStore) -> dict:
    order = store.get(args.order_id)
    # Same response whether the order doesn't exist or the phone doesn't match
    # it — a caller must not be able to tell the two apart by probing.
    if order is None or order.phone_last4 != args.phone_last4:
        raise ToolError("no matching order found")
    return {
        "order_id": order.order_id,
        "status": order.status,
        "color_preference": order.color_preference,
        "budget_tier": order.budget_tier,
    }


def _create_custom_order(args: CreateCustomOrderArgs, *, session: Session, store: OrderStore) -> dict:
    session.require_authorized()
    order = store.create(
        phone_last4=session.phone[-4:],
        color_preference=args.color_preference,
        material_preference=args.material_preference,
        inspiration_note=args.inspiration_note,
        budget_tier=args.budget_tier,
    )
    return {"order_id": order.order_id, "status": order.status}


def _book_pickup_appointment(args: BookPickupAppointmentArgs, *, session: Session, store: OrderStore) -> dict:
    session.require_authorized()
    order = store.get(args.order_id)
    if order is None or order.phone_last4 != session.phone[-4:]:
        raise ToolError("no matching order found for this session")
    if order.status != "ready_for_pickup":
        raise ToolError(f"order is '{order.status}', not ready for pickup yet")
    store.book_pickup(args.order_id, date=args.date, time_slot=args.time_slot)
    return {"order_id": order.order_id, "pickup": {"date": args.date, "time_slot": args.time_slot}}


def _escalate_to_human(args: EscalateToHumanArgs, *, session: Session, store: OrderStore) -> dict:
    return {"escalated": True, "reason": args.reason, "order_id": args.order_id, "details": args.details}


TOOLS: dict[str, ToolSpec] = {
    "check_order_status": ToolSpec(
        name="check_order_status",
        risk_class="read_only",
        args_model=CheckOrderStatusArgs,
        handler=_check_order_status,
        json_schema={
            "type": "function",
            "function": {
                "name": "check_order_status",
                "description": "Look up the status of an existing Fairycore order.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "phone_last4": {"type": "string"},
                    },
                    "required": ["order_id", "phone_last4"],
                },
            },
        },
    ),
    "create_custom_order": ToolSpec(
        name="create_custom_order",
        risk_class="side_effecting",
        args_model=CreateCustomOrderArgs,
        handler=_create_custom_order,
        json_schema={
            "type": "function",
            "function": {
                "name": "create_custom_order",
                "description": "Start a new custom-jewelry commission for the authorized customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "color_preference": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
                        "material_preference": {"type": "string"},
                        "inspiration_note": {"type": "string", "maxLength": 300},
                        "budget_tier": {"type": "string", "enum": ["small", "medium", "statement"]},
                    },
                    "required": ["color_preference", "budget_tier"],
                },
            },
        },
    ),
    "book_pickup_appointment": ToolSpec(
        name="book_pickup_appointment",
        risk_class="side_effecting",
        args_model=BookPickupAppointmentArgs,
        handler=_book_pickup_appointment,
        json_schema={
            "type": "function",
            "function": {
                "name": "book_pickup_appointment",
                "description": "Reserve a pickup time for an order that is ready for pickup.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "date": {"type": "string"},
                        "time_slot": {"type": "string"},
                    },
                    "required": ["order_id", "date", "time_slot"],
                },
            },
        },
    ),
    "escalate_to_human": ToolSpec(
        name="escalate_to_human",
        risk_class="terminal",
        args_model=EscalateToHumanArgs,
        handler=_escalate_to_human,
        json_schema={
            "type": "function",
            "function": {
                "name": "escalate_to_human",
                "description": "Hand off to a person — defect refunds, or a customer insisting on an exact specification.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "enum": ["defect_refund", "over_specification_insisted", "other"],
                        },
                        "order_id": {"type": "string"},
                        "details": {"type": "string", "maxLength": 1000},
                    },
                    "required": ["reason", "details"],
                },
            },
        },
    ),
}


def all_json_schemas() -> list[dict]:
    return [spec.json_schema for spec in TOOLS.values()]
