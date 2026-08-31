"""Tests  Enedis api."""

from __future__ import annotations

from datetime import datetime as dt
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

import myelectricaldatapy
from myelectricaldatapy import (
    DETAIL_CONSUM,
    Enedis,
    EnedisByPDL,
    EnedisException,
    LimitReached,
)
from myelectricaldatapy.tz import LOCAL_TIMEZONE

from .consts import PDL, TOKEN


@freeze_time("2023-01-23")
async def test_subscription(mock_enedis: Mock, session) -> None:
    """Test subscription compute."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="hphc")
    assert api.has_offpeak_hours_subscription is True


@freeze_time("2023-01-23")
async def test_subscription_error(mock_enedis: Mock, session) -> None:
    """Test subscription msiconfiguration value."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="toto")
    assert api.has_standard_subscription is True


@freeze_time("2023-01-23")
async def test_address(mock_enedis: Mock, session) -> None:
    """Test subscription compute."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    await api.async_update()
    assert api.address.usage_point_id == "01234567890"


@freeze_time("2023-01-23")
async def test_contract(mock_enedis: Mock, session) -> None:
    """Test subscription compute."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    await api.async_update()
    assert api.contract.segment == "C5"


@freeze_time("2023-01-23")
async def test_offpeak_intervals(mock_enedis: Mock, session) -> None:
    """Test subscription compute."""
    api = Enedis(token=TOKEN, session=session)
    await api.async_get_contract(PDL)
    assert isinstance(api.offpeaks[0], tuple)

    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    await api.async_update()
    assert isinstance(api.offpeak_intervals[0], tuple)


@freeze_time("2023-01-23")
async def test_ecowatt(mock_enedis: Mock, session) -> None:
    """Test get ecowatt."""
    api = Enedis(token=TOKEN, session=session)
    resultat = await api.async_get_ecowatt()
    assert resultat["2023-01-22"].value == 1

    mypdl = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    mypdl.set_ecowatt_subscription(True)
    await mypdl.async_update()
    assert mypdl.ecowatt_day.message == "Pas d’alerte."


@pytest.mark.parametrize("mock_ecowatt", [True], indirect=True)
async def test_invalid_ecowatt(mock_enedis: Mock, session) -> None:
    """Test ecowatt."""

    api = Enedis(token=TOKEN, session=session)
    resultat = await api.async_get_ecowatt()
    assert resultat.get("2023-01-22") is None


@freeze_time("2023-3-3")
async def test_tempoday(mock_enedis: Mock, session) -> None:
    """Test get tempo day."""
    api = Enedis(token=TOKEN, session=session)
    resultat = await api.async_get_tempo()
    assert resultat["2023-03-01"] == "blue"

    mypdl = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="tempo")
    mypdl.set_data_fetch(DETAIL_CONSUM)
    await mypdl.async_update()
    resultat = mypdl.stats["consumption"]
    assert mypdl.tempo_day == "blue"


@freeze_time("2023-3-3")
async def test_tempo_infos(mock_enedis: Mock, session) -> None:
    """Test get tempo day."""
    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session, subscription="tempo")
    await api.async_update()
    assert api.tempo_days.red == 5
    assert api.tempo_prices.standard.blue == 0.1654
    assert api.tempo_prices.offpeak.blue == 0.1356


