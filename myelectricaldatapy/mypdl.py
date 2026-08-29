"""Class for my PDL."""

from collections.abc import Callable
from datetime import date, datetime as dt, timedelta, tzinfo as _tzinfo
import logging
from typing import Any, Literal

from aiohttp import ClientSession

from .analytics import EnedisAnalytics
from .api import Enedis
from .const import (
    ATTR_CONSUM,
    ATTR_CUM_PRICE,
    ATTR_CUM_VALUE,
    ATTR_END,
    ATTR_FN,
    ATTR_HPHC,
    ATTR_INTERVALS,
    ATTR_OFFPEAK,
    ATTR_PRICE,
    ATTR_PRICES,
    ATTR_PROD,
    ATTR_STANDARD,
    ATTR_START,
    ATTR_TEMPO,
    CONF_VALUE,
    DAILY_CONSUM,
    DAILY_PROD,
    DEFAULT_SUBSCRIPTION,
    DETAIL_CONSUM,
    DETAIL_PROD,
    SUBSCRIPTIONS,
    TEMPO_B,
    TEMPO_DAYS,
)
from .exceptions import EnedisException, LimitReached
from .types import Cum, EnergyCollect, Mode, Prices, Subscription
from .tz import as_local, local_now, set_local_timezone

_LOGGER = logging.getLogger(__name__)

STANDARD_KEYS = (ATTR_PRICE,)


class FormatError(ValueError):
    """Raised when a user-provided mapping does not match the expected format."""


