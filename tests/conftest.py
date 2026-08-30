"""Test helpers for MyElectricalData."""

from __future__ import annotations

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tests import load_fixture


@pytest.fixture(name="mock_access")
def mock_access(request) -> dict[str, Any]:
    if hasattr(request, "param") and request.param:
        return json.loads(load_fixture("invalid_access.json"))
    return json.loads(load_fixture("access.json"))


@pytest.fixture(name="mock_ecowatt")
def mock_ecowatt(request) -> dict[str, Any]:
    if hasattr(request, "param") and request.param:
        return {
            "detail": "Pas de données disponible entre la date du 2023-01-22 00:00:00 et 2023-01-22 00:00:00"
        }
    return json.loads(load_fixture("ecowatt.json"))


@pytest.fixture(name="mock_enedis")
def mock_enedis(mock_access, mock_ecowatt) -> Generator[AsyncMock, None, None]:
    """Mock a successful connection."""

    with (
        patch(
            "myelectricaldatapy.Enedis.async_get_daily_consumption",
            return_value=json.loads(load_fixture("daily.json")),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_daily_production",
            return_value=json.loads(load_fixture("daily.json")),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_details_consumption",
            return_value=json.loads(load_fixture("detail.json")),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_details_production",
            return_value=json.loads(load_fixture("detail.json")),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_valid_access",
            return_value=mock_access,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_contracts",
            return_value=json.loads(load_fixture("contract.json")),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_address",
            return_value=json.loads(load_fixture("address.json")),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_tempo",
            return_value=json.loads(load_fixture("tempo.json")),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_ecowatt",
            return_value=mock_ecowatt,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_tempo_days",
            return_value={"blue": 0, "white": 10, "red": 5},
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_tempo_prices",
            return_value={
                "red_hc": "0.1615",
                "red_hp": "0.7295",
                "blue_hc": "0.1356",
                "blue_hp": "0.1654",
                "white_hc": "0.1536",
                "white_hp": "0.1921",
            },
        ),
    ):
        yield AsyncMock()
