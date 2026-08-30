"""Tests analytics."""

from __future__ import annotations

from datetime import datetime as dt
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

from myelectricaldatapy import (
    DAILY_CONSUM,
    DAILY_PROD,
    DETAIL_CONSUM,
    EnedisByPDL,
    LimitReached,
)
from myelectricaldatapy.tz import LOCAL_TIMEZONE

from .consts import PDL, TOKEN

STANDARD_PRICE = {"standard": {"price": 0.17}}
OFFPEAK_INTERVALS = [("01:30:00", "08:00:00"), ("12:30:00", "14:00:00")]
HPHC_PRICE = {"standard": {"price": 0.17}, "offpeak": {"price": 0.18}}
CUMSUM_VALUE_0 = {"standard": {"sum_value": 0}, "offpeak": {"sum_value": 0}}
CUMSUM_PRICE_0 = {"standard": {"sum_price": 0}, "offpeak": {"sum_price": 0}}
CUMSUM_VALUE = {"standard": 100, "offpeak": 1000}
CUMSUM_PRICE = {"standard": 50, "offpeak": 75}
TEMPO_PRICE = {
    "standard": {"blue": 0.2, "white": 0.3, "red": 3},
    "offpeak": {"blue": 0.1, "white": 0.2, "red": 1.5},
}
START_D = dt.strptime("2023-03-01", "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE)
END_D = dt.strptime("2023-03-08", "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE)


@freeze_time("2023-03-01")
async def test_standard_daily_consumption(mock_enedis: Mock, session) -> None:  # pylint: disable=unused-argument
    """Test standard consumption."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    api.set_data_fetch(DAILY_CONSUM)
    await api.async_update()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert resultat[0]["value"] == 42.045
    assert resultat[0].get("price") is None


@freeze_time("2023-03-01")
async def test_standard_daily_consumption_with_prices(
    mock_enedis: Mock, session
) -> None:
    """Test standard with price."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    api.set_data_fetch(DAILY_CONSUM, prices=STANDARD_PRICE)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 7.15


@freeze_time("2023-03-01")
async def test_standard_detail_consumption(mock_enedis: Mock, session) -> None:
    """Test standard with price."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    api.set_data_fetch(DETAIL_CONSUM)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert resultat[0].get("price") is None


@freeze_time("2023-03-01")
async def test_standard_detail_consumption_with_prices(
    mock_enedis: Mock, session
) -> None:
    """Test standard with price."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    api.set_data_fetch(DETAIL_CONSUM, prices=STANDARD_PRICE)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "standard"
    assert round(resultat[0]["price"], 2) == 0.22


@freeze_time("2023-03-01")
async def test_hphc_detail_consumption(mock_enedis: Mock, session) -> None:
    # Without price
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    api.set_data_fetch(DETAIL_CONSUM, intervals=OFFPEAK_INTERVALS)
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert resultat[27]["value"] == 1.296
    assert resultat[28]["value"] == 0.618


@freeze_time("2023-03-01")
async def test_hphc_detail_consumption_with_prices(mock_enedis: Mock, session) -> None:
    """Test without offpeak , with price."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    api.set_data_fetch(DETAIL_CONSUM, prices=HPHC_PRICE, intervals=OFFPEAK_INTERVALS)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["notes"] == "offpeak"
    assert resultat[0]["value"] == 1.079
    assert resultat[0].get("sum_value") == 1.079
    assert round(resultat[2]["price"], 3) == 0.833


@freeze_time("2023-03-01")
async def test_hphc_daily_consumption(mock_enedis: Mock, session) -> None:
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    api.set_data_fetch(DAILY_CONSUM, intervals=OFFPEAK_INTERVALS)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["value"] == 42.045
    assert resultat[359]["value"] == 68.68


@freeze_time("2023-03-01")
async def test_hphc_daily_consumption_with_prices(mock_enedis: Mock, session) -> None:
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    api.set_data_fetch(DAILY_CONSUM, prices=HPHC_PRICE, intervals=OFFPEAK_INTERVALS)
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["value"] == 42.045
    assert resultat[359]["value"] == 68.68


@freeze_time("2023-03-01")
async def test_hphc_check_summary_value(mock_enedis: Mock, session) -> None:
    """Test compare summary detail with summary daily.

    Summary of 01/03/2003 at 03/203/2023
    """

    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    api.set_data_fetch(
        DETAIL_CONSUM,
        prices=HPHC_PRICE,
        intervals=OFFPEAK_INTERVALS,
        cum_value=CUMSUM_VALUE_0,
        cum_price=CUMSUM_PRICE_0,
    )
    await api.async_update()
    resultat1 = api.stats["consumption"]

    sum_value = 0
    for rslt in resultat1:
        print(rslt)
        sum_value += rslt["value"]
        print(sum_value)
    sum_value_1 = resultat1[26]["sum_value"] + resultat1[77]["sum_value"]
    assert round(sum_value, 3) == round(sum_value_1, 3)

    api.set_data_fetch(
        DAILY_CONSUM,
        prices=HPHC_PRICE,
        intervals=OFFPEAK_INTERVALS,
        cum_value=CUMSUM_VALUE_0,
        cum_price=CUMSUM_PRICE_0,
    )
    await api.async_update(force_refresh=True)
    resultat2 = api.stats["consumption"]
    assert (
        round(sum_value, 3)
        == resultat2[358]["value"] + resultat2[359]["value"] + resultat2[360]["value"]
    )


@freeze_time("2023-03-01")
async def test_hphc_cumsums(mock_enedis: Mock, session) -> None:
    """Test cumulative summary."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    api.set_data_fetch(
        DETAIL_CONSUM,
        start=START_D,
        end=END_D,
        prices=HPHC_PRICE,
        intervals=OFFPEAK_INTERVALS,
        cum_value=CUMSUM_VALUE,
        cum_price=CUMSUM_PRICE,
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
async def test_hphc_cumsum_range(mock_enedis: Mock, session) -> None:  # pylint: disable=unused-argument
    """Test cumulative summary."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    api.set_data_fetch(
        DETAIL_CONSUM,
        start=START_D,
        end=END_D,
        prices=HPHC_PRICE,
        intervals=OFFPEAK_INTERVALS,
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    # offpeak
    assert resultat[0]["sum_value"] is not None
    # standard
    assert resultat[27]["sum_value"] is not None

    api.set_data_fetch(
        DETAIL_CONSUM,
        start=dt.strptime("2023-03-01", "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE),
        end=dt.strptime("2023-03-28", "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE),
        prices=HPHC_PRICE,
        intervals=OFFPEAK_INTERVALS,
    )
    with patch(
        "myelectricaldatapy.Enedis.async_fetch_datas",
        side_effect=[mock_enedis, LimitReached(500, {"detail": "Limit reached"})],
    ):
        await api.async_update_collects()
        resultat = api.stats["consumption"]
        assert resultat[0]["sum_value"] is not None


@freeze_time("2023-3-1")
async def test_tempo_detail_comsumption(mock_enedis: Mock, session) -> None:
    """Test tempo pricings."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="tempo")
    api.set_data_fetch(
        DETAIL_CONSUM,
        intervals=OFFPEAK_INTERVALS,
        cum_value=CUMSUM_VALUE,
        cum_price=CUMSUM_PRICE,
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["tempo"] == "blue"
    assert resultat[0]["value"] == 1.079
    assert resultat[0].get("sum_price") is None
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert api.tempo_day == "blue"


@freeze_time("2023-3-1")
async def test_tempo_detail_comsumption_with_price(mock_enedis: Mock, session) -> None:
    """Test tempo pricings."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="tempo")
    api.set_data_fetch(
        DETAIL_CONSUM,
        prices=TEMPO_PRICE,
        intervals=OFFPEAK_INTERVALS,
        cum_value=CUMSUM_VALUE,
        cum_price=CUMSUM_PRICE,
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]

    assert resultat[0]["tempo"] == "blue"
    assert resultat[0]["value"] == 1.079
    assert resultat[0]["sum_price"] == resultat[0]["price"] + 75
    assert resultat[0]["sum_value"] == resultat[0]["value"] + 1000
    assert api.tempo_day == "blue"


@freeze_time("2023-3-1")
async def test_production(mock_enedis: Mock, session) -> None:
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="tempo")
    api.set_data_fetch(DAILY_PROD, intervals=OFFPEAK_INTERVALS)
    await api.async_update_collects()
    resultat = api.stats.get("production")
    assert resultat[0].get("tempo") is None
    assert resultat[0].get("price") is None
    assert resultat[1].get("value") == 32.464
    assert resultat[1].get("sum_value") == 74.509


@freeze_time("2023-3-1")
async def test_production_with_price(mock_enedis: Mock, session) -> None:
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="tempo")
    api.set_data_fetch(DAILY_PROD, prices=STANDARD_PRICE, intervals=OFFPEAK_INTERVALS)
    await api.async_update_collects()
    resultat = api.stats.get("production")
    assert round(resultat[1].get("price", 0), 3) == 5.519
    assert resultat[1].get("value") == 32.464
    assert resultat[1].get("sum_value") == 74.509
    assert round(resultat[1].get("sum_price", 0), 3) == 12.667


@pytest.mark.asyncio
async def test_start_date(mock_enedis: Mock, session) -> None:
    """Test with start_date."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    api.set_data_fetch(
        DETAIL_CONSUM,
        start=dt.strptime("2023-3-7", "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE),
    )
    await api.async_update_collects()
    resultat = api.stats["consumption"]
    assert len(resultat) == 0


@freeze_time("2023-3-1")
async def test_twice_call(
    mock_enedis: Mock,  # pylint: disable=unused-argument
    session,
) -> None:
    """Tests raise exception."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    api.set_data_fetch(DETAIL_CONSUM, intervals=OFFPEAK_INTERVALS)
    api.set_data_fetch(DAILY_PROD)
    await api.async_update()
    assert len(api.stats["consumption"]) != 0
    assert len(api.stats["production"]) != 0
    assert api.stats["consumption"][0]["notes"] == "offpeak"
    assert api.stats["production"][0]["notes"] == "standard"
    await api.async_update()
    assert api.last_access is not None
