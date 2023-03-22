from __future__ import annotations

from datetime import datetime as dt
from unittest.mock import patch

import pytest

import myelectricaldatapy
from myelectricaldatapy import Enedis

from .consts import ACCESS
from .consts import DATASET_30 as DATASET
from .consts import ECOWATT, INVALID_ACCESS, INVALID_ECOWATT, TEMPO

PDL = "012345"
TOKEN = "xxxxxxxxxxxxx"


@pytest.mark.asyncio
async def test_ecowatt() -> None:
    """Test get ecowatt."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=ECOWATT
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_get_ecowatt()
        assert resultat["2023-01-22"]["value"] == 1

    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=INVALID_ECOWATT
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_get_ecowatt()
        assert resultat.get("2023-01-22") is None


@pytest.mark.asyncio
async def test_tempoday() -> None:
    """Test get tempo day."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=TEMPO
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_get_ecowatt()
        assert resultat["2023-3-1"] == "blue"


@pytest.mark.asyncio
async def test_valid_access() -> None:
    """Test access."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=ACCESS
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_valid_access(PDL)
        assert resultat["valid"] is True

        resultat = await api.async_has_access(PDL)
        assert resultat is True

    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=INVALID_ACCESS
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_valid_access(PDL)
        assert resultat["quota_reached"] is True


@pytest.mark.asyncio
async def test_fetch_data() -> None:
    """Test fetch data."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=DATASET
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_fetch_datas(
            service="comsumption_load_curve",
            pdl=PDL,
            start=dt.strptime("2022-12-30", "%Y-%m-%d"),
            end=dt.strptime("2022-12-31", "%Y-%m-%d"),
        )
        assert (
            resultat["meter_reading"]["interval_reading"]
            == DATASET["meter_reading"]["interval_reading"]  # noqa
        )


@pytest.mark.asyncio
async def test_load() -> None:
    """Test load object."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=DATASET
    ):
        api = Enedis(token=TOKEN)
        await api.async_get_max_power(PDL, dt.now(), dt.now())
        await api.async_get_contract(PDL)
        await api.async_get_address(PDL)
        await api.async_has_offpeak(PDL)
        await api.async_check_offpeak(PDL, dt.now())
        await api.async_get_identity(PDL)
        await api.async_get_daily_consumption(PDL, dt.now(), dt.now())
        await api.async_get_daily_production(PDL, dt.now(), dt.now())
        await api.async_get_details_production(PDL, dt.now(), dt.now())
