from __future__ import annotations

import pytest

from fairy.tools.session import Session


def test_authorize_succeeds_with_the_correct_otp():
    session = Session()
    otp = session.request_otp("0501234321")
    assert session.authorize("0501234321", otp) is True
    assert session.verified is True


def test_authorize_fails_with_the_wrong_otp():
    session = Session()
    session.request_otp("0501234321")
    assert session.authorize("0501234321", "0000") is False
    assert session.verified is False


def test_authorize_fails_for_a_different_phone_than_the_otp_was_issued_to():
    session = Session()
    otp = session.request_otp("0501234321")
    assert session.authorize("0509999999", otp) is False


def test_require_authorized_raises_when_not_verified():
    session = Session()
    with pytest.raises(PermissionError):
        session.require_authorized()


def test_require_authorized_passes_once_verified():
    session = Session()
    otp = session.request_otp("0501234321")
    session.authorize("0501234321", otp)
    session.require_authorized()  # no raise
