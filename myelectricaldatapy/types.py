"""Public type definitions for myelectricaldatapy.

These aliases and ``TypedDict`` structures describe the data accepted and
returned by :class:`~myelectricaldatapy.EnedisByPDL` and
:class:`~myelectricaldatapy.Enedis`. They are re-exported from the package
root so consumers can annotate their own code::

    from myelectricaldatapy import Prices, EnergyCollect
"""

from typing import Literal, TypedDict

type Subscription = Literal["hphc", "tempo", "standard"]
type ProductionCollect = Literal["production_load_curve", "daily_production"]
type ConsumptionCollect = Literal["consumption_load_curve", "daily_consumption"]
type EnergyCollect = ProductionCollect | ConsumptionCollect
type Mode = Literal["consumption", "production"]

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


class StandardPrice(TypedDict):
    """Price mapping for a standard (single-rate) contract."""

    price: float


class TempoPrice(TypedDict):
    """Price mapping for a Tempo contract, one value per day colour."""

    blue: float
    white: float
    red: float


class Prices(TypedDict):
    """Prices for the ``standard`` and ``offpeak`` intervals."""

    standard: StandardPrice | TempoPrice
    offpeak: StandardPrice | TempoPrice


class Cum(TypedDict):
    """Cumulative starting values for ``standard`` and ``offpeak`` intervals."""

    standard: float
    offpeak: float


__all__ = [
    "ConsumptionCollect",
    "Cum",
    "EnergyCollect",
    "Mode",
    "Prices",
    "ProductionCollect",
    "Service",
    "StandardPrice",
    "Subscription",
    "TempoPrice",
]
