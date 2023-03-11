from __future__ import annotations

import pytest

from myelectricaldatapy import EnedisAnalytics

from .consts import DATASET_30 as DS_30
from .consts import DATASET_DAILY as DS_DAILY
from .consts import DATASET_DAILY_COMPARE as DS_COMPARE

PDL = "012345"
TOKEN = "xxxxxxxxxxxxx"


@pytest.mark.asyncio
async def test_hours_analytics() -> None:
    """Test analytics compute."""
    dataset = DS_30["meter_reading"]["interval_reading"]
    cumsums = {
        "standard": {"sum_value": 1000, "sum_price": 0},
        "offpeak": {"sum_value": 1000, "sum_price": 0},
    }
    prices = [{"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}]
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="H",
        groupby=True,
        summary=True,
        cumsums=cumsums,
        prices=prices,
    )
    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 0.618
    assert resultat[0].get("sum_value") is not None
    assert resultat[0].get("sum_price") is not None
    print(resultat)

    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="H",
        groupby=True,
        prices=prices,
    )
    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 0.618
    assert resultat[2]["price"] == 0.55152
    assert resultat[0].get("sum_value") is None
    print(resultat)

    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=True,
        intervals=intervals,
        freq="H",
        groupby=True,
        prices=prices,
    )
    print(resultat)

    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="H",
        groupby=True,
    )
    assert resultat[27]["value"] == 0.672
    assert resultat[28]["value"] == 0.624
    print(resultat)

    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="D",
        groupby=True,
        summary=True,
        cumsums=cumsums,
        prices=prices,
    )
    assert resultat[0]["value"] == 33.951
    assert resultat[3]["value"] == 43.608
    print(resultat)


@pytest.mark.asyncio
async def test_daily_analytics() -> None:
    prices = [{"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}]
    dataset = DS_30["meter_reading"]["interval_reading"]
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_DAILY["meter_reading"]["interval_reading"]
    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="D",
        groupby=True,
        summary=True,
        prices=prices,
    )
    assert resultat[359]["value"] == 68.68
    print(resultat)


@pytest.mark.asyncio
async def test_compare_analytics() -> None:
    prices = [{"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}]
    cumsums = {
        "standard": {"sum_value": 0, "sum_price": 0},
        "offpeak": {"sum_value": 0, "sum_price": 0},
    }
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30["meter_reading"]["interval_reading"]
    analytics = EnedisAnalytics(dataset)
    resultat1 = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="D",
        groupby=True,
        summary=True,
        cumsums=cumsums,
        prices=prices,
        start_date="2023-02-28",
    )
    print(resultat1)
    sum_value = 0
    for rslt in resultat1:
        sum_value = sum_value + rslt["value"]

    sum_value_1 = resultat1[2]["sum_value"] + resultat1[5]["sum_value"]
    assert sum_value == sum_value_1
    dataset = DS_COMPARE["meter_reading"]["interval_reading"]
    analytics = EnedisAnalytics(dataset)
    resultat2 = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="D",
        groupby=True,
        summary=True,
        cumsums=cumsums,
        prices=prices,
        start_date="2023-02-28",
    )
    assert sum_value == resultat2[2]["sum_value"]
    print(resultat2)


@pytest.mark.asyncio
async def test_cumsums_analytics() -> None:
    prices = [{"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}]
    cumsums = {
        "standard": {"sum_value": 100, "sum_price": 50},
        "offpeak": {"sum_value": 1000, "sum_price": 75},
    }
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30["meter_reading"]["interval_reading"]
    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="D",
        groupby=True,
        summary=True,
        cumsums=cumsums,
        prices=prices,
        start_date="2023-02-28",
    )
    # offpeak
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    # standard
    assert resultat[3]["sum_value"] == resultat[3]["value"] + 100
    assert resultat[3]["sum_price"] == resultat[3]["price"] + 50


@pytest.mark.asyncio
async def test_tempo_analytics() -> None:
    prices = [
        {
            "standard": {"price": 0.2, "date": "2023-03-01"},
            "offpeak": {"price": 0.3, "date": "2023-03-01"},
        },
        {
            "standard": {"price": 0.1, "date": "2023-03-02"},
            "offpeak": {"price": 0.2, "date": "2023-03-02"},
        },
        {
            "standard": {"price": 0.2, "date": "2023-03-03"},
            "offpeak": {"price": 0.3, "date": "2023-03-03"},
        },
    ]
    cumsums = {
        "standard": {"sum_value": 100, "sum_price": 50},
        "offpeak": {"sum_value": 1000, "sum_price": 75},
    }
    intervals = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
    dataset = DS_30["meter_reading"]["interval_reading"]
    analytics = EnedisAnalytics(dataset)
    resultat = analytics.get_data_analytics(
        convertKwh=True,
        convertUTC=False,
        intervals=intervals,
        freq="D",
        groupby=True,
        summary=True,
        cumsums=cumsums,
        prices=prices,
        start_date="2023-02-28",
    )
    print(resultat)
