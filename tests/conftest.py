"""Test helpers for MyElectricalData."""

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import myelectricaldatapy

from . import load_fixture


@pytest.fixture(name="mock_detail")
def mock_detail() -> dict[str, Any]:
    return json.loads(load_fixture("detail.json"))


@pytest.fixture(name="mock_daily")
def mock_daily() -> dict[str, Any]:
    return json.loads(load_fixture("daily.json"))


@pytest.fixture(name="mock_contract")
def mock_contract() -> dict[str, Any]:
    return json.loads(load_fixture("contract.json"))


@pytest.fixture(name="mock_access")
def mock_access(request) -> dict[str, Any]:
    if hasattr(request, "param") and request.param:
        return json.loads(load_fixture("invalid_access.json"))
    return json.loads(load_fixture("access.json"))


@pytest.fixture(name="mock_address")
def mock_address() -> dict[str, Any]:
    return json.loads(load_fixture("address.json"))


@pytest.fixture(name="mock_tempo")
def mock_tempo(return_invalid: bool = False) -> dict[str, Any]:
    return json.loads(load_fixture("tempo.json"))


@pytest.fixture(name="mock_ecowatt")
def mock_ecowatt(request) -> dict[str, Any]:
    if hasattr(request, "param") and request.param:
        return {
            "detail": "Pas de données disponible entre la date du 2023-01-22 00:00:00 et 2023-01-22 00:00:00"  # noqa
        }
    return json.loads(load_fixture("ecowatt.json"))


@pytest.fixture(name="mock_enedis")
def mock_enedis(
    mock_detail,
    mock_daily,
    mock_contract,
    mock_access,
    mock_address,
    mock_tempo,
    mock_ecowatt,
) -> Generator[AsyncMock, None, None]:
    """Mock a successful connection."""

    with (
        patch.object(
            myelectricaldatapy.Enedis,
            "async_get_daily_consumption",
            return_value=mock_daily,
        ),
        patch.object(
            myelectricaldatapy.Enedis,
            "async_get_daily_production",
            return_value=mock_daily,
        ),
        patch.object(
            myelectricaldatapy.Enedis,
            "async_get_details_consumption",
            return_value=mock_detail,
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_valid_access", return_value=mock_access
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_contract", return_value=mock_contract
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_address", return_value=mock_address
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_tempo", return_value=mock_tempo
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_ecowatt", return_value=mock_ecowatt
        ),
    ):
        yield AsyncMock()


@pytest.fixture(name="mock_base")
def mock_base(
    mock_access, mock_contract, mock_address, mock_tempo, mock_ecowatt
) -> Generator[AsyncMock, None, None]:
    """Mock a successful connection."""
    with (
        patch.object(
            myelectricaldatapy.Enedis, "async_valid_access", return_value=mock_access
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_contract", return_value=mock_contract
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_address", return_value=mock_address
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_tempo", return_value=mock_tempo
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_ecowatt", return_value=mock_ecowatt
        ),
    ):
        yield AsyncMock()
