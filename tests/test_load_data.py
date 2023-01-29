from __future__ import annotations

from datetime import datetime as dt
from unittest.mock import patch

import pytest

import myelectricaldatapy
from myelectricaldatapy import EnedisAnalytics, EnedisByPDL

from .consts import ACCESS, DATASET, ECOWATT, INVALID_ACCESS, INVALID_ECOWATT, TEMPO

PDL = "012345"
TOKEN = "xxxxxxxxxxxxx"


@pytest.mark.asyncio
async def test_ecowatt() -> None:
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=ECOWATT
    ):
        api = EnedisByPDL(token=TOKEN)
        resultat = await api.async_get_ecowatt()
        assert resultat["2023-01-22"]["value"] == 1

    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=INVALID_ECOWATT
    ):
        api = EnedisByPDL(token=TOKEN)
        resultat = await api.async_get_ecowatt()
        assert resultat.get("2023-01-22") is None


@pytest.mark.asyncio
async def test_tempoday() -> None:
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=TEMPO
    ):
        api = EnedisByPDL(token=TOKEN)
        resultat = await api.async_get_ecowatt()
        assert resultat["2023-01-22"] == "BLUE"


@pytest.mark.asyncio
async def test_valid_access() -> None:
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=ACCESS
    ):
        api = EnedisByPDL(token=TOKEN)
        resultat = await api.async_valid_access(PDL)
        assert resultat["valid"] is True

    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=INVALID_ACCESS
    ):
        api = EnedisByPDL(token=TOKEN)
        resultat = await api.async_valid_access(PDL)
        assert resultat["quota_reached"] is True


@pytest.mark.asyncio
async def test_fetch_data() -> None:
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=DATASET
    ):
        api = EnedisByPDL(token=TOKEN)
        resultat = await api.async_fetch_datas(
            service="comsumption_load_curve",
            pdl=PDL,
            start=dt.strptime("2022-12-30", "%Y-%m-%d"),
            end=dt.strptime("2022-12-31", "%Y-%m-%d"),
        )
        assert (
            resultat["meter_reading"]["interval_reading"]
            == DATASET["meter_reading"]["interval_reading"]
        )


@pytest.mark.asyncio
async def test_load() -> None:
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=DATASET
    ):
        api = EnedisByPDL(token=TOKEN)
        await api.async_get_max_power(PDL, dt.now(), dt.now())
        await api.async_get_contract(PDL)
        await api.async_get_address(PDL)
        await api.async_has_offpeak(PDL)
        await api.async_check_offpeak(PDL, dt.now())
        await api.async_get_identity(PDL)
        await api.async_get_daily_consumption(PDL, dt.now(), dt.now())
        await api.async_get_daily_production(PDL, dt.now(), dt.now())
        await api.async_get_details_production(PDL, dt.now(), dt.now())
        await api.async_close()


@pytest.mark.asyncio
async def test_analytcis() -> None:
    dataset = DATASET["meter_reading"]["interval_reading"]
    cumsum = 62.533
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        intervals=intervals,
        freq="D",
        groupby="date",
        summary=True,
        cumsum=cumsum,
    )
    resultat = analytics.set_price(resultat, 0.1641, True)
    assert resultat[0]["value"] == 18.852
    print(resultat)
    # Inverse
    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        intervals=intervals,
        freq="D",
        groupby="date",
        summary=True,
        cumsum=cumsum,
        reverse=True,
    )
    resultat = analytics.set_price(resultat, 0.1641, True)
    assert resultat[0]["value"] == 48.482
    print(resultat)
    # Other
    analytics = EnedisAnalytics(dataset)
    cumsum = 744.86
    intervals = [
        ("00:00:00", "01:30:00"),
        ("08:00:00", "12:30:00"),
        ("14:00:00", "00:00:00"),
    ]
    resultat = analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        intervals=intervals,
        freq="D",
        groupby="date",
        summary=True,
        cumsum=cumsum,
    )
    resultat = analytics.set_price(resultat, 0.1641, True)
    assert resultat[0]["value"] == 29.63
    # Other
    value = analytics.get_last_value(resultat, "date", "sum_value")
    assert value == 920.566
    resultat = analytics.get_data_analytcis(
        convertKwh=False,
        convertUTC=False,
        intervals=intervals,
        freq="D",
        groupby="date",
        summary=False,
        cumsum=cumsum,
    )


@pytest.mark.asyncio
async def test_empty() -> None:
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    analytics = EnedisAnalytics([])
    analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        start_date="2000-01-01",
        intervals=intervals,
        groupby="date",
        summary=True,
    )
    analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        start_date="2000-01-01",
        intervals=None,
        groupby="date",
        summary=True,
    )
    analytics = EnedisAnalytics(None)
    analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        start_date="2000-01-01",
        intervals=None,
        groupby="date",
        summary=True,
    )


@pytest.mark.asyncio
async def test_nodata() -> None:
    analytics = EnedisAnalytics([])
    resultat = analytics.get_data_analytcis()
    offpeak = analytics.set_price(resultat, 0.1641, True)
    assert not offpeak
