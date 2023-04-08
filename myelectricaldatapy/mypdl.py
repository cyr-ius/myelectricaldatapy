"""Class for my PDL."""
from __future__ import annotations

import logging
from datetime import date
from datetime import datetime as dt
from datetime import timedelta
from typing import Any, Callable, Tuple

import voluptuous as vol

from myelectricaldatapy import Enedis

from .analytics import EnedisAnalytics
from .const import (
    ATTR_CUM_PRICE,
    ATTR_CUM_VALUE,
    ATTR_END,
    ATTR_INTERVALS,
    ATTR_OFFPEAK,
    ATTR_PRICES,
    ATTR_SERVICE,
    ATTR_STANDARD,
    ATTR_START,
    CONSUMPTION,
    DAILY_CONSUM,
    DAILY_PROD,
    DETAIL_CONSUM,
    DETAIL_PROD,
    PRODUCTION,
    TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

MODES_SCH = vol.Schema(
    {
        vol.Optional(CONSUMPTION): {
            vol.Required(ATTR_SERVICE): str,
            vol.Optional(ATTR_START): dt,
            vol.Optional(ATTR_END): dt,
        },
        vol.Optional(PRODUCTION): {
            vol.Required(ATTR_SERVICE): str,
            vol.Optional(ATTR_START): dt,
            vol.Optional(ATTR_END): dt,
        },
    }
)

PRICE_SCH = vol.Schema(
    {
        vol.Required(ATTR_STANDARD): {
            vol.Required("price"): vol.Any(int, float),
        },
        vol.Optional(ATTR_OFFPEAK): {
            vol.Required("price"): vol.Any(int, float),
        },
    }
)

PRICE_TEMPO_SCH = vol.Schema(
    {
        vol.Required(ATTR_STANDARD): {
            vol.Required("blue"): vol.Any(int, float),
            vol.Required("white"): vol.Any(int, float),
            vol.Required("red"): vol.Any(int, float),
        },
        vol.Optional(ATTR_OFFPEAK): {
            vol.Required("blue"): vol.Any(int, float),
            vol.Required("white"): vol.Any(int, float),
            vol.Required("red"): vol.Any(int, float),
        },
    }
)

CUM_SCH = vol.Schema(
    {
        vol.Required(ATTR_STANDARD): vol.Any(int, float),
        vol.Optional(ATTR_OFFPEAK): vol.Any(int, float),
    }
)


class EnedisByPDL:
    """PDL class."""

    def __init__(
        self,
        pdl: str,
        token: str,
        session: Any | None = None,
        timeout: int = TIMEOUT,
    ) -> None:
        """Initialize."""
        self._api: Enedis = Enedis(token, session, timeout)
        self.pdl = pdl
        self._tempo_subs: bool = False
        self._off_subs: bool = False
        self._ecowatt_subs: bool = False
        self._maxpower_subs: bool = False
        self.intervals: list[Tuple[str, str]] = []
        self.access: dict[str, Any] = {}
        self.contract: dict[str, Any] = {}
        self.address: dict[str, Any] = {}
        self.tempo: dict[str, Any] = {}
        self.ecowatt: dict[str, Any] = {}
        self.max_power: dict[str, Any] = {}
        self._connected: bool = False
        self._last_access: date | None = None
        self._params: dict[str, dict[str, Any]] = {PRODUCTION: {}, CONSUMPTION: {}}

    @property
    def is_connected(self) -> bool:
        """Connect state."""
        return self.access.get("valid", False) is True

    @property
    def has_intervals(self) -> bool:
        """Intervals exist."""
        return len(self.intervals) > 0

    @property
    def ecowatt_day(self) -> dict[str, Any]:
        """ecowatt."""
        str_date = dt.now().strftime("%Y-%m-%d")
        return self.ecowatt.get(str_date, {})

    @property
    def tempo_day(self) -> str | None:
        """Tempo day."""
        str_date = dt.now().strftime("%Y-%-m-%-d")
        return self.tempo.get(str_date)

    @property
    def prod_prices(self) -> dict[str, Any] | None:
        """Production resel price."""
        return self._params[PRODUCTION].get(ATTR_PRICES)

    @property
    def consum_prices(self) -> dict[str, Any] | None:
        """Offpeak hours prices."""
        return self._params[CONSUMPTION].get(ATTR_PRICES)

    @property
    def stats(self) -> dict[str, Any]:
        """Statistics."""
        stats = {}
        for mode, params in self._params.items():
            data = (
                params.get("dataset", {})
                .get("meter_reading", {})
                .get("interval_reading", {})
            )
            analytics = EnedisAnalytics(data)
            resultat = analytics.get_data_analytics(
                convertKwh=True,
                convertUTC=False,
                intervals=params.get(ATTR_INTERVALS, []),
                groupby=True,
                summary=True,
                prices=params.get(ATTR_PRICES, {}),
                cum_value=params.get(ATTR_CUM_VALUE, {}),
                cum_price=params.get(ATTR_CUM_PRICE, {}),
                start_date=params.get(ATTR_START),
                tempo=self.tempo,
            )
            stats.update({mode: resultat})
        return stats

    async def async_update(
        self,
        modes: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> None:
        """Update data.

        modes = {
            "consumption":{
                "service":["daily_consumption" | "consumption_load_curve"],
                start: [date],
                end: [date]
            },
            "production":{
                "service":["daily_production" | "production_load_curve"],
                start: [date],
                end: [date]
            }
        }
        If the update succeeds, the next one can only be done on the next day
        at least that force_refresh is true
        """
        self.access = await self._api.async_valid_access(self.pdl)
        if (
            self._last_access is not None
            and self._last_access > dt.now().date()
            and force_refresh is False
        ):
            return

        start = dt.now() - timedelta(days=730)
        end = dt.now()
        funcs: dict[str, Callable[..., Any]] = {
            DAILY_PROD: self._api.async_get_daily_production,
            DETAIL_PROD: self._api.async_get_details_production,
            DAILY_CONSUM: self._api.async_get_daily_consumption,
            DETAIL_CONSUM: self._api.async_get_details_consumption,
        }

        self.contract = await self._api.async_get_contract(self.pdl)
        self.address = await self._api.async_get_address(self.pdl)
        if self._ecowatt_subs:
            self.ecowatt = await self._api.async_get_ecowatt(
                start, end + timedelta(days=1)
            )
        if self._maxpower_subs:
            self.max_power = await self._api.async_get_max_power(self.pdl, start, end)
        if modes:
            try:
                validate = MODES_SCH(modes)
            except vol.Error as error:
                _LOGGER.error("The format is incorrect. (%s)", error)
            else:
                for mode, params in validate.items():
                    service = params.get(ATTR_SERVICE)
                    days = 370 if service in [DAILY_PROD, DAILY_CONSUM] else 7
                    func = funcs[params.get(ATTR_SERVICE)]
                    start = (
                        params.get(ATTR_START)
                        if params.get(ATTR_START)
                        else dt.now() - timedelta(days=days)
                    )
                    end = params.get(ATTR_END) if params.get(ATTR_END) else dt.now()
                    dataset = await func(self.pdl, start, end)
                    self._params[mode].update({"dataset": dataset, ATTR_START: start})
                    if service in [DAILY_CONSUM, DETAIL_CONSUM] and self._tempo_subs:
                        self.tempo = await self._api.async_get_tempo(start, end)

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

    def set_intervals(self, mode: str, intervals: list[Tuple[str, str]]) -> None:
        """Set intervals."""
        if isinstance(intervals, list):
            self.intervals = intervals
            self._params[mode].update({ATTR_INTERVALS: intervals})

    def set_prices(
        self,
        mode: str,
        prices: dict[str, Any],
    ) -> None:
        """Set intervals.

        prices = {
            "standard":{"price":[float]},
            "offpeak":{"price":[float]}
        }
        or
        prices = {
            "standard":{"blue":[float],"white":[float],"red":[float]},
            "offpeak":{"blue":[float],"white":[float],"red":[float]}
        }
        """
        try:
            validate = PRICE_SCH(prices)
        except vol.Error:
            try:
                validate = PRICE_TEMPO_SCH(prices)
            except vol.Error as error:
                _LOGGER.error("Format is incorrect (%s)", error)
            else:
                self.tempo_subscription(True)
                self._params[mode].update({ATTR_PRICES: validate})
        else:
            self.offpeak_subscription(True)
            self._params[mode].update({ATTR_PRICES: validate})

    def set_cumsum(self, mode: str, form: str, cum_sum: dict[str, Any]) -> None:
        """Set cumulative summary.

        mode: "production" or "consumption"
        format: "value" or "price"
        cum_sum = {"standard":[float], "offpeak":[float]}
        """
        try:
            validate = CUM_SCH(cum_sum)
        except vol.Error as error:
            _LOGGER.error("Format is incorrect (%s)", error)
        else:
            self._params[mode].update({f"cum_{form}".lower(): validate})
