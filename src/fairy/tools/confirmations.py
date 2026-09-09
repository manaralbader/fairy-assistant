"""Bilingual templates for turning a successful tool result into a short
customer-facing sentence. Used by two different callers for two different
reasons: :class:`~fairy.llm.sim.SimClient` uses these to stand in for what a
real model would compose given the tool result on its next turn; the router
uses the same templates directly for a *terminal* tool's result, because the
bounded loop ends the turn immediately on terminal success and no backend —
real or simulated — ever gets a turn to compose anything for it.
"""

from __future__ import annotations

TOOL_CONFIRMATIONS = {
    "check_order_status": {
        "en": lambda p: f"Order {p.get('order_id', '')} is currently \"{p.get('status', '')}\".",
        "ar": lambda p: f"طلبك {p.get('order_id', '')} حالته حاليًا \"{p.get('status', '')}\".",
    },
    "create_custom_order": {
        "en": lambda p: f"Your commission {p.get('order_id', '')} has been started.",
        "ar": lambda p: f"تم بدء طلبك المخصص برقم {p.get('order_id', '')}.",
    },
    "book_pickup_appointment": {
        "en": lambda p: (
            f"Pickup for {p.get('order_id', '')} is booked for "
            f"{p.get('pickup', {}).get('date', '')} {p.get('pickup', {}).get('time_slot', '')}."
        ),
        "ar": lambda p: (
            f"تم حجز موعد استلام طلبك {p.get('order_id', '')} بتاريخ "
            f"{p.get('pickup', {}).get('date', '')} في {p.get('pickup', {}).get('time_slot', '')}."
        ),
    },
    "escalate_to_human": {
        "en": lambda p: "I've flagged this for a person on our team to follow up with you directly.",
        "ar": lambda p: "قمت بتحويل هذا لأحد أفراد الفريق للتواصل معك مباشرة.",
    },
}
