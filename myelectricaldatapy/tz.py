"""Local timezone helpers.

The Enedis/RTE APIs return naive timestamps that represent local wall-clock
time (see tests/fixtures, e.g. access.json's "last_call"), so this library
treats "naive datetime" as "local time" throughout. These helpers make that
convention explicit and DST-safe, instead of relying on a fixed UTC offset
captured once at import time.
"""

from __future__ import annotations

from datetime import datetime as dt, timezone as _timezone, tzinfo as _tzinfo
import os
from typing import cast
from zoneinfo import ZoneInfo


def _resolve_local_timezone() -> _tzinfo:
    """Resolve the local IANA timezone, DST-aware.

    Falls back to the fixed UTC offset captured at call time when the
    system timezone database cannot be resolved (e.g. non-Linux hosts).
    """
    try:
        tz_path = os.path.realpath("/etc/localtime")
        return ZoneInfo(tz_path.split("zoneinfo/")[-1])
    except Exception:  # noqa: BLE001
        # dt.now().astimezone() always sets tzinfo when called without
        # arguments; typeshed just can't express that.
        return cast(_tzinfo, dt.now().astimezone().tzinfo) or _timezone.utc


LOCAL_TIMEZONE = _resolve_local_timezone()


def local_now() -> dt:
    """Return the current time, timezone-aware in the local zone."""
    return dt.now(tz=LOCAL_TIMEZONE)


def as_local(value: dt) -> dt:
    """Attach the local timezone to a naive datetime; pass aware ones through."""
    if value.tzinfo is None:
        return value.replace(tzinfo=LOCAL_TIMEZONE)
    return value
