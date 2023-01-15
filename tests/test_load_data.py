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
        myelectricaldatapy.auth.EnedisAuth, "request", return_value={}
    ), patch.object(
        EnedisByPDL, "async_get_tempoday", return_value=TEMPO
    ):
        api = EnedisByPDL(token=TOKEN, pdl=PDL)
        await api.async_load()
        await api.async_get_max_power(dt.now(), dt.now())
        await api.async_get_contract()
        await api.async_get_tempoday()
        await api.async_get_address()
        await api.async_get_ecowatt()
        await api.async_has_offpeak()
        await api.async_check_offpeak(dt.now())
        await api.async_get_identity()
        await api.async_get_daily_consumption(dt.now())
        await api.async_get_daily_production(dt.now())
        await api.async_get_details_production(dt.now(), dt.now())
        assert (
            api.power_datas["consumption"]
            == DATASET["meter_reading"]["interval_reading"]
        )
        await api.async_refresh()
        await api.async_close()


@pytest.mark.asyncio
async def test_analytcis() -> None:
    intervals = [(dt.strptime("08H00", "%HH%M"), dt.strptime("12H00", "%HH%M"))]
    dataset = DATASET["meter_reading"]["interval_reading"]
    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytcis(
        convertKwh=True,
        convertUTC=True,
        intervals=intervals,
        groupby="date",
        summary=True,
    )
    offpeak = analytics.set_price(resultat[0], 0.1641, True)
    normal = analytics.set_price(resultat[1], 0.18, True)
    print(offpeak)
    print(normal)
