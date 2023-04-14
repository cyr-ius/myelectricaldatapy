"""Tests analytics."""
from __future__ import annotations

from datetime import datetime as dt
from typing import Any
from unittest.mock import patch

import pytest
from freezegun import freeze_time

import myelectricaldatapy
from myelectricaldatapy import EnedisByPDL

from .consts import ACCESS
from .consts import DATASET_30 as DS_30
from .consts import DATASET_DAILY as DS_DAILY
from .consts import DATASET_DAILY_COMPARE as DS_COMPARE
from .consts import TEMPO

PDL = "012345"
TOKEN = "xxxxxxxxxxxxx"


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_compute() -> None:
    """Test standard."""
    dataset = DS_30
    modes = {"consumption": {"service": "consumption_load_curve"}}
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert resultat[0]["value"] == 1.296

    dataset = DS_DAILY
    modes = {"consumption": {"service": "daily_consumption"}}
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert resultat[0]["value"] == 42.045


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_without_offpeak() -> None:
    """Test without offpeak , with price."""
    dataset = DS_30
    prices: dict[str, Any] = {"standard": {"price": 0.17}}
    modes = {"consumption": {"service": "consumption_load_curve"}}
    # Test standard price
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_prices("consumption", prices)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 0.22

    dataset = DS_DAILY
    modes = {"consumption": {"service": "daily_consumption"}}
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 7.15


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_with_offpeak() -> None:
    """Test without offpeak , with price."""
    dataset = DS_30
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    modes = {"consumption": {"service": "consumption_load_curve"}}
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 1.079
    assert resultat[0].get("sum_value") is not None
    assert resultat[0].get("sum_price") is not None
    print(resultat)

    # Without cums
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 1.079
    assert round(resultat[2]["price"], 3) == 0.833
    assert resultat[0].get("sum_value") == 1.079
    print(resultat)

    # Whitout price
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]
    assert resultat[27]["value"] == 1.296
    assert resultat[28]["value"] == 0.618
    print(resultat)

    # Daily
    dataset = DS_DAILY
    modes = {"consumption": {"service": "daily_consumption"}}
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_prices("consumption", prices)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["value"] == 42.045
    print(resultat)


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_daily_with_offpeak() -> None:
    """Test daily with offpeak."""
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    modes = {"consumption": {"service": "daily_consumption"}}
    dataset = DS_DAILY
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]
    assert resultat[359]["value"] == 68.68
    print(resultat)


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_compare() -> None:
    """Test details compare."""
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    cumsum_value: dict[str, Any] = {
        "standard": {"sum_value": 0},
        "offpeak": {"sum_value": 0},
    }
    cumsum_price: dict[str, Any] = {
        "standard": {"sum_price": 0},
        "offpeak": {"sum_price": 0},
    }
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    modes = {"consumption": {"service": "consumption_load_curve"}}

    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    api.set_cumsum("consumption", "value", cumsum_value)
    api.set_cumsum("consumption", "price", cumsum_price)

    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat1 = api.stats["consumption"]

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
        await api.async_update(modes=modes)
        resultat2 = api.stats["consumption"]
    assert round(sum_value, 3) == resultat2[2]["sum_value"]
    print(resultat2)


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_cumsums() -> None:
    """Test cummulative summary."""
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    cumsum_value: dict[str, Any] = {"standard": 100, "offpeak": 1000}
    cumsum_price: dict[str, Any] = {"standard": 50, "offpeak": 75}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    modes = {
        "consumption": {
            "service": "consumption_load_curve",
            "start": dt.strptime("2023-03-01", "%Y-%m-%d"),
            "end": dt.strptime("2023-03-08", "%Y-%m-%d"),
        }
    }
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    api.set_cumsum("consumption", "value", cumsum_value)
    api.set_cumsum("consumption", "price", cumsum_price)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]
    # offpeak
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    # standard
    assert resultat[27]["sum_value"] == resultat[27]["value"] + 100
    assert resultat[27]["sum_price"] == resultat[27]["price"] + 50


@freeze_time("2023-3-1")
@pytest.mark.asyncio
async def test_tempo() -> None:
    """Test tempo pricings."""
    prices: dict[str, Any] = {
        "standard": {
            "blue": 0.2,
            "white": 0.3,
            "red": 3,
        },
        "offpeak": {
            "blue": 0.1,
            "white": 0.2,
            "red": 1.5,
        },
    }
    cumsum_value: dict[str, Any] = {"standard": 100, "offpeak": 1000}
    cumsum_price: dict[str, Any] = {"standard": 50, "offpeak": 75}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    modes = {"consumption": {"service": "consumption_load_curve"}}
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    api.set_cumsum("consumption", "value", cumsum_value)
    api.set_cumsum("consumption", "price", cumsum_price)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ), patch.object(myelectricaldatapy.Enedis, "async_get_tempo", return_value=TEMPO):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["tempo"] == "blue"
    assert resultat[0]["value"] == 1.079
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert api.tempo_day == "blue"

    # Check Daily -> compute not possible.
    dataset = DS_DAILY
    modes = {"production": {"service": "daily_production"}}
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ), patch.object(myelectricaldatapy.Enedis, "async_get_tempo", return_value=TEMPO):
        await api.async_update(modes=modes)
        resultat = api.stats["production"]
    assert resultat[0].get("tempo") is None


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_standard_offpeak_cumsum() -> None:
    """Test with offpeak and cumsum."""
    prices: dict[str, Any] = {"standard": {"price": 0.5}, "offpeak": {"price": 1}}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30
    modes = {"consumption": {"service": "consumption_load_curve"}}
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["value"] == 1.079

    # Test daily data , check ignore intervals.
    dataset = DS_DAILY
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_intervals("consumption", intervals)
    api.set_prices("consumption", prices)
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    assert resultat[0]["price"] == resultat[0]["value"] * 0.5


@pytest.mark.asyncio
async def test_start_date() -> None:
    """Test with start_date."""
    dataset = DS_DAILY
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    modes = {
        "consumption": {
            "service": "consumption_load_curve",
            "start": dt.strptime("2023-3-7", "%Y-%m-%d"),
        }
    }
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ), patch.object(
        myelectricaldatapy.Enedis, "async_valid_access", return_value=ACCESS
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    print(resultat)
    assert len(resultat) == 0

    dataset = DS_30
    modes = {
        "consumption": {
            "service": "consumption_load_curve",
            "start": dt.strptime("2023-3-7", "%Y-%m-%d"),
        }
    }
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=dataset
    ):
        await api.async_update(modes=modes)
        resultat = api.stats["consumption"]

    print(resultat)
    assert len(resultat) == 0