@freeze_time("2023-03-01")
async def test_check_offpeak(mock_enedis, session) -> None:
    """Test off-peak hour detection against the real contract's schedule.

    contract.json's offpeak_hours is "HC (1H30-8H00;12H30-14H00)". Patches
    the HTTP layer (not async_get_contract itself) so the real parsing in
    Enedis.async_get_contract runs and populates self.offpeaks.
    """

    api = Enedis(token=TOKEN, session=session)
    assert await api.async_has_offpeak(PDL) is True

    # 03:00 falls inside the 01:30-08:00 off-peak window
    assert (
        await api.async_check_offpeak(PDL, dt(2023, 3, 1, 3, 0, tzinfo=LOCAL_TIMEZONE))
        is True
    )
    # exactly on the lower bound is excluded (start, end] convention
    assert (
        await api.async_check_offpeak(PDL, dt(2023, 3, 1, 1, 30, tzinfo=LOCAL_TIMEZONE))
        is False
    )
    # exactly on the upper bound is included
    assert (
        await api.async_check_offpeak(PDL, dt(2023, 3, 1, 8, 0, tzinfo=LOCAL_TIMEZONE))
        is True
    )
    # standard hours, not off-peak
    assert (
        await api.async_check_offpeak(PDL, dt(2023, 3, 1, 10, 0, tzinfo=LOCAL_TIMEZONE))
        is False
    )
    # second window 12:30-14:00
    assert (
        await api.async_check_offpeak(PDL, dt(2023, 3, 1, 13, 0, tzinfo=LOCAL_TIMEZONE))
        is True
    )


async def test_valid_access(mock_enedis: Mock, session) -> None:  # pylint: disable=unused-argument
    """Test access."""
    api = Enedis(token=TOKEN, session=session)
    resultat = await api.async_valid_access(PDL)
    assert resultat.valid is True

    resultat = await api.async_has_access(PDL)
    assert resultat is True


@pytest.mark.parametrize("mock_access", [True], indirect=True)
async def test_invalid_access(mock_enedis: Mock, session) -> None:
    """Test access."""

    api = Enedis(token=TOKEN, session=session)
    resultat = await api.async_valid_access(PDL)
    assert resultat.quota_reached is True


async def test_fetch_data(mock_enedis, session) -> None:
    """Test fetch data."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "async_request", return_value=mock_enedis
    ):
        api = Enedis(token=TOKEN, session=session)
        resultat = await api.async_fetch_datas(
            service=DETAIL_CONSUM,
            pdl=PDL,
            start=dt.strptime("2022-12-30", "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE),
            end=dt.strptime("2022-12-31", "%Y-%m-%d").replace(tzinfo=LOCAL_TIMEZONE),
        )
        assert (
            resultat["meter_reading"]["interval_reading"]
            == mock_enedis["meter_reading"]["interval_reading"]
        )


async def test_force_refresh(
    mock_enedis: Mock,  # pylint: disable=unused-argument
    session,
) -> None:
    """Test refresh object."""

    api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
    api.set_data_fetch(DETAIL_CONSUM)
    await api.async_update()
    save_refresh = api.last_refresh
    await api.async_update()
    assert api.last_refresh == save_refresh
    await api.async_update(force_refresh=True)
    assert api.last_refresh != save_refresh


async def test_exception(
    mock_enedis: Mock,  # pylint: disable=unused-argument
    session,
) -> None:
    """Tests raise exception."""
    with patch.object(
        myelectricaldatapy.Enedis,
        "async_valid_access",
        side_effect=LimitReached(500, {"detail": "Limit reached"}),
    ):
        api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
        api.set_data_fetch(DETAIL_CONSUM)
        try:
            await api.async_update()
        except EnedisException:
            pass
        assert api.last_access is not None
        assert api.access is None

    with patch.object(
        myelectricaldatapy.Enedis,
        "async_get_details_consumption",
        side_effect=LimitReached(500, {"detail": "Limit reached"}),
    ):
        api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
        api.set_data_fetch(DETAIL_CONSUM)
        try:
            await api.async_update()
        except LimitReached:
            pass
        assert api.last_access is not None
        assert api.access.valid is True

    with patch.object(
        myelectricaldatapy.Enedis,
        "async_get_details_consumption",
        side_effect=EnedisException(500, {"detail": "Error"}),
    ):
        api = EnedisByPDL(pdl=PDL, token=TOKEN, session=session)
        api.set_data_fetch(DETAIL_CONSUM)
        api.set_data_fetch("daily_production")
        try:
            await api.async_update()
            await api.async_update()
        except EnedisException:
            pass
        assert api.last_access is not None
        assert api.access.valid is True
