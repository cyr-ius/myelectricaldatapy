"""Tests  Enedis api."""
from __future__ import annotations

from datetime import datetime as dt
from unittest.mock import patch

import pytest
from freezegun import freeze_time

import myelectricaldatapy
from myelectricaldatapy import Enedis, EnedisByPDL

from .consts import ACCESS
from .consts import DATASET_30 as DS_30
from .consts import ECOWATT, INVALID_ACCESS, INVALID_ECOWATT, TEMPO

PDL = "012345"
TOKEN = "xxxxxxxxxxxxx"


@freeze_time("2023-01-23")
@pytest.mark.asyncio
async def test_ecowatt() -> None:
    """Test get ecowatt."""
    api = Enedis(token=TOKEN)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=ECOWATT
    ):
        resultat = await api.async_get_ecowatt()
        assert resultat["2023-01-22"]["value"] == 1

    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=INVALID_ECOWATT
    ):
        resultat = await api.async_get_ecowatt()
        assert resultat.get("2023-01-22") is None

    mypdl = EnedisByPDL(pdl=PDL, token=TOKEN)
    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ), patch.object(
        myelectricaldatapy.Enedis, "async_get_ecowatt", return_value=ECOWATT
    ):
        mypdl.ecowatt_subscription(True)
        await mypdl.async_update()

    print(mypdl.ecowatt_day)
    assert mypdl.ecowatt_day["message"] == "Pas d’alerte."


@freeze_time("2023-3-3")
@pytest.mark.asyncio
async def test_tempoday() -> None:
    """Test get tempo day."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=TEMPO
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_get_tempo()
        assert resultat["2023-3-1"] == "blue"

    mypdl = EnedisByPDL(pdl=PDL, token=TOKEN)
    dataset = DS_30
    modes = {"consumption": {"service": "consumption_load_curve"}}
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ), patch.object(myelectricaldatapy.Enedis, "async_get_tempo", return_value=TEMPO):
        mypdl.tempo_subscription(True)
        await mypdl.async_update(modes=modes)
        resultat = mypdl.stats["consumption"]
    assert mypdl.tempo_day == "blue"


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
    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
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
            == dataset["meter_reading"]["interval_reading"]  # noqa
        )


@pytest.mark.asyncio
async def test_load() -> None:
    """Test load object."""
    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
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
