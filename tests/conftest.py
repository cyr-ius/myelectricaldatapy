"""Test helpers for MyElectricalData."""

from __future__ import annotations

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from myelectricaldatapy.types import (
    AccessResponse,
    CustomerResponse,
    DataCollect,
    EcowattResponse,
    Prices,
    TempoDays,
    TempoPrice,
    TempoResponse,
    UsagePoint,
)
from tests import load_fixture


@pytest.fixture(name="mock_access")
def mock_access(request) -> AccessResponse:
    if hasattr(request, "param") and request.param:
        return AccessResponse.model_validate(
            json.loads(load_fixture("invalid_access.json"))
        )
    return AccessResponse.model_validate(json.loads(load_fixture("access.json")))


@pytest.fixture(name="mock_ecowatt")
def mock_ecowatt(request):
    if hasattr(request, "param") and request.param:
        return {
            "detail": "Pas de données disponible entre la date du 2023-01-22 00:00:00 et 2023-01-22 00:00:00"
        }
    return EcowattResponse.validate_python(json.loads(load_fixture("ecowatt.json")))


@pytest.fixture(name="mock_enedis")
def mock_enedis(mock_access, mock_ecowatt) -> Generator[AsyncMock, None, None]:
    """Mock a successful connection."""

    daily = DataCollect.model_validate(json.loads(load_fixture("daily.json")))
    detail = DataCollect.model_validate(json.loads(load_fixture("detail.json")))
    contracts = CustomerResponse.model_validate(
        json.loads(load_fixture("contract.json"))
    )
    address_payload = json.loads(load_fixture("address.json"))
    address = UsagePoint.model_validate(
        address_payload["customer"]["usage_points"][0]["usage_point"]
    )
    tempo = TempoResponse.validate_python(json.loads(load_fixture("tempo.json")))

    with (
        patch(
            "myelectricaldatapy.Enedis.async_get_daily_consumption",
            return_value=daily,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_daily_production",
            return_value=daily,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_details_consumption",
            return_value=detail,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_details_production",
            return_value=detail,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_valid_access",
            return_value=mock_access,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_contracts",
            return_value=contracts,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_address",
            return_value=address,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_tempo",
            return_value=tempo,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_ecowatt",
            return_value=mock_ecowatt,
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_tempo_days",
            return_value=TempoDays(blue=0, white=10, red=5),
        ),
        patch(
            "myelectricaldatapy.Enedis.async_get_tempo_prices",
            return_value=Prices(
                standard=TempoPrice(blue=0.1654, white=0.1921, red=0.7295),
                offpeak=TempoPrice(blue=0.1356, white=0.1536, red=0.1615),
            ),
        ),
    ):
        yield AsyncMock()