def _is_number(value: Any) -> bool:
    """Return True for an int or a float (but not a bool)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_price_group(group: Any, keys: tuple[str, ...], name: str) -> None:
    """Validate one price group (``standard`` or ``offpeak``)."""
    if not isinstance(group, dict):
        raise FormatError(f"'{name}' must be a mapping")
    if missing := [key for key in keys if key not in group]:
        raise FormatError(f"'{name}' is missing required keys {missing}")
    if extra := [key for key in group if key not in keys]:
        raise FormatError(f"'{name}' has unexpected keys {extra}")
    if invalid := [key for key in keys if not _is_number(group[key])]:
        raise FormatError(f"'{name}' values must be numbers {invalid}")


def validate_prices(prices: Any) -> None:
    """Validate a prices mapping and return the detected format."""
    if not isinstance(prices, dict):
        raise FormatError("prices must be a mapping")
    if ATTR_STANDARD not in prices:
        raise FormatError(f"'{ATTR_STANDARD}' is required")
    if extra := [key for key in prices if key not in (ATTR_STANDARD, ATTR_OFFPEAK)]:
        raise FormatError(f"unexpected keys {extra}")
    standard = prices[ATTR_STANDARD]
    is_tempo = isinstance(standard, dict) and TEMPO_B in standard
    keys = TEMPO_DAYS if is_tempo else STANDARD_KEYS
    _check_price_group(standard, keys, ATTR_STANDARD)
    if ATTR_OFFPEAK in prices:
        _check_price_group(prices[ATTR_OFFPEAK], keys, ATTR_OFFPEAK)


def validate_cumsum(cum_sum: Any) -> None:
    """Validate a cumulative summary mapping."""
    if not isinstance(cum_sum, dict):
        raise FormatError("cumulative summary must be a mapping")
    if ATTR_STANDARD not in cum_sum:
        raise FormatError(f"'{ATTR_STANDARD}' is required")
    for key, value in cum_sum.items():
        if key not in (ATTR_STANDARD, ATTR_OFFPEAK):
            raise FormatError(f"unexpected key '{key}'")
        if not _is_number(value):
            raise FormatError(f"'{key}' must be a number")


class EnedisByPDL:
    """Enedis by PDL class.

    This class allows you to obtain information specific to a connection point.

    The "set_collect" function allows you to specify the collection parameters from Enedis
    The "async_update_collects" function allows you to perform the calculations
    The result is displayed in the property: stats
    y"""

    def __init__(
        self,
        pdl: str,
        token: str,
        subscription: Subscription = "standard",
        session: ClientSession | None = None,
        timeout: int = 30,
        timezone: _tzinfo | None = None,
    ) -> None:
        """Initialize.

        timezone: the timezone to interpret naive datetimes in (e.g. Home
            Assistant's hass.config.time_zone / dt_util.get_default_time_zone()).
            Defaults to the host machine's timezone, which has no reason to
            match the consuming application's configured timezone.
        """
        session = ClientSession() if session is None else session
        self._api: Enedis = Enedis(token, session, timeout)
        self.pdl = pdl
        self._timezone = timezone
        self._connected: bool = False
        self._ecowatt_subs: bool = False
        self._maxpower_subs: bool = False
        self._params: dict[Mode, dict[str, Any]] = {}
        self.subscription: Subscription = subscription
        self.access: dict[str, Any] | None = None
        self.address: dict[str, Any] | None = None
        self.contract: dict[str, Any] | None = None
        self.ecowatt: dict[str, Any] | None = None
        self.has_collected: bool = False
        self.has_parameters: bool = False
        self.intervals: list[tuple[str, str]] = []
        self.last_access: dt = local_now()
        self.last_refresh: date | None = None
        self.max_power: dict[str, Any] | None = None
        self.tempo: dict[str, Any] | None = None

        if timezone is not None:
            set_local_timezone(timezone)

    @property
    def is_connected(self) -> bool:
        """Connect state."""
        return self.access is not None and (self.access.get("valid", False) is True)

    @property
    def has_intervals(self) -> bool:
        """Intervals exist."""
        return len(self.intervals) > 0

    @property
    def has_tempo_subscription(self) -> bool:
        """Tempo subscription status."""
        return self.subscription == ATTR_TEMPO

    @property
    def has_offpeak_hours_subscription(self) -> bool:
        """Offpeak hours subscription status."""
        return self.subscription == ATTR_HPHC

    @property
    def has_standard_subscription(self) -> bool:
        """Offpeak hours subscription status."""
        return self.subscription == ATTR_STANDARD

    @property
    def has_ecowatt_subscription(self) -> bool:
        """Ecowatt subscription status."""
        return self._ecowatt_subs

    @property
    def has_maxpower_subscription(self) -> bool:
        """Max power subscription status."""
        return self._maxpower_subs

    @property
    def ecowatt_day(self) -> dict[str, Any] | None:
        """ecowatt."""
        str_date = local_now().strftime("%Y-%m-%d")
        return self.ecowatt.get(str_date) if self.ecowatt is not None else None

    @property
    def tempo_day(self) -> str | None:
        """Tempo day."""
        str_date = local_now().strftime("%Y-%m-%d")
        return self.tempo.get(str_date) if self.tempo is not None else None

    @property
    def prod_prices(self) -> Prices | None:
        """Production resel price."""
        return (
            self._params[ATTR_PROD].get(ATTR_PRICES)
            if self._params is not None
            else None
        )

    @property
    def consum_prices(self) -> Prices | None:
        """Consumption prices."""
        return (
            self._params[ATTR_CONSUM].get(ATTR_PRICES)
            if self._params is not None
            else None
        )

    @property
    def stats(self) -> dict[str, Any]:
        """Statistics."""
        stats: dict[str, Any] = {}
        for mode, params in self._params.items():
            data = params.get("data", {})
            analytics = EnedisAnalytics(data, timezone=self._timezone)
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

    async def async_update(self, force_refresh: bool = False) -> None:
        """Update data."""

        start = local_now() - timedelta(days=1095)
        end = local_now() + timedelta(days=1)

        if force_refresh or (self.last_access.date() != local_now().date()):
            self.access = None
            self.contract = None
            self.address = None
            self.ecowatt = None
            self.max_power = None
            self.has_collected = False

        try:
            self.access = await self._api.async_valid_access(self.pdl)
            if self.access is not None and self.access.get("quota_reached", False):
                detail = self.access.get("information", "Quota reached")
                raise LimitReached(409, {"detail": detail})

            if self.is_connected is False:
                raise EnedisException(200, {"detail": "Api access not valid"})

            if not self.contract and self.has_collected is False:
                try:
                    self.contract = await self._api.async_get_contract(self.pdl)
                except EnedisException as error:
                    _LOGGER.warning(error)

            if not self.address and self.has_collected is False:
                try:
                    self.address = await self._api.async_get_address(self.pdl)
                except EnedisException as error:
                    _LOGGER.warning(error)

            if not self.ecowatt and self._ecowatt_subs:
                self.ecowatt = await self._api.async_get_ecowatt(start, end)

            if not self.max_power and self._maxpower_subs:
                self.max_power = await self._api.async_get_max_power(
                    self.pdl, start, end
                )

            if self.has_parameters and self.has_collected is False:
                await self.async_update_collects()
                self.last_refresh = local_now()
        except EnedisException as error:
            raise error from error
        finally:
            self.last_access = local_now()

    def set_ecowatt_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Ecowatt Subscription."""
        self._ecowatt_subs = activate is True

    def set_maxpower_subscription(self, activate: bool = False) -> None:
        """Enable or Disable Max power Subscription."""
        self._maxpower_subs = activate is True

    def _set_intervals(self, mode: Mode, intervals: list[tuple[str, str]]) -> None:
        """Set intervals."""
        if isinstance(intervals, list):
            self.intervals = intervals
            self._params[mode].update({ATTR_INTERVALS: intervals})

    def _set_prices(self, mode: Mode, prices: Prices) -> None:
        """Set prices."""
        try:
            validate_prices(prices)
        except FormatError as error:
            _LOGGER.error("Format is incorrect (%s)", error)
            return

        self._params[mode].update({ATTR_PRICES: prices})

    def _set_cumsum(
        self, mode: Mode, form: Literal["value", "price"], cum_sum: Cum
    ) -> None:
        """Set cumulative summary."""
        try:
            validate_cumsum(cum_sum)
        except FormatError as error:
            _LOGGER.error("Format is incorrect (%s)", error)
            return

        self._params[mode].update({f"cum_{form}".lower(): cum_sum})

    def _set_subscription(self, sub: Subscription) -> None:
        """Set subscription contract."""
        self._subscription = sub if sub in SUBSCRIPTIONS else DEFAULT_SUBSCRIPTION

    def set_data_fetch(
        self,
        service: EnergyCollect,
        start: dt | None = None,
        end: dt | None = None,
        intervals: list[tuple[str, str]] | None = None,
        prices: Prices | None = None,
        cum_value: Cum | None = None,
        cum_price: Cum | None = None,
    ) -> None:
        """Set parameters for data fetching.

        service: type of data collected
        start: date of begin to collect data
        end: date of end to collect data
        intervals: offpeak hours range - ex: [("01:00","05:00"),("12:00","14:00")]
        prices: price for standard interval and offpeak interval
        cum_sum: price of start
        cum_price:
        """
        funcs: dict[str, Callable[..., Any]] = {
            DAILY_PROD: self._api.async_get_daily_production,
            DETAIL_PROD: self._api.async_get_details_production,
            DAILY_CONSUM: self._api.async_get_daily_consumption,
            DETAIL_CONSUM: self._api.async_get_details_consumption,
        }
        days = 1095 if service in [DAILY_PROD, DAILY_CONSUM] else 7
        mode: Mode = (
            ATTR_CONSUM if service in [DAILY_CONSUM, DETAIL_CONSUM] else ATTR_PROD
        )
        func = funcs[service]
        dt_start = as_local(start) if start else local_now() - timedelta(days=days)
        dt_end = as_local(end) if end else local_now() + timedelta(days=1)
        self._params[mode] = {ATTR_FN: func, ATTR_START: dt_start, ATTR_END: dt_end}

        if intervals:
            self._set_intervals(mode, intervals)
        if prices:
            self._set_prices(mode, prices)
        if cum_value:
            self._set_cumsum(mode, CONF_VALUE, cum_value)
        if cum_price:
            self._set_cumsum(mode, ATTR_PRICE, cum_price)

        self.has_parameters = True

    async def async_update_collects(self) -> None:
        """Fetch data.

        It is necessary to value the initial data via the method: set_data_fetch.
        The execution of this method updates the property: stats.
        """

        for mode, attr in self._params.items():
            dataset = {}
            start = attr[ATTR_START]
            end = attr[ATTR_END]
            fn = attr[ATTR_FN]

            dataset = await fn(self.pdl, start, end)

            if dataset is None:
                raise EnedisException("Data collection is empty")

            data = dataset.get("meter_reading", {}).get("interval_reading", [])
            if len(data) == 0:
                raise EnedisException("Data collection is empty")

            self._params[mode].update({"data": data})

            if mode == ATTR_CONSUM and self.has_tempo_subscription:
                self.tempo = await self._api.async_get_tempo(start, end)

        self.has_collected = True

    async def async_close(self) -> None:
        """Close the session."""
        if self._api.auth.session:
            await self._api.auth.session.close()
