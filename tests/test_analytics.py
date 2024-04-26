"""Tests analytics."""

from __future__ import annotations

from datetime import datetime as dt
from typing import Any
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

import myelectricaldatapy
from myelectricaldatapy import EnedisByPDL

from .consts import DATASET_DAILY_COMPARE, PDL, TOKEN


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_compute(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
    """Test standard."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("consumption_load_curve")
    await api.async_update()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert resultat[0]["value"] == 1.296

    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("daily_consumption")
    await api.async_update()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert resultat[0]["value"] == 42.045


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_without_offpeak(
    mock_enedis: Mock,
) -> None:  # pylint: disable=unused-argument
    """Test without offpeak , with price."""
    await mock_enedis()
    prices: dict[str, Any] = {"standard": {"price": 0.17}}
    # Test standard price
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("consumption_load_curve", prices=prices)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 0.22

    api.set_collects("daily_consumption", prices=prices)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 7.15


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_with_offpeak(
    mock_enedis: Mock,  # pylint: disable=unused-argument
) -> None:
    """Test without offpeak , with price."""
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("consumption_load_curve", prices=prices, intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 1.079
    assert resultat[0].get("sum_value") is not None
    assert resultat[0].get("sum_price") is not None
    print(resultat)

    # Without cums
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("consumption_load_curve", prices=prices, intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 1.079
    assert round(resultat[2]["price"], 3) == 0.833
    assert resultat[0].get("sum_value") == 1.079
    print(resultat)

    # Without price
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("consumption_load_curve", intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert resultat[27]["value"] == 1.296
    assert resultat[28]["value"] == 0.618
    print(resultat)

    # Daily
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("daily_consumption", prices=prices, intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["value"] == 42.045
    print(resultat)


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_daily_with_offpeak(
    mock_enedis: Mock,  # pylint: disable=unused-argument
) -> None:
    """Test daily with offpeak."""
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("daily_consumption", prices=prices, intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert resultat[359]["value"] == 68.68
    print(resultat)


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_compare(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
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
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects(
        "consumption_load_curve",
        prices=prices,
        intervals=intervals,
        cum_value=cumsum_value,
        cum_price=cumsum_price,
    )
    await api.async_update()
    resultat1 = api.stats["consumption"]

    print(resultat1)
    sum_value = 0
    for rslt in resultat1:
        sum_value += rslt["value"]
    sum_value_1 = resultat1[26]["sum_value"] + resultat1[77]["sum_value"]
    assert round(sum_value, 3) == round(sum_value_1, 3)

    with patch.object(
        myelectricaldatapy.Enedis,
        "async_get_daily_consumption",
        return_value=DATASET_DAILY_COMPARE,
    ):
        api.set_collects(
            "daily_consumption",
            prices=prices,
            intervals=intervals,
            cum_value=cumsum_value,
            cum_price=cumsum_price,
        )
        await api.async_update(force_refresh=True)
        resultat2 = api.stats["consumption"]
    assert round(sum_value, 3) == resultat2[2]["sum_value"]
    print(resultat2)


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_cumsums(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
    """Test cumulative summary."""
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    cumsum_value: dict[str, Any] = {"standard": 100, "offpeak": 1000}
    cumsum_price: dict[str, Any] = {"standard": 50, "offpeak": 75}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects(
        "consumption_load_curve",
        start=dt.strptime("2023-03-01", "%Y-%m-%d"),
        end=dt.strptime("2023-03-08", "%Y-%m-%d"),
        prices=prices,
        intervals=intervals,
        cum_value=cumsum_value,
        cum_price=cumsum_price,
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    # offpeak
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    # standard
    assert resultat[27]["sum_value"] == resultat[27]["value"] + 100
    assert resultat[27]["sum_price"] == resultat[27]["price"] + 50


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_extra_date(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
    """Test cumulative summary."""
    prices: dict[str, Any] = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects(
        "consumption_load_curve",
        start=dt.strptime("2023-03-01", "%Y-%m-%d"),
        end=dt.strptime("2023-03-28", "%Y-%m-%d"),
        prices=prices,
        intervals=intervals,
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    # offpeak
    assert resultat[0]["sum_value"] is not None
    # standard
    assert resultat[27]["sum_value"] is not None


@freeze_time("2023-3-1")
@pytest.mark.asyncio
async def test_tempo(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
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
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects(
        "consumption_load_curve",
        prices=prices,
        intervals=intervals,
        cum_value=cumsum_value,
        cum_price=cumsum_price,
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["tempo"] == "blue"
    assert resultat[0]["value"] == 1.079
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert api.tempo_day == "blue"

    # Check Daily -> compute not possible.
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("daily_production", prices=prices, intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats.get("production")
    assert resultat[0].get("tempo") is None


@freeze_time("2023-03-01")
@pytest.mark.asyncio
async def test_standard_offpeak_cumsum(
    mock_enedis: Mock,  # pylint: disable=unused-argument
) -> None:
    """Test with offpeak and cumsum."""
    prices: dict[str, Any] = {"standard": {"price": 0.5}, "offpeak": {"price": 1}}
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("consumption_load_curve", prices=prices, intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert resultat[0]["value"] == 1.079

    # Test daily data , check ignore intervals.
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("daily_consumption", prices=prices, intervals=intervals)
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert resultat[0]["price"] == resultat[0]["value"] * 0.5


@pytest.mark.asyncio
async def test_start_date(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
    """Test with start_date."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects(
        "consumption_load_curve", start=dt.strptime("2023-3-7", "%Y-%m-%d")
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert len(resultat) == 0

    api.set_collects(
        "consumption_load_curve", start=dt.strptime("2023-3-7", "%Y-%m-%d")
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert len(resultat) == 0


@freeze_time("2023-3-1")
@pytest.mark.asyncio
async def test_twice_call(
    mock_enedis: Mock,  # pylint: disable=unused-argument
) -> None:
    """Tests raise exception."""
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    api = EnedisByPDL(pdl=PDL, token=TOKEN)
    api.set_collects("consumption_load_curve", intervals=intervals)
    api.set_collects("daily_production")
    await api.async_update()
    assert len(api.stats["consumption"]) != 0
    assert len(api.stats["production"]) != 0
    assert api.stats["consumption"][0]["notes"] == "offpeak"
    assert api.stats["production"][0]["notes"] == "standard"
    await api.async_update()
    assert api.last_access is not None
