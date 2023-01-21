from __future__ import annotations

from datetime import datetime as dt
from typing import Any
from unittest.mock import patch

import pytest

import myelectricaldatapy
from myelectricaldatapy import EnedisAnalytics, EnedisByPDL

from .consts import DATASET

PDL = "012345"
TOKEN = "xxxxxxxxxxxxx"

VALID = {
    "valid": False,
    "consent_expiration_date": "2026-01-14T15:32:38",
    "call_number": 7,
    "quota_reached": False,
    "quota_limit": 50,
    "quota_reset_at": "2023-01-14T23:59:59.999999",
    "last_call": "2023-01-07T13:58:24.532501",
    "ban": False,
}

INVALID = {
    "valid": False,
    "information": "Vous avez dépassé votre quota journalier (50)",
    "consent_expiration_date": "2026-01-14T15:32:38",
    "call_number": 65,
    "quota_reached": True,
    "quota_limit": 50,
    "quota_reset_at": "2023-01-14T23:59:59.999999",
    "last_call": "2023-01-07T13:58:24.532501",
    "ban": False,
}


CONTRACT: dict[str, Any] = {}
TEMPO = "RED"


@pytest.mark.asyncio
async def test_load() -> None:
    with patch.object(
        EnedisByPDL, "async_get_details_consumption", return_value=DATASET
    ), patch.object(
        EnedisByPDL, "async_get_contract", return_value=CONTRACT
    ), patch.object(
        EnedisByPDL, "async_valid_access", return_value=VALID
    ), patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=DATASET
    ), patch.object(
        EnedisByPDL, "async_get_tempoday", return_value=TEMPO
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
        await api.async_get_max_power(PDL, dt.now(), dt.now())
        await api.async_get_contract(PDL)
        await api.async_get_tempoday()
        await api.async_get_address(PDL)
        await api.async_get_ecowatt()
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
    intervals = [
        (dt.strptime("01H30", "%HH%M"), dt.strptime("08H00", "%HH%M")),
        (dt.strptime("12H30", "%HH%M"), dt.strptime("14H00", "%HH%M")),
    ]
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
    print(resultat)
    analytics = EnedisAnalytics(dataset)
    cumsum = 744.86
    intervals = [
        (dt.strptime("00H00", "%HH%M"), dt.strptime("01H30", "%HH%M")),
        (dt.strptime("08H00", "%HH%M"), dt.strptime("12H30", "%HH%M")),
        (dt.strptime("14H00", "%HH%M"), dt.strptime("00H00", "%HH%M")),
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
    print(resultat)
    offpeak = analytics.set_price(resultat, 0.1641, True)
    assert offpeak[0]["value"] == 29.63
    value = analytics.get_last_value(resultat, "date", "sum_value")
    assert value == 920.566


@pytest.mark.asyncio
async def test_empty() -> None:
    intervals = [(dt.strptime("08H00", "%HH%M"), dt.strptime("12H00", "%HH%M"))]
    analytics = EnedisAnalytics([])
    resultat = analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        start_date="2000-01-01",
        intervals=intervals,
        groupby="date",
        summary=True,
    )
    offpeak = analytics.set_price(resultat, 0.1641, True)
    assert not offpeak


@pytest.mark.asyncio
async def test_nodata() -> None:
    analytics = EnedisAnalytics([])
    resultat = analytics.get_data_analytcis()
    offpeak = analytics.set_price(resultat, 0.1641, True)
    assert not offpeak
