"""Class for Enedis Gateway (http://www.myelectricaldata.fr)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from datetime import datetime as dt
from datetime import timedelta
from types import TracebackType
from typing import Any, Collection, Optional, Tuple

import pandas as pd

from .auth import TIMEOUT, EnedisAuth

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnedisAnalytics:
    """Data analaytics."""

    local_timezone = dt.now().astimezone().tzinfo

    def __init__(self, data: Collection[Collection[str]]) -> None:
        """Initialize Dataframe."""
        self.df = pd.DataFrame(data)

    def get_data_analytics(
        self,
        convertKwh: bool = False,
        convertUTC: bool = False,
        start_date: str | None = None,
        intervals: list[Tuple[str, str]] | None = None,
        groupby: bool = False,
        summary: bool = False,
        cum_value: dict[str, Any] = {},
        cum_price: dict[str, Any] = {},
        prices: dict[str, Any] | None = None,
        tempo: dict[str, str] | None = None,
    ) -> Any:
        """Convert datas to analyze."""
        step_hour = False
        if not self.df.empty:
            # Convert str to datetime
            self.df.date = pd.to_datetime(self.df.date, format="%Y-%m-%d %H:%M:%S")
            self.df.date = self.df.date.dt.tz_localize(self.local_timezone)

            if convertUTC:
                self.df.date = pd.to_datetime(
                    self.df.date, utc=True, format="%Y-%m-%d %H:%M:%S"
                )

            # Substract 1 minute at hour
            # because Pandas considers hour as the next hour while
            # for Enedis it is the hour before
            if "interval_length" in self.df:
                step_hour = True
                self.df.loc[
                    (
                        self.df.date.dt.minute
                        == dt.strptime("00:00:00", "%H:%M:%S").minute
                    ),
                    "date",
                ] = self.df.date - timedelta(minutes=1)

            if start_date:
                dt_start_date = pd.to_datetime(start_date, format="%Y-%m-%d %H:%M:%S")
                dt_start_date = dt_start_date.tz_localize(self.local_timezone)
                self.df = self.df[(self.df.date > dt_start_date)]

            self.df.index = self.df.date

            # Add mark
            self.df["notes"] = "standard"

        if self.df.empty:
            return self.df.to_dict(orient="records")

        if step_hour:
            self.df.interval_length = self.df.interval_length.transform(
                self._weighted_interval
            )
        else:
            self.df.interval_length = 1

        if convertKwh:
            self.df.value = (
                pd.to_numeric(self.df.value) / 1000 * self.df.interval_length
            )
        else:
            self.df.value = pd.to_numeric(self.df.value) * self.df.interval_length

        if intervals:
            self._get_data_interval(intervals)

        if groupby:
            freq = "H" if step_hour else "D"
            self.df = (
                self.df.groupby(["notes", pd.Grouper(key="date", freq=freq)])["value"]
                .sum()
                .reset_index()
            )

        if tempo:
            self._set_tempo_days(tempo)

        if prices:
            for mode, values in prices.items():
                if isinstance(values, dict):
                    for offset, price in values.items():
                        if tempo and offset in ["blue", "white", "red"]:
                            self.df.loc[
                                (self.df.notes == mode) & (self.df.tempo == offset),
                                "price",
                            ] = (
                                self.df.value * price
                            )
                        elif offset == "price":
                            self.df.loc[(self.df.notes == mode), "price"] = (
                                self.df.value * price
                            )

            if summary:
                for mode, sums in cum_price.items():
                    self.df.loc[(self.df.notes == mode), "sum_price"] = self.df[
                        (self.df.notes == mode)
                    ].price.cumsum() + sums.get("sum_price")

        if summary:
            for mode, sums in cum_value.items():
                self.df.loc[(self.df.notes == mode), "sum_value"] = self.df[
                    (self.df.notes == mode)
                ].value.cumsum() + sums.get("sum_value")

        return self.df.to_dict(orient="records")

    def _weighted_interval(self, interval: str) -> float | int:
        """Compute weighted."""
        if interval and len(rslt := re.findall("PT([0-9]{2})M", interval)) == 1:
            return int(rslt[0]) / 60
        return 1

    def _get_data_interval(self, intervalls: list[Tuple[str, str]]) -> pd.DataFrame:
        """Group date from range time."""
        for intervall in intervalls:
            # Convert str to datetime
            start = pd.to_datetime(intervall[0], format="%H:%M:%S").time()
            end = pd.to_datetime(intervall[1], format="%H:%M:%S").time()
            # Mark
            self.df.loc[
                (self.df.date.dt.time > start) & (self.df.date.dt.time <= end),
                "notes",
            ] = "offpeak"

        return self.df

    def _set_tempo_days(self, tempo: dict[str, str]) -> pd.DataFrame:
        """Add columns with tempo day."""
        for str_date, value in tempo.items():
            dt_date = pd.to_datetime(str_date, format="%Y-%m-%d")
            self.df.loc[(self.df.date.dt.date == dt_date.date()), "tempo"] = value

    def get_last_value(self, data: dict[str, Any], orderby: str, value: str) -> Any:
        """Return last value after order by."""
        df = pd.DataFrame(data)
        if not df.empty and value in df.columns:
            df = df.sort_values(by=orderby)
            return df[value].iloc[-1]  # pylint: disable=unsubscriptable-object


@dataclass
class Enedis:
    """Get data of pdl."""

    def __init__(
        self, token: str, session: Optional[Any] = None, timeout: int = TIMEOUT
    ) -> None:
        """Initialize."""
        self.auth = EnedisAuth(token, session, timeout)
        self.offpeaks: list[str] = []
        self.dt_offpeak: list[dt] = []
        self.last_access: date | None = None

    async def async_fetch_datas(
        self, service: str, pdl: str, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Retrieve date from service.

        service:    contracts, identity, contact, addresses,
                    daily_consumption_max_power,
                    daily_consumption, daily_production,
                    consumption_load_curve, production_load_curve
        """
        self.last_access = dt.now()
        path_range = ""
        if start and end:
            start_date = start.strftime("%Y-%m-%d")
            end_date = end.strftime("%Y-%m-%d")
            path_range = f"/start/{start_date}/end/{end_date}"
        path = f"{service}/{pdl}{path_range}"
        return await self.auth.request(path=path)

    async def async_valid_access(self, pdl: str) -> Any:
        """Return valid access."""
        return await self.async_fetch_datas("valid_access", pdl)

    async def async_has_access(self, pdl: str) -> bool:
        """Check valid access."""
        access = await self.async_valid_access(pdl)
        return access.get("valid", False) is True

    async def async_get_contract(self, pdl: str) -> Any:
        """Return contract information."""
        contract = {}
        contracts = await self.async_fetch_datas("contracts", pdl)
        usage_points = contracts.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == pdl:
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

    async def async_get_contracts(self, pdl: str) -> Any:
        """Return all contracts information."""
        return await self.async_fetch_datas("contracts", pdl)

    async def async_get_address(self, pdl: str) -> Any:
        """Return adress information."""
        address = {}
        addresses = await self.async_fetch_datas("addresses", pdl)
        usage_points = addresses.get("customer", {}).get("usage_points", "")
        for usage_point in usage_points:
            if usage_point.get("usage_point", {}).get("usage_point_id") == pdl:
                address = usage_point.get("usage_point")
        return address

    async def async_get_addresses(self, pdl: str) -> Any:
        """Return all adresses information."""
        return await self.async_fetch_datas("adresses", pdl)

    async def async_get_tempoday(
        self, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Return Tempo Day."""
        str_start = (
            start.strftime("%Y-%m-%d") if start else dt.now().strftime("%Y-%m-%d")
        )
        str_end = (
            end.strftime("%Y-%m-%d")
            if end
            else (dt.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        return await self.auth.request(path=f"rte/tempo/{str_start}/{str_end}")

    async def async_get_ecowatt(
        self, start: dt | None = None, end: dt | None = None
    ) -> Any:
        """Return Ecowatt information."""
        str_start = (
            start.strftime("%Y-%m-%d") if start else dt.now().strftime("%Y-%m-%d")
        )
        str_end = (
            end.strftime("%Y-%m-%d")
            if end
            else (dt.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        return await self.auth.request(path=f"rte/ecowatt/{str_start}/{str_end}")

    async def async_has_offpeak(self, pdl: str) -> bool:
        """Has offpeak hours."""
        if not self.offpeaks:
            await self.async_get_contract(pdl)
        return len(self.offpeaks) > 0

    async def async_check_offpeak(self, pdl: str, start: dt) -> bool:
        """Return offpeak status."""
        if await self.async_has_offpeak(pdl) is True:
            start_time = start.time()
            for range_time in self.offpeaks:
                starting = dt.strptime(range_time[0], "%HH%M").time()
                ending = dt.strptime(range_time[1], "%HH%M").time()
                if ending <= start_time > starting:
                    return True
        return False

    async def async_get_identity(self, pdl: str) -> Any:
        """Get identity."""
        return await self.async_fetch_datas("identity", pdl)

    async def async_get_daily_consumption(self, pdl: str, start: dt, end: dt) -> Any:
        """Get daily consumption."""
        return await self.async_fetch_datas("daily_consumption", pdl, start, end)

    async def async_get_daily_production(self, pdl: str, start: dt, end: dt) -> Any:
        """Get daily production."""
        return await self.async_fetch_datas("daily_production", pdl, start, end)

    async def async_get_details_consumption(self, pdl: str, start: dt, end: dt) -> Any:
        """Get consumption details. (max: 7 days)."""
        return await self.async_fetch_datas("consumption_load_curve", pdl, start, end)

    async def async_get_details_production(self, pdl: str, start: dt, end: dt) -> Any:
        """Get production details. (max: 7 days)."""
        return await self.async_fetch_datas("production_load_curve", pdl, start, end)

    async def async_get_max_power(self, pdl: str, start: dt, end: dt) -> Any:
        """Get consumption max power."""
        return await self.async_fetch_datas(
            "daily_consumption_max_power", pdl, start, end
        )

    async def __aenter__(self) -> Enedis:
        """Asynchronous enter."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Asynchronous exit."""
        await self.close()

    async def close(self) -> None:
        """Close the session."""
        await self.auth.async_close()


class EnedisByPDL:
    """PDL class."""

    def __init__(
        self,
        pdl: str,
        token: str,
        session: Optional[Any] = None,
        svc_consumption: str | None = None,
        svc_production: str | None = None,
        timeout: int = TIMEOUT,
    ) -> None:
        """Initialize."""
        self.pdl = pdl
        self._api: Enedis = Enedis(token, session, timeout)
        self.svc_consumption = svc_consumption
        self.svc_production = svc_production
        self._tempo_subs: bool = False
        self._off_subs: bool = False
        self._ecowatt_subs: bool = False
        self._maxpower_subs: bool = False
        self._intervals: list[Tuple[str, str]] = []
        self._access: dict[str, Any] = {}
        self._contract: dict[str, Any] = {}
        self._address: dict[str, Any] = {}
        self._tempo: dict[str, Any] = {}
        self._ecowatt: dict[str, Any] = {}
        self._max_power: dict[str, Any] = {}

        self._consumption: dict[str, Any] = {}
        self._production: dict[str, Any] = {}

        self._pricings: dict[str, Any] = {}

        self._sum: dict[str, Any] = {}
        self._sum_price: dict[str, Any] = {}

        self._connected: bool = False
        self._last_access: date | None = None
        self.start_date: str | None = None

    @property
    def is_connected(self) -> bool:
        """Connect state."""
        return self._access.get("valid", False) is True

    @property
    def contract(self) -> dict[str, Any]:
        """Contact."""
        return self._contract

    @property
    def address(self) -> dict[str, Any]:
        """Address."""
        return self._address

    @property
    def tempo(self) -> dict[str, Any]:
        """Tempo."""
        return self._tempo

    @property
    def ecowatt(self) -> dict[str, Any]:
        """ecowatt."""
        return self._ecowatt

    @property
    def max_power(self) -> dict[str, Any]:
        """max_power."""
        return self._max_power

    @property
    def tempoday(self) -> str | None:
        """Tempo day."""
        str_date = dt.now().strftime("%Y-%m-%d")
        return self._tempo.get(str_date)

    @property
    def intervals(self) -> list[Tuple[str, str]]:
        """Offpeak hours intervals."""
        return self._intervals

    @property
    def prod_prices(self) -> dict[str, dict[str, Any]]:
        """Production resel price."""
        return self._pricings.get("production", {})

    @property
    def consum_prices(self) -> dict[str, dict[str, Any]]:
        """Offpeak hours prices."""
        return self._pricings.get("consumption", {})

    @property
    def production_stats(self) -> list[dict[str, Any]]:
        """Production statistics."""
        resultat = []
        data = self._production.get("meter_reading", {}).get("interval_reading", {})
        analytics = EnedisAnalytics(data)
        resultat = analytics.get_data_analytics(
            convertKwh=True,
            convertUTC=False,
            intervals=self.intervals,
            groupby=True,
            summary=True,
            prices=self.prod_prices,
            cum_value=self._sum.get("production", {}),
            cum_price=self._sum_price.get("production", {}),
            start_date=self.start_date,
        )
        return resultat

    @property
    def consumption_stats(self) -> list[dict[str, Any]]:
        """Consumption statistics."""
        resultat = []
        data = self._consumption.get("meter_reading", {}).get("interval_reading", {})
        analytics = EnedisAnalytics(data)
        resultat = analytics.get_data_analytics(
            convertKwh=True,
            convertUTC=False,
            intervals=self.intervals,
            groupby=True,
            summary=True,
            prices=self.consum_prices,
            cum_value=self._sum.get("consumption", {}),
            cum_price=self._sum_price.get("consumption", {}),
            tempo=self.tempo,
            start_date=self.start_date,
        )
        return resultat

    async def async_update(
        self,
        start: dt | None = None,
        end: dt | None = None,
        start_date: str | None = None,
        force_refresh: bool = False,
    ) -> None:
        """Update data.

        If the update succeeds, the next one can only be done on the next day
        at least that force_refresh is true
        """
        self._access = await self._api.async_valid_access(self.pdl)
        if (
            self._last_access is not None
            and self._last_access > dt.now().date()
            and force_refresh is False
        ):
            return

        start = start if start else dt.now() - timedelta(days=730)
        end = end if end else dt.now()
        self.start_date = start_date

        self._contract = await self._api.async_get_contract(self.pdl)
        self._address = await self._api.async_get_address(self.pdl)
        if self._ecowatt_subs:
            self._ecowatt = await self._api.async_get_ecowatt(start, end)
        if self._max_power:
            self._max_power = await self._api.async_get_max_power(self.pdl, start, end)

        if self.svc_production == "daily_production":
            start = start if start else dt.now() - timedelta(days=730)
            self._production = await self._api.async_get_daily_production(
                self.pdl, start, end
            )
        elif self.svc_production == "production_load_curve":
            start = start if start else dt.now() - timedelta(days=7)
            self._production = await self._api.async_get_details_production(
                self.pdl, start, end
            )

        if self.svc_consumption == "daily_consumption":
            start = start if start else dt.now() - timedelta(days=730)
            self._consumption = await self._api.async_get_daily_consumption(
                self.pdl, start, end
            )
        elif self.svc_consumption == "consumption_load_curve":
            start = start if start else dt.now() - timedelta(days=7)
            self._consumption = await self._api.async_get_details_consumption(
                self.pdl, start, end
            )
            if self._tempo_subs:
                self._tempo = await self._api.async_get_tempoday(start, end)

        self._last_access = dt.now().date()

    def tempo_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Tempo Subscription."""
        self._off_subs = False
        self._tempo_subs = activate is True

    def offpeak_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Offpeak Hours Subscription."""
        self._tempo_subs = False
        self._off_subs = activate is True

    def ecowatt_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Ecowatt Subscription."""
        self._ecowatt_subs = activate is True

    def maxpower_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Max power Subscription."""
        self._maxpower_subs = activate is True

    def set_intervals(self, intervals: list[Tuple[str, str]]) -> None:
        """Set intervals."""
        if isinstance(intervals, list):
            self._intervals = intervals

    def set_prices(
        self,
        mode: str,
        prices: dict[str, Any],
    ) -> None:
        """Set intervals."""
        pricings = {}
        if std := prices.get("standard"):
            pricings["standard"] = {k: v for k, v in std.items() if v is not None}
        if off := prices.get("offpeak"):
            pricings["offpeak"] = {k: v for k, v in off.items() if v is not None}

        if off and "blue" not in off:
            self.offpeak_subscription(True)
        if off and "blue" in off:
            self.tempo_subscription(True)

        self._pricings.update({mode: prices})

    def set_cumsum_value(self, mode: str, cum_value: dict[str, Any]) -> None:
        """Set cumulative summary for consumption."""
        cumsums = {}
        if std := cum_value.get("standard"):
            cumsums["standard"] = {k: v for k, v in std.items() if v is not None}
        if off := cum_value.get("offpeak"):
            cumsums["offpeak"] = {k: v for k, v in off.items() if v is not None}

        self._sum.update({mode: cumsums})

    def set_cumsum_price(self, mode: str, cum_price: dict[str, Any]) -> None:
        """Set cumulative summary for consumption."""
        cumsums = {}
        if std := cum_price.get("standard"):
            cumsums["standard"] = {k: v for k, v in std.items() if v is not None}
        if off := cum_price.get("offpeak"):
            cumsums["offpeak"] = {k: v for k, v in off.items() if v is not None}

        self._sum_price.update({mode: cumsums})
