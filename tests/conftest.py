"""Test helpers for MyElectricalData."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

import myelectricaldatapy

from .consts import ACCESS, ADDRESS, CONTRACT, DATASET_30, DATASET_DAILY, ECOWATT, TEMPO


@pytest.fixture(name="mock_enedis")
def mock_enedis() -> Generator[AsyncMock, None, None]:
    """Mock a successful connection."""
    with (
        patch.object(
            myelectricaldatapy.Enedis,
            "async_get_daily_consumption",
            return_value=DATASET_DAILY,
        ),
        patch.object(
            myelectricaldatapy.Enedis,
            "async_get_daily_production",
            return_value=DATASET_DAILY,
        ),
        patch.object(
            myelectricaldatapy.Enedis,
            "async_get_details_consumption",
            return_value=DATASET_30,
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_valid_access", return_value=ACCESS
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_contract", return_value=CONTRACT
        ),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_address", return_value=ADDRESS
        ),
        patch.object(myelectricaldatapy.Enedis, "async_get_tempo", return_value=TEMPO),
        patch.object(
            myelectricaldatapy.Enedis, "async_get_ecowatt", return_value=ECOWATT
        ) as service_mock,
    ):
        yield service_mock
