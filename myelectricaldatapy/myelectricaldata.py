"""Class for Enedis Gateway (http://www.myelectricaldata.fr)."""
from __future__ import annotations

import logging
import re
from datetime import date
from datetime import datetime as dt
from datetime import timedelta
from typing import Any, Optional, Tuple

import pandas as pd

from .auth import TIMEOUT, EnedisAuth

_LOGGER = logging.getLogger(__name__)


class EnedisAnalytics:
    """Data analaytics."""

    def get_data_interval(
        self, jsdata: dict[str, Any], intervalls: list[Tuple[dt, dt]]
    ) -> Tuple[Any, Any]:
        """Group date from range time."""
        df = self._todataframe(jsdata)
        in_df = pd.DataFrame()
        for intervall in intervalls:
            df2 = df[
                (df.date.dt.time >= intervall[0].time())
                & (df.date.dt.time < intervall[1].time())
            ]
            in_df = pd.concat([in_df, df2], ignore_index=True)

        out_df = df[df.apply(tuple, 1).isin(in_df.apply(tuple, 1))]
        return self._tostring(in_df), self._tostring(out_df)

    def group_data(
        self, jsdata: dict[str, Any], field: str = "date", freq: str = "H"
    ) -> Any:
        """Group by date."""
        df = self._todataframe(jsdata)
        df.resample(freq, on=field).value.sum()
        return self._tostring(df)

    def set_price(self, jsdata: dict[str, Any], price: float) -> Any:
        """Set prince."""
        df = self._todataframe(jsdata)
        df["price"] = df["value"] * price
        return self._tostring(df)

    def _tostring(self, df: pd.DataFrame) -> Any:
        """Return dict with string date."""
        df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
        return df.to_dict()

    def _todataframe(self, jsdata: dict[str, Any]) -> pd.DataFrame:
        """Convert dict to dataframe."""
        df = pd.DataFrame(jsdata)
        df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d %H:%M:%S")
        df["value"] = pd.to_numeric(df["value"])
        return df


class EnedisByPDL:
    """Get data of pdl."""

    def __init__(
        self,
        token: str,
        pdl: str,
        session: Optional[Any] = None,
        timeout: int = TIMEOUT,
        production: bool = False,
        tempo: bool = False,
        ecowatt: bool = False,
    ) -> None:
        """Initialize."""
        self.auth = EnedisAuth(token, session, timeout)
        self.pdl = pdl
        self.b_production = production
        self.b_tempo = tempo
        self.b_ecowatt = ecowatt
        self.offpeaks: list[str] = []
        self.dt_offpeak: list[dt] = []
        self.power_datas: dict[str, Any] = {}
        self.last_refresh_date: date | None = None
        self.contract: dict[str, Any] = {}
        self.tempo_day: str | None = None
        self.ecowatt: dict[str, Any] = {}
        self.valid_access: dict[str, Any] = {}

    async def async_fetch_datas(
        self, service: str, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Retrieve date from service.

        service:    contracts, identity, contact, addresses,
                    daily_consumption_max_power,
                    daily_consumption, daily_production,
                    consumption_load_curve, production_load_curve
        """
        path_range = ""
        if start and end:
            start_date = start.strftime("%Y-%m-%d")
            end_date = end.strftime("%Y-%m-%d")
            path_range = f"/start/{start_date}/end/{end_date}"
        path = f"{service}/{self.pdl}{path_range}"
        return await self.auth.request(path=path)

    async def async_valid_access(self) -> Any:
        """Return valid access."""
        return await self.async_fetch_datas("valid_access")

    async def async_get_contract(self) -> Any:
        """Return all."""
        contract = {}
        contracts = await self.async_fetch_datas("contracts")
        usage_points = contracts.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == self.pdl:
                contract = usage_point.get("contracts", {})
                if offpeak_hours := contract.get("offpeak_hours"):
                    self.offpeaks = re.findall("(?:(\\w+)-(\\w+))+", offpeak_hours)
                    self.dt_offpeak = [
                        (  # type: ignore
                            dt.strptime(offpeak[0], "%HH%M"),
                            dt.strptime(offpeak[1], "%HH%M"),
                        )
                        for offpeak in self.offpeaks
                    ]
        return contract

    async def async_get_address(self) -> Any:
        """Return all."""
        address = {}
        addresses = await self.async_fetch_datas("addresses")
        usage_points = addresses.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == self.pdl:
                address = usage_point.get("usage_point")
        return address

    async def async_get_tempoday(self) -> Any:
        """Return Tempo Day."""
        day = dt.now().strftime("%Y-%m-%d")
        return await self.auth.request(path=f"rte/tempo/{day}/{day}")

    async def async_get_ecowatt(self) -> Any:
        """Return Ecowatt information."""
        day = dt.now().strftime("%Y-%m-%d")
        return await self.auth.request(path=f"rte/ecowatt/{day}/{day}")

    async def async_has_offpeak(self) -> bool:
        """Has offpeak hours."""
        if not self.offpeaks:
            await self.async_get_contract()
        return len(self.offpeaks) > 0

    async def async_check_offpeak(self, start: dt) -> bool:
        """Return offpeak status."""
        if await self.async_has_offpeak() is True:
            start_time = start.time()
            for range_time in self.offpeaks:
                starting = dt.strptime(range_time[0], "%HH%M").time()
                ending = dt.strptime(range_time[1], "%HH%M").time()
                if ending <= start_time > starting:
                    return True
        return False

    async def async_get_identity(self) -> Any:
        """Get identity."""
        return await self.async_fetch_datas("identity")

    async def async_get_daily_consumption(self, day: dt) -> Any:
        """Get daily consumption."""
        return await self.async_fetch_datas("daily_consumption", day, day)

    async def async_get_daily_production(self, day: dt) -> Any:
        """Get daily production."""
        return await self.async_fetch_datas("daily_production", day, day)

    async def async_get_details_consumption(self, start: dt, end: dt) -> Any:
        """Get consumption details. (max: 7 days)."""
        return await self.async_fetch_datas("consumption_load_curve", start, end)

    async def async_get_details_production(self, start: dt, end: dt) -> Any:
        """Get production details. (max: 7 days)."""
        return await self.async_fetch_datas("production_load_curve", start, end)

    async def async_get_max_power(self, start: dt, end: dt) -> Any:
        """Get consumption max power."""
        return await self.async_fetch_datas("daily_consumption_max_power", start, end)

    async def async_close(self) -> None:
        """Close session."""
        await self.auth.async_close()

    async def async_load(
        self,
        start: dt = dt.now() - timedelta(days=7),
        end: dt = dt.now(),
    ) -> None:
        """Retrieves production and consumption data over 7 days"""
        self.valid_access = await self.async_valid_access()
        c_datas = await self.async_get_details_consumption(start, end)
        self.power_datas.update(
            {"consumption": c_datas.get("meter_reading", {}).get("interval_reading")}
        )
        if self.b_production:
            p_datas = await self.async_get_details_production(start, end)
            self.power_datas.update(
                {"production": p_datas.get("meter_reading", {}).get("interval_reading")}
            )

        if self.last_refresh_date is None or dt.now().date() > self.last_refresh_date:
            await self.async_get_contract()
            if self.b_tempo:
                self.tempo_day = await self.async_get_tempoday()
            if self.b_ecowatt:
                self.ecowatt = await self.async_get_ecowatt()

        self.last_refresh_date = dt.now().date()

    async def async_refresh(self) -> None:
        """Refresh datas."""
        await self.async_load()
