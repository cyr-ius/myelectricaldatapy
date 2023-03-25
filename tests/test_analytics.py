from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import myelectricaldatapy
from myelectricaldatapy import EnedisByPDL

from .consts import ACCESS
from .consts import DATASET_30 as DS_30
from .consts import DATASET_DAILY as DS_DAILY
from .consts import DATASET_DAILY_COMPARE as DS_COMPARE
from .consts import TEMPO

PDL = "012345"
TOKEN = "xxxxxxxxxxxxx"


@pytest.mark.asyncio
async def test_compute() -> None:
    """Test standard."""
    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["notes"] == "standard"
    assert resultat[0]["value"] == 1.296

    dataset = DS_DAILY
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["notes"] == "standard"
    assert resultat[0]["value"] == 42.045


@pytest.mark.asyncio
async def test_without_offpeak() -> None:
    """Test without offpeak , with price."""
    dataset = DS_30
    prices: dict[str, Any] = {"mode": "consumption", "price_std": 0.17}
    # Test standard price
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_prices(**prices)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 0.22

    dataset = DS_DAILY
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_prices(**prices)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 7.15


@pytest.mark.asyncio
async def test_with_offpeak() -> None:
    """Test without offpeak , with price."""
    dataset = DS_30
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    prices: dict[str, Any] = {
        "mode": "consumption",
        "price_std": 0.17,
        "price_off": 0.18,
    }
    cumsum_value: dict[str, Any] = {
        "mode": "consumption",
        "value": 1000,
        "off_value": 1000,
    }
    cumsum_price: dict[str, Any] = {"mode": "consumption", "price": 0, "off_price": 0}
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 1.079
    assert resultat[0].get("sum_value") is not None
    assert resultat[0].get("sum_price") is not None
    print(resultat)

    # Without cums
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 1.079
    assert round(resultat[2]["price"], 3) == 0.833
    assert resultat[0].get("sum_value") is None
    print(resultat)

    # Whitout price
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        await api.async_update()
        resultat = api.consumption_stats
    assert resultat[27]["value"] == 1.296
    assert resultat[28]["value"] == 0.618
    print(resultat)

    # Daily
    dataset = DS_DAILY
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["value"] == 42.045
    print(resultat)


@pytest.mark.asyncio
async def test_daily_with_offpeak_analytics() -> None:
    prices: dict[str, Any] = {
        "mode": "consumption",
        "price_std": 0.17,
        "price_off": 0.18,
    }
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_DAILY
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        await api.async_update()
        resultat = api.consumption_stats
    assert resultat[359]["value"] == 68.68
    print(resultat)


@pytest.mark.asyncio
async def test_compare() -> None:
    prices: dict[str, Any] = {
        "mode": "consumption",
        "price_std": 0.17,
        "price_off": 0.18,
    }
    cumsum_value: dict[str, Any] = {"mode": "consumption", "value": 0, "off_value": 0}
    cumsum_price: dict[str, Any] = {"mode": "consumption", "price": 0, "off_price": 0}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat1 = api.consumption_stats

    print(resultat1)
    sum_value = 0
    for rslt in resultat1:
        sum_value = sum_value + rslt["value"]

    sum_value_1 = resultat1[26]["sum_value"] + resultat1[77]["sum_value"]
    assert round(sum_value, 3) == round(sum_value_1, 3)
    dataset = DS_COMPARE
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat2 = api.consumption_stats
    assert round(sum_value, 3) == resultat2[2]["sum_value"]
    print(resultat2)


@pytest.mark.asyncio
async def test_cumsums() -> None:
    prices: dict[str, Any] = {
        "mode": "consumption",
        "price_std": 0.17,
        "price_off": 0.18,
    }
    cumsum_value: dict[str, Any] = {
        "mode": "consumption",
        "value": 100,
        "off_value": 1000,
    }
    cumsum_price: dict[str, Any] = {"mode": "consumption", "price": 50, "off_price": 75}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat = api.consumption_stats
    # offpeak
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    # standard
    assert resultat[27]["sum_value"] == resultat[27]["value"] + 100
    assert resultat[27]["sum_price"] == resultat[27]["price"] + 50


@pytest.mark.asyncio
async def test_tempo() -> None:
    """Test tempo pricings."""
    prices: dict[str, Any] = {
        "mode": "consumption",
        "blue": 0.2,
        "white": 0.3,
        "red": 3,
        "blue_off": 0.1,
        "white_off": 0.2,
        "red_off": 1.5,
    }
    cumsum_value: dict[str, Any] = {
        "mode": "consumption",
        "value": 100,
        "off_value": 1000,
    }
    cumsum_price: dict[str, Any] = {"mode": "consumption", "price": 50, "off_price": 75}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ), patch.object(
        myelectricaldatapy.Enedis, "async_get_tempoday", return_value=TEMPO
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["tempo"] == "blue"
    assert resultat[0]["value"] == 1.079
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000


@pytest.mark.asyncio
async def test_standard_offpeak_cumsum() -> None:
    """Test with offpeak and cumsum."""
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    prices: dict[str, Any] = {"mode": "consumption", "price_std": 0.5, "price_off": 1}
    cumsum_value: dict[str, Any] = {
        "mode": "consumption",
        "value": 100,
        "off_value": 50,
    }
    cumsum_price: dict[str, Any] = {
        "mode": "consumption",
        "price": 1000,
        "off_price": 75,
    }

    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["value"] == 1.079

    # Test daily data , check ignore intervals.
    dataset = DS_DAILY
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        api.set_intervals(intervals)
        api.set_prices(**prices)
        api.set_cumsum_value(**cumsum_value)
        api.set_cumsum_price(**cumsum_price)
        await api.async_update()
        resultat = api.consumption_stats

    assert resultat[0]["price"] == resultat[0]["value"] * 0.5


@pytest.mark.asyncio
async def test_start_date() -> None:
    """Test with start_date."""
    dataset = DS_DAILY
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ), patch.object(
        myelectricaldatapy.Enedis, "async_valid_access", return_value=ACCESS
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        await api.async_update(start_date="2023-3-7")
        resultat = api.consumption_stats

    print(resultat)
    assert len(resultat) == 0

    dataset = DS_30
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        api = EnedisByPDL(
            pdl=PDL, token=TOKEN, svc_consumption="consumption_load_curve"
        )
        await api.async_update(start_date="2023-3-4")
        resultat = api.consumption_stats

    print(resultat)
    assert len(resultat) == 0
