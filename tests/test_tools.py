"""Tests for the tool layer: the bounded loop, the validate/repair path, and
— the negative cases the rubric specifically wants as green assert-shaped
tests — that authorization actually lives in the session object and not in
whatever the model claims."""

from __future__ import annotations

from fairy.llm.fake import FakeClient
from fairy.llm.interfaces import Message
from fairy.tools.loop import FALLBACK_TEXT, run_tool_loop
from fairy.tools.session import Session
from fairy.tools.store import demo_store


def authorized_session(phone: str = "0501234321") -> Session:
    session = Session()
    otp = session.request_otp(phone)
    assert session.authorize(phone, otp)
    return session


def test_read_only_lookup_happy_path():
    client = (
        FakeClient()
        .script_tool_call("check_order_status", {"order_id": "FC-1001", "phone_last4": "4321"})
        .script_text("Your order is in progress.")
    )
    result = run_tool_loop(
        client, [Message(role="user", content="where is my order?")], session=Session(), store=demo_store()
    )
    assert result.final_text == "Your order is in progress."
    assert result.log == [{"iteration": 1, "tool": "check_order_status", "risk_class": "read_only", "outcome": "ok"}]


def test_check_order_status_does_not_need_authorization():
    """Read-only really is read-only: no session verification required."""
    client = FakeClient().script_tool_call(
        "check_order_status", {"order_id": "FC-1001", "phone_last4": "4321"}
    ).script_text("ok")
    result = run_tool_loop(
        client, [Message(role="user", content="status?")], session=Session(), store=demo_store()
    )
    assert result.log[0]["outcome"] == "ok"


def test_check_order_status_does_not_leak_existence_on_wrong_phone():
    client = FakeClient().script_tool_call(
        "check_order_status", {"order_id": "FC-1001", "phone_last4": "0000"}
    ).script_text("not found")
    result = run_tool_loop(
        client, [Message(role="user", content="status?")], session=Session(), store=demo_store()
    )
    assert result.log[0]["outcome"] == "tool_error"


def test_side_effecting_tool_blocked_without_an_authorized_session_even_with_valid_arguments():
    """The negative safety case: perfectly valid schema arguments are not
    enough to create an order — the session must actually be authorized, and
    nothing in the tool arguments themselves can satisfy that."""
    client = FakeClient().script_tool_call(
        "create_custom_order",
        {
            "color_preference": ["lavender"],
            "budget_tier": "small",
        },
    ).script_text("cannot proceed")
    result = run_tool_loop(
        client, [Message(role="user", content="start a new order")], session=Session(), store=demo_store()
    )
    assert result.log[0]["outcome"] == "tool_error"


def test_side_effecting_tool_succeeds_once_the_session_is_actually_authorized():
    client = FakeClient().script_tool_call(
        "create_custom_order",
        {
            "color_preference": ["lavender", "silver"],
            "budget_tier": "medium",
        },
    ).script_text("order started")
    result = run_tool_loop(
        client,
        [Message(role="user", content="start a new order")],
        session=authorized_session("0501234321"),
        store=demo_store(),
    )
    assert result.log[0]["outcome"] == "ok"
    assert result.final_text == "order started"


def test_over_specification_boundary_rejects_a_third_color():
    """Schema-level enforcement of ADR 001's 'we collect a vibe, not a spec':
    more than two colors cannot validate, regardless of what the model sent."""
    client = FakeClient().script_tool_call(
        "create_custom_order",
        {
            "color_preference": ["lavender", "silver", "gold"],
            "budget_tier": "small",
        },
    ).script_text("please narrow it down")
    result = run_tool_loop(
        client,
        [Message(role="user", content="start a new order")],
        session=authorized_session("0501234321"),
        store=demo_store(),
    )
    assert result.log[0]["outcome"] == "validation_error"


def test_pickup_booking_rejected_when_order_is_not_ready():
    # FC-1001 is "in_progress", not "ready_for_pickup" — matching the session
    # to its phone so this exercises the status rule specifically, not the
    # ownership check.
    client = FakeClient().script_tool_call(
        "book_pickup_appointment", {"order_id": "FC-1001", "date": "2026-09-20", "time_slot": "16:00-17:00"}
    ).script_text("not ready yet")
    result = run_tool_loop(
        client,
        [Message(role="user", content="book pickup")],
        session=authorized_session("0501234321"),
        store=demo_store(),
    )
    assert result.log[0]["outcome"] == "tool_error"


def test_pickup_booking_succeeds_when_order_is_ready():
    client = FakeClient().script_tool_call(
        "book_pickup_appointment", {"order_id": "FC-1002", "date": "2026-09-20", "time_slot": "16:00-17:00"}
    ).script_text("booked")
    result = run_tool_loop(
        client,
        [Message(role="user", content="book pickup")],
        session=authorized_session("0509876"),
        store=demo_store(),
    )
    assert result.log[0]["outcome"] == "ok"


def test_malformed_arguments_are_reported_and_recovered_on_the_next_turn():
    client = (
        FakeClient()
        .script_tool_call("check_order_status", arguments="{not valid json")
        .script_tool_call("check_order_status", {"order_id": "FC-1001", "phone_last4": "4321"})
        .script_text("recovered")
    )
    result = run_tool_loop(
        client, [Message(role="user", content="status?")], session=Session(), store=demo_store()
    )
    outcomes = [entry["outcome"] for entry in result.log]
    assert outcomes == ["validation_error", "ok"]
    assert result.final_text == "recovered"


def test_bounded_loop_stops_a_model_that_never_gives_up():
    client = FakeClient().script_endless_tool_calls(
        "check_order_status", {"order_id": "FC-9999", "phone_last4": "0000"}
    )
    result = run_tool_loop(
        client, [Message(role="user", content="status?")], session=Session(), store=demo_store(), max_iterations=3
    )
    assert result.final_text == FALLBACK_TEXT
    assert result.escalated is True
    assert result.log[-1]["outcome"] == "bounded_loop_exhausted"
    assert client.call_count == 3


def test_terminal_tool_ends_the_loop_immediately():
    client = FakeClient().script_tool_call(
        "escalate_to_human", {"reason": "defect_refund", "details": "a bead fell off within a week"}
    )
    result = run_tool_loop(
        client, [Message(role="user", content="my bracelet broke")], session=Session(), store=demo_store()
    )
    assert result.escalated is True
    assert result.log == [{"iteration": 1, "tool": "escalate_to_human", "risk_class": "terminal", "outcome": "ok"}]
    assert client.call_count == 1  # never asked the model again after the terminal tool succeeded
