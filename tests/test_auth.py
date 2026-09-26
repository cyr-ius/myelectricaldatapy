"""Tests for the low-level Enedis auth layer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError
import pytest

from myelectricaldatapy import EnedisException, LimitReached, ThrottlingError
from myelectricaldatapy.auth import EnedisAuth

from .consts import TOKEN

THROTTLE_PAYLOAD = {
    "code": "900804",
    "message": "Message throttled out",
    "description": (
        "You have exceeded your quota .You can access API after "
        "2026-Sep-05 16:00:00+0000 UTC"
    ),
    "nextAccessTime": "2026-Sep-05 16:00:00+0000 UTC",
}


def _mock_session(payload: dict, status: int = 200) -> MagicMock:
    """Return a session whose request yields ``payload`` with the given status."""
    body = json.dumps(payload).encode()
    response = MagicMock()
    response.read = AsyncMock(return_value=body)
    response.raise_for_status = MagicMock()
    response.headers = {"Content-Type": "application/json"}
    response.status = status
    response.json = AsyncMock(return_value=payload)
    session = MagicMock()
    session.request = AsyncMock(return_value=response)
    return session


async def test_throttling_returns_dedicated_exception() -> None:
    """An HTTP 200 throttling body is raised as :class:`ThrottlingError`."""
    auth = EnedisAuth(_mock_session(THROTTLE_PAYLOAD), TOKEN)

    with pytest.raises(ThrottlingError) as excinfo:
        await auth.async_request("/valid_access/01234567890")

    error = excinfo.value
    assert error.next_access_time == "2026-Sep-05 16:00:00+0000 UTC"
    assert isinstance(error, LimitReached)
    assert isinstance(error, EnedisException)


async def test_regular_payload_is_returned() -> None:
    """A normal JSON body is passed through untouched."""
    auth = EnedisAuth(_mock_session({"valid": True}), TOKEN)

    assert await auth.async_request("/valid_access/01234567890") == {"valid": True}


def _mock_error_session(payload: dict, status: int) -> MagicMock:
    """Return a session whose request fails ``raise_for_status`` with ``payload``.

    Mirrors a gateway that returns the throttling body under a non-200
    status instead of the (more commonly observed) HTTP 200 success path.
    """
    body = json.dumps(payload).encode()
    response = MagicMock()
    response.read = AsyncMock(return_value=body)
    response.raise_for_status = MagicMock(
        side_effect=ClientResponseError(
            request_info=None,
            history=(),
            status=status,
            headers={"Content-Type": "application/json"},
        )
    )
    session = MagicMock()
    session.request = AsyncMock(return_value=response)
    return session


async def test_throttling_recognized_under_error_status() -> None:
    """The throttling body must be recognized even under a non-200 status.

    Regression test: the throttle signature (APIM code 900804) was only
    checked in the HTTP-200 success path, so the very same body arriving
    under an error status (anything other than 409) fell through to a bare
    ``EnedisException`` instead of ``ThrottlingError`` -- losing
    ``next_access_time`` and the caller's ability to back off correctly.
    """
    auth = EnedisAuth(_mock_error_session(THROTTLE_PAYLOAD, status=429), TOKEN)

    with pytest.raises(ThrottlingError) as excinfo:
        await auth.async_request("/valid_access/01234567890")

    assert excinfo.value.next_access_time == "2026-Sep-05 16:00:00+0000 UTC"


async def test_non_throttling_error_status_unchanged() -> None:
    """A genuine (non-throttle) error body under a non-409 status is unchanged."""
    auth = EnedisAuth(
        _mock_error_session({"detail": "Something else went wrong"}, status=400),
        TOKEN,
    )

    with pytest.raises(EnedisException) as excinfo:
        await auth.async_request("/valid_access/01234567890")

    assert not isinstance(excinfo.value, LimitReached)
