"""Class for analytics."""

from datetime import datetime as dt, timedelta, tzinfo as _tzinfo
import logging
import re
from typing import Any

import pandas as pd

from .const import ATTR_OFFPEAK, ATTR_STANDARD, TEMPO_DAYS
from .exceptions import AnalyticsError, EnedisException
from .types import TempoLabels
from .tz import get_local_timezone

logger = logging.getLogger(__name__)


class EnedisAnalytics:
    """Data analytics."""

    def __init__(self, data: Any, timezone: _tzinfo | None = None) -> None:
        """Initialize Dataframe."""
        # Resolved per instance (not at import/class-definition time) so a
        # timezone set later via tz.set_local_timezone(), or passed here
        # explicitly, is honored.
        self.local_timezone = timezone or get_local_timezone()
        try:
            if isinstance(data, list):
                data = self._shift_timestamps_to_interval_start(data)
            self.df = pd.DataFrame(data)
        except Exception as error:  # normalized below
            raise AnalyticsError(
                f"Could not build a dataframe from the provided data: {error}"
            ) from error

    def get_data_analytics(
        self,
        convertKwh: bool = False,
        start_date: dt | None = None,
        intervals: list[tuple[str, str]] | None = None,
        groupby: bool = False,
        summary: bool = False,
        cum_value: dict[str, Any] | None = None,
        cum_price: dict[str, Any] | None = None,
        prices: dict[str, Any] | None = None,
        tempo: dict[str, TempoLabels] | None = None,
    ) -> Any:
        """Convert data to analyze.

        Any failure while crunching the dataframe is re-raised as
        :class:`AnalyticsError` so callers only have to catch
        :class:`EnedisException`.
        """
        try:
            return self._get_data_analytics(
                convertKwh=convertKwh,
                start_date=start_date,
                intervals=intervals,
                groupby=groupby,
                summary=summary,
                cum_value=cum_value,
                cum_price=cum_price,
                prices=prices,
                tempo=tempo,
            )
        except EnedisException:
            raise
        except Exception as error:  # normalized below
            raise AnalyticsError(
                f"Failed to compute analytics from the provided dataset: {error}"
            ) from error

    def _get_data_analytics(
        self,
        convertKwh: bool = False,
        start_date: dt | None = None,
        intervals: list[tuple[str, str]] | None = None,
        groupby: bool = False,
        summary: bool = False,
        cum_value: dict[str, Any] | None = None,
        cum_price: dict[str, Any] | None = None,
        prices: dict[str, Any] | None = None,
        tempo: dict[str, TempoLabels] | None = None,
    ) -> Any:
        """Convert data to analyze."""

        cum_value = cum_value or {}
        cum_price = cum_price or {}

        step_hour = self._prepare_dataframe(start_date)
        if self.df.empty:
            return self.df.to_dict(orient="records")

        self._apply_value_conversion(convertKwh, step_hour)

        if intervals:
            self._get_data_interval(intervals)

        if groupby:
            self._groupby_period(step_hour)

        if tempo:
            self._set_tempo_days(tempo)

        notes = list(self.df.notes.drop_duplicates())
        self._apply_pricing(prices, tempo, summary, cum_price, notes)

        if summary:
            self._apply_value_summary(cum_value, notes)

        return self.df.to_dict(orient="records")

    def _prepare_dataframe(self, start_date: dt | None) -> bool:
        """Normalize dates, localize timezone, filter and mark rows.

        Timestamps are already shifted from interval-END to interval-START
        by :meth:`_shift_timestamps_to_interval_start` at construction time,
        so no further per-row adjustment is needed here.

        Returns whether the dataset is stepped (has an interval_length column).
        """
        step_hour = False

        if self.df.empty:
            return step_hour

        # Convert str to datetime
        try:
            self.df["date"] = pd.to_datetime(
                self.df["date"], format="%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            self.df["date"] = pd.to_datetime(self.df["date"], format="%Y-%m-%d")

        self.df["date"] = self.df["date"].dt.tz_localize(self.local_timezone)

        if "interval_length" in self.df:
            step_hour = True

        if start_date:
            dt_start_date = pd.to_datetime(start_date, format="%Y-%m-%d %H:%M:%S")
            if dt_start_date.tzinfo is None:
                dt_start_date = dt_start_date.tz_localize(self.local_timezone)
            self.df = self.df[(self.df["date"] > dt_start_date)]

        self.df.index = self.df["date"]

        # Add mark
        self.df["notes"] = ATTR_STANDARD

        return step_hour

    def _apply_value_conversion(self, convertKwh: bool, step_hour: bool) -> None:
        """Weight values by interval length and optionally convert Wh to kWh."""
        self.df["interval_length"] = (
            self.df["interval_length"].transform(self._weighted_interval)
            if step_hour
            else 1
        )

        if convertKwh:
            self.df["value"] = (
                pd.to_numeric(self.df["value"]) / 1000 * self.df["interval_length"]
            )
        else:
            self.df["value"] = (
                pd.to_numeric(self.df["value"]) * self.df["interval_length"]
            )

    def _groupby_period(self, step_hour: bool) -> None:
        """Aggregate values by note and period (hour or day)."""
        freq = "h" if step_hour else "D"
        self.df = (
            self.df.groupby(["notes", pd.Grouper(key="date", freq=freq)])["value"]
            .sum()
            .reset_index()
        )

    def _apply_pricing(
        self,
        prices: dict[str, Any] | None,
        tempo: dict[str, TempoLabels] | None,
        summary: bool,
        cum_price: dict[str, Any],
        notes: list[str],
    ) -> None:
        """Compute a price per row and, if requested, a cumulative price per note."""
        if not prices:
            return

        for mode, values in prices.items():
            if isinstance(values, dict):
                for offset, price in values.items():
                    if tempo and offset in TEMPO_DAYS:
                        self.df.loc[
                            (self.df.notes == mode) & (self.df.tempo == offset),
                            "price",
                        ] = self.df.value * price
                    elif offset == "price":
                        self.df.loc[(self.df.notes == mode), "price"] = (
                            self.df.value * price
                        )
                    else:
                        self.df.loc[(self.df.notes == mode), "price"] = None

        if summary:
            for note in notes:
                self.df.loc[(self.df.notes == note), "sum_price"] = self.df[
                    (self.df.notes == note)
                ].price.cumsum() + cum_price.get(note, 0)

    def _apply_value_summary(self, cum_value: dict[str, Any], notes: list[str]) -> None:
        """Add a cumulative value sum per note."""
        for note in notes:
            self.df.loc[(self.df.notes == note), "sum_value"] = self.df[
                (self.df.notes == note)
            ].value.cumsum() + cum_value.get(note, 0)

    def _weighted_interval(self, interval: str) -> float | int:
        """Compute weighted."""
        if interval and len(rslt := re.findall("PT([0-9]{1,2})M", interval)) == 1:
            return int(rslt[0]) / 60
        return 1

    def _get_data_interval(self, intervals: list[tuple[str, str]]) -> pd.DataFrame:
        """Group date from range time."""
        for interval in intervals:
            # Convert str to datetime
            start = pd.to_datetime(interval[0], format="%H:%M:%S").time()
            end = pd.to_datetime(interval[1], format="%H:%M:%S").time()
            # Mark (handle ranges spanning midnight, e.g. 22:00:00 -> 06:00:00).
            # `date` holds the START of each reading's interval (see
            # _shift_timestamps_to_interval_start), so bounds are
            # start-inclusive / end-exclusive: a reading starting at
            # `end` already belongs to the next (non-offpeak) slot.
            date_time = self.df["date"].dt.time
            if start <= end:
                mask = (date_time >= start) & (date_time < end)
            else:
                mask = (date_time >= start) | (date_time < end)
            self.df.loc[mask, "notes"] = ATTR_OFFPEAK

        return self.df

    def _set_tempo_days(self, tempo: dict[str, TempoLabels]) -> None:
        """Add columns with tempo day."""
        for str_date, value in tempo.items():
            dt_date = pd.to_datetime(str_date, format="%Y-%m-%d")
            self.df.loc[(self.df["date"].dt.date == dt_date.date()), "tempo"] = value

    def _parse_iso8601_duration_to_minutes(self, duration: str) -> int:
        """Parse ISO 8601 duration format to minutes."""
        match = re.match(r"PT(\d+)([HM])", duration)
        if not match:
            return 30

        value = int(match.group(1))
        unit = match.group(2)

        return value * 60 if unit == "H" else value

    def _shift_timestamps_to_interval_start(
        self, readings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Shift timestamps from interval END to interval START.

        Enedis API returns timestamps representing the END of each measurement interval.
        For better UX and to avoid confusion with midnight timestamps, we shift all timestamps
        backwards by the interval_length to represent the START of each interval.

        Example with 30min intervals:
            API returns:  2025-11-22 00:30:00 (end of 00:00-00:30 interval)
            We transform: 2025-11-22 00:00:00 (start of 00:00-00:30 interval)

        This also fixes the midnight edge case where:
            API returns:  2025-11-23 00:00:00 (end of 23:30-00:00 interval of day 22)
            We transform: 2025-11-22 23:30:00 (start of that interval, correctly on day 22)

        Readings without an interval_length (e.g. daily aggregates) are returned
        unchanged. Input readings are never mutated: callers (e.g. EnedisByPDL.stats,
        a property recomputed on every access from the same stored list) may reuse
        them across multiple EnedisAnalytics calls.
        """
        shifted_count = 0
        shifted_readings: list[dict[str, Any]] = []

        for reading in readings:
            interval_length_iso = reading.get("interval_length")
            original_date = reading.get("date")
            if not original_date or not interval_length_iso:
                shifted_readings.append(reading)
                continue

            # Parse ISO 8601 duration to minutes
            interval_minutes = self._parse_iso8601_duration_to_minutes(
                interval_length_iso
            )

            # Parse datetime (handle both formats: "YYYY-MM-DD HH:MM:SS" and "YYYY-MM-DDTHH:MM:SS")
            try:
                if "T" in original_date:
                    dt_orig_date = dt.fromisoformat(original_date)
                else:
                    dt_orig_date = dt.strptime(
                        original_date, "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=self.local_timezone)

                # Shift backwards by interval_length
                shifted_dt = dt_orig_date - timedelta(minutes=interval_minutes)

                # Format back to original format
                new_date = (
                    shifted_dt.strftime("%Y-%m-%dT%H:%M:%S")
                    if "T" in original_date
                    else shifted_dt.strftime("%Y-%m-%d %H:%M:%S")
                )

                shifted_readings.append({**reading, "date": new_date})
                shifted_count += 1

            except ValueError as e:
                logger.warning(
                    f"[ENEDIS] Failed to shift timestamp '{original_date}': {e}"
                )
                shifted_readings.append(reading)

        if shifted_count > 0:
            logger.info(
                f"[ENEDIS] Shifted {shifted_count} timestamps from interval END → START"
            )

        return shifted_readings
