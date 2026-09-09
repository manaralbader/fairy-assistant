"""Direct tests of the validated request objects — independent of the tool
loop, so a schema regression shows up here first."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fairy.tools.schemas import CheckOrderStatusArgs, CreateCustomOrderArgs


def test_valid_custom_order_passes():
    args = CreateCustomOrderArgs(color_preference=["lavender", "gold"], budget_tier="medium")
    assert args.budget_tier == "medium"


def test_more_than_two_colors_is_rejected():
    with pytest.raises(ValidationError):
        CreateCustomOrderArgs(color_preference=["lavender", "gold", "silver"], budget_tier="small")


def test_a_color_outside_the_palette_is_rejected():
    with pytest.raises(ValidationError):
        CreateCustomOrderArgs(color_preference=["neon orange"], budget_tier="small")


def test_inspiration_note_over_300_chars_is_rejected():
    with pytest.raises(ValidationError):
        CreateCustomOrderArgs(color_preference=["gold"], budget_tier="small", inspiration_note="x" * 301)


def test_unknown_budget_tier_is_rejected():
    with pytest.raises(ValidationError):
        CreateCustomOrderArgs(color_preference=["gold"], budget_tier="huge")


def test_order_id_must_match_the_fc_shape():
    with pytest.raises(ValidationError):
        CheckOrderStatusArgs(order_id="not-an-id", phone_last4="1234")


def test_phone_last4_must_be_four_digits():
    with pytest.raises(ValidationError):
        CheckOrderStatusArgs(order_id="FC-1001", phone_last4="12")
