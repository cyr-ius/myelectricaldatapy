"""Public type definitions for myelectricaldatapy.

These ``pydantic`` models and ``Literal`` aliases describe the data accepted and
returned by :class:`~myelectricaldatapy.EnedisByPDL` and
:class:`~myelectricaldatapy.Enedis`. They are re-exported from the package root
so consumers can annotate their own code and let ``pydantic`` validate the
payloads coming from the API::

    from myelectricaldatapy import Prices, DataCollect
"""

from datetime import datetime
from enum import IntFlag
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, TypeAdapter, model_validator

# type Subscription = Literal["hphc", "tempo", "standard"]
type ProductionCollect = Literal["production_load_curve", "daily_production"]
type ConsumptionCollect = Literal["consumption_load_curve", "daily_consumption"]
type EnergyCollect = ProductionCollect | ConsumptionCollect
type Mode = Literal["consumption", "production"]
type TempoLabels = Literal["blue", "white", "red"]

type Service = (
    Literal[
        "addresses",
        "contact",
        "contracts",
        "daily_consumption_max_power",
        "identity",
        "valid_access",
    ]
    | EnergyCollect
)


class _ApiModel(BaseModel):
    """Base for models parsed from an API response.

    ``extra="allow"`` keeps unknown keys instead of raising, so an upstream
    schema change adding fields does not break parsing.
    """

    model_config = ConfigDict(extra="allow")


class _InputModel(BaseModel):
    """Base for mappings provided by the caller.

    ``extra="forbid"`` rejects unexpected keys, matching the strict validation
    the hand-written validators used to perform.
    """

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Caller-provided mappings
# --------------------------------------------------------------------------- #
class StandardPrice(_InputModel):
    """Price mapping for a standard (single-rate) contract."""

    price: float


class TempoPrice(_InputModel):
    """Price mapping for a Tempo contract, one value per day colour."""

    blue: float
    white: float
    red: float


class Prices(BaseModel):
    """Prices for the ``standard`` and ``offpeak`` intervals."""

    model_config = ConfigDict(extra="forbid")

    standard: StandardPrice | TempoPrice
    offpeak: StandardPrice | TempoPrice | None = None

    @model_validator(mode="after")
    def _consistent_format(self) -> "Prices":
        """``standard`` and ``offpeak`` must use the same price format."""
        if self.offpeak is not None and type(self.standard) is not type(self.offpeak):
            raise ValueError("'standard' and 'offpeak' must use the same price format")
        return self


class Cum(_InputModel):
    """Cumulative starting values for ``standard`` and ``offpeak`` intervals."""

    standard: float
    offpeak: float | None = None


# --------------------------------------------------------------------------- #
# API responses
# --------------------------------------------------------------------------- #
class AccessResponse(_ApiModel):
    """``valid_access`` payload."""

    valid: bool = False
    information: str | None = None
    consent_expiration_date: str | None = None
    call_number: int | None = None
    quota_reached: bool = False
    quota_limit: int | None = None
    quota_reset_at: str | None = None
    last_call: str | None = None
    ban: bool | None = None


class NaturalPerson(_ApiModel):
    """Natural person."""

    title: str
    firstname: str
    lastname: str


class Identity(_ApiModel):
    """Identity."""

    natural_person: NaturalPerson


class IdentityResponse(_ApiModel):
    """Identity payload."""

    customer_id: int
    identity: Identity


class UsagePointAddress(_ApiModel):
    """Postal address of a usage point."""

    street: str | None = None
    locality: str | None = None
    postal_code: str | None = None
    insee_code: str | None = None
    city: str | None = None
    country: str | None = None
    geo_points: dict[str, Any] | None = None


class UsagePoint(_ApiModel):
    """A single usage point (delivery point / PDL)."""

    usage_point_id: str
    usage_point_status: str | None = None
    meter_type: str | None = None
    usage_point_addresses: UsagePointAddress | None = None


class Contract(_ApiModel):
    """Contract attached to a usage point."""

    segment: str | None = None
    subscribed_power: str | None = None
    last_activation_date: str | None = None
    distribution_tariff: str | None = None
    offpeak_hours: str | None = None
    contract_status: str | None = None
    last_distribution_tariff_change_date: str | None = None


class UsagePointWrapper(_ApiModel):
    """``usage_points[]`` entry bundling a usage point and its contract."""

    usage_point: UsagePoint
    contracts: Contract | None = None


class Customer(_ApiModel):
    """``customer`` envelope of the ``addresses`` / ``contracts`` payloads."""

    customer_id: str | None = None
    usage_points: list[UsagePointWrapper] = []


class CustomerResponse(_ApiModel):
    """Top-level ``addresses`` / ``contracts`` payload."""

    customer: Customer


class ReadingType(_ApiModel):
    measurement_kind: str | None = None
    measuring_period: str | None = None
    unit: str | None = None
    aggregate: str | None = None


class IntervalReading(_ApiModel):
    value: str
    date: str
    interval_length: str | None = None
    measure_type: str | None = None


class MeterReading(_ApiModel):
    usage_point_id: str | None = None
    start: str | None = None
    end: str | None = None
    quality: str | None = None
    reading_type: ReadingType | None = None
    interval_reading: list[IntervalReading] = []


class DataCollect(_ApiModel):
    meter_reading: MeterReading


class EcowattDay(_ApiModel):
    value: int
    message: str
    detail: dict[str, int] = {}


class TempoDays(_ApiModel):
    """``rte/tempo/days`` payload: remaining days per colour before year end."""

    blue: int = 0
    white: int = 0
    red: int = 0


class Subscription(IntFlag):
    """Subscription."""

    STANDARD = 1
    HPHC = 2
    TEMPO = 4


def _check_iso_date(value: str) -> str:
    """Ensure a mapping key is a real, zero-padded ``YYYY-MM-DD`` calendar date."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")  # noqa: DTZ007  # shape check only
    except ValueError as error:
        raise ValueError(f"expected a YYYY-MM-DD date, got {value!r}") from error
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(f"expected a zero-padded YYYY-MM-DD date, got {value!r}")
    return value


type IsoDate = Annotated[str, AfterValidator(_check_iso_date)]

type EcowattMapping = dict[IsoDate, EcowattDay]
type TempoMapping = dict[IsoDate, TempoLabels]


# Adapters for the payloads that are plain mappings rather than objects.
EcowattResponse: TypeAdapter[EcowattMapping] = TypeAdapter(EcowattMapping)
TempoResponse: TypeAdapter[TempoMapping] = TypeAdapter(TempoMapping)


__all__ = [
    "AccessResponse",
    "ConsumptionCollect",
    "Contract",
    "Cum",
    "Customer",
    "CustomerResponse",
    "DataCollect",
    "EcowattDay",
    "EcowattMapping",
    "EcowattResponse",
    "EnergyCollect",
    "IdentityResponse",
    "IntervalReading",
    "IsoDate",
    "MeterReading",
    "Mode",
    "Prices",
    "ProductionCollect",
    "ReadingType",
    "Service",
    "StandardPrice",
    "Subscription",
    "TempoDays",
    "TempoLabels",
    "TempoMapping",
    "TempoPrice",
    "TempoResponse",
    "UsagePoint",
    "UsagePointAddress",
    "UsagePointWrapper",
]
