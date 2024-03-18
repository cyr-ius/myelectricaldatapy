"""Tests  Enedis api."""

from __future__ import annotations

from datetime import datetime as dt
from unittest.mock import Mock, patch

import pytest
from freezegun import freeze_time

import myelectricaldatapy
from myelectricaldatapy import Enedis, EnedisByPDL, EnedisException, LimitReached

from .consts import DATASET_30, INVALID_ACCESS, INVALID_ECOWATT, PDL, TOKEN


@freeze_time("2023-01-23")
@pytest.mark.asyncio
async def test_ecowatt(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
    """Test get ecowatt."""
    api = Enedis(token=TOKEN)
    resultat = await api.async_get_ecowatt()
    assert resultat["2023-01-22"]["value"] == 1

    mypdl = EnedisByPDL(pdl=PDL, token=TOKEN)
    mypdl.ecowatt_subscription(True)
    await mypdl.async_update()
    assert mypdl.ecowatt_day["message"] == "Pas d’alerte."

    with patch.object(
        myelectricaldatapy.Enedis, "async_get_ecowatt", return_value=INVALID_ECOWATT
    ):
        resultat = await api.async_get_ecowatt()
        assert resultat.get("2023-01-22") is None


@freeze_time("2023-3-3")
@pytest.mark.asyncio
async def test_tempoday(mock_enedis: Mock) -> None:  # pylint: disable=unused-argument
    """Test get tempo day."""
    api = Enedis(token=TOKEN)
    resultat = await api.async_get_tempo()
    assert resultat["2023-3-1"] == "blue"

    mypdl = EnedisByPDL(pdl=PDL, token=TOKEN)
    mypdl.set_collects("consumption_load_curve")
    mypdl.tempo_subscription(True)
    await mypdl.async_update()
    resultat = mypdl.stats["consumption"]
    assert mypdl.tempo_day == "blue"


@pytest.mark.asyncio
async def test_valid_access(
    mock_enedis: Mock,  # pylint: disable=unused-argument
) -> None:
    """Test access."""
    api = Enedis(token=TOKEN)
    resultat = await api.async_valid_access(PDL)
    assert resultat["valid"] is True

    resultat = await api.async_has_access(PDL)
    assert resultat is True

    with patch.object(
        myelectricaldatapy.Enedis, "async_valid_access", return_value=INVALID_ACCESS
    ):
        api = Enedis(token=TOKEN)
        resultat = await api.async_valid_access(PDL)
        assert resultat["quota_reached"] is True


@pytest.mark.asyncio
async def test_fetch_data() -> None:
    """Test fetch data."""
    with patch.object(
        myelectricaldatapy.auth.EnedisAuth, "request", return_value=DATASET_30
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
            == DATASET_30["meter_reading"]["interval_reading"]  # noqa
        )


@pytest.mark.asyncio
async def test_force_refresh(
    mock_enedis: Mock,  # pylint: disable=unused-argument
) -> None:
    """Test refresh object."""
    last_call = dt.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
    access = {
        "valid": True,
        "quota_reached": False,
        "last_call": last_call,
    }
    with patch.object(
        myelectricaldatapy.Enedis, "async_valid_access", return_value=access
    ):
        api = EnedisByPDL(pdl=PDL, token=TOKEN)
        api.set_collects("consumption_load_curve")
        await api.async_update()
        save_refresh = api.last_refresh
        await api.async_update()
        assert api.last_refresh == save_refresh
        await api.async_update(force_refresh=True)
        assert api.last_refresh != save_refresh


@pytest.mark.asyncio
async def test_exception(
    mock_enedis: Mock,  # pylint: disable=unused-argument
) -> None:
    """Tests raise exception."""
    with patch.object(
        myelectricaldatapy.Enedis,
        "async_valid_access",
        side_effect=LimitReached(500, {"detail": "Limit reached"}),
    ):
        api = EnedisByPDL(pdl=PDL, token=TOKEN)
        api.set_collects("consumption_load_curve")
        try:
            await api.async_update()
        except EnedisException:
            pass
        assert api.last_access is not None
        assert len(api.access) == 0

    with patch.object(
        myelectricaldatapy.Enedis,
        "async_get_details_consumption",
        side_effect=LimitReached(500, {"detail": "Limit reached"}),
    ):
        api = EnedisByPDL(pdl=PDL, token=TOKEN)
        api.set_collects("consumption_load_curve")
        try:
            await api.async_update()
        except LimitReached:
            pass
        assert api.last_access is not None
        assert api.access["valid"] is True

    with patch.object(
        myelectricaldatapy.Enedis,
        "async_get_details_consumption",
        side_effect=EnedisException(500, {"detail": "Error"}),
    ):
        api = EnedisByPDL(pdl=PDL, token=TOKEN)
        api.set_collects("consumption_load_curve")
        api.set_collects("daily_production")
        try:
            await api.async_update()
            await api.async_update()
        except EnedisException:
            pass
        assert api.last_access is not None
        assert api.access["valid"] is True
