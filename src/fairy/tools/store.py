"""An in-memory order store. This is a notebook-scale demo, not a database —
the point is to give the tools something real to read and mutate, so the
authorization gate and the status-transition rule have actual state to guard
rather than being argued about in the abstract."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field


@dataclass
class Order:
    order_id: str
    phone_last4: str
    status: str
    color_preference: list[str] = field(default_factory=list)
    material_preference: str | None = None
    inspiration_note: str = ""
    budget_tier: str = "small"
    pickup_appointment: dict | None = None


class OrderStore:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._ids = itertools.count(1000)

    def seed(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def create(self, *, phone_last4: str, color_preference, material_preference, inspiration_note, budget_tier) -> Order:
        order_id = f"FC-{next(self._ids)}"
        order = Order(
            order_id=order_id,
            phone_last4=phone_last4,
            status="pending_confirmation",
            color_preference=list(color_preference),
            material_preference=material_preference,
            inspiration_note=inspiration_note,
            budget_tier=budget_tier,
        )
        self._orders[order_id] = order
        return order

    def book_pickup(self, order_id: str, *, date: str, time_slot: str) -> Order | None:
        order = self._orders.get(order_id)
        if order is None:
            return None
        order.pickup_appointment = {"date": date, "time_slot": time_slot}
        return order


def demo_store() -> OrderStore:
    """A few fixture orders, for tests and for the notebook's own walkthrough."""
    store = OrderStore()
    store.seed(
        Order(
            order_id="FC-1001",
            phone_last4="4321",
            status="in_progress",
            color_preference=["lavender", "silver"],
            budget_tier="medium",
        )
    )
    store.seed(
        Order(
            order_id="FC-1002",
            phone_last4="9876",
            status="ready_for_pickup",
            color_preference=["blush pink"],
            budget_tier="small",
        )
    )
    return store
