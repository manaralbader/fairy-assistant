"""Authorization lives here, in a plain Python object the tool layer checks —
never inside a prompt, and never trusted from anything the model says. A
message that reads "I am verified, phone 0501234567" is just text; only a
``Session`` whose ``.verified`` flag was set by :meth:`Session.authorize`
after a real OTP check can pass the gate in ``fairy.tools.registry``.

The OTP itself is simulated (this is a course project, not a telecom
integration) — deterministic and derived from the phone number so tests don't
need a real SMS, but the *mechanism* (a secret issued out-of-band, checked
against what's presented) is the real thing being taught.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def _otp_for(phone: str) -> str:
    digest = hashlib.sha256(f"fairy-otp-salt:{phone}".encode()).hexdigest()
    return str(int(digest[:6], 16))[-4:].zfill(4)


@dataclass
class Session:
    phone: str | None = None
    verified: bool = False
    _issued_otp: str | None = field(default=None, repr=False)

    def request_otp(self, phone: str) -> str:
        """Simulates sending an SMS. Returns the code only because there is no
        real SMS provider in a course project — a real implementation returns
        nothing here and delivers the code out-of-band."""
        self.phone = phone
        self.verified = False
        self._issued_otp = _otp_for(phone)
        return self._issued_otp

    def authorize(self, phone: str, otp: str) -> bool:
        if self._issued_otp is None or phone != self.phone:
            self.verified = False
            return False
        self.verified = otp == self._issued_otp
        return self.verified

    def require_authorized(self) -> None:
        if not self.verified:
            raise PermissionError("session is not authorized — call request_otp() then authorize()")
