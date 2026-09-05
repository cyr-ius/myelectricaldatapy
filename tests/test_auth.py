"""Tests for the low-level Enedis auth layer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

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
