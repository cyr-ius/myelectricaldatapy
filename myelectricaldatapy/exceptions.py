"""Class exception."""

from typing import Any


class EnedisException(Exception):
    """Enedis exception."""


class LimitReached(EnedisException):
    """Limit reached exception."""


class ThrottlingError(LimitReached):
    """Raised when MyElectricalData throttles the request.

    The gateway answers with an HTTP 200 status and a body such as::

        {"code": "900804", "message": "Message throttled out",
         "description": "You have exceeded your quota ...",
         "nextAccessTime": "2026-Sep-05 16:00:00+0000 UTC"}

    ``next_access_time`` carries the raw ``nextAccessTime`` string when the
    payload provides it, so callers can back off until the quota resets.
    """

    def __init__(self, detail: Any, next_access_time: str | None = None) -> None:
        """Init."""
        super().__init__(detail)
        self.next_access_time = next_access_time


class TimeoutExceededError(EnedisException):
    """Timeout exceeded exception."""


class HttpRequestError(EnedisException):
    """Http request error."""


class PayloadError(EnedisException):
    """Raised when an API payload cannot be decoded or does not match the schema."""


class AnalyticsError(EnedisException):
    """Raised when analytics computation fails on the provided dataset."""
