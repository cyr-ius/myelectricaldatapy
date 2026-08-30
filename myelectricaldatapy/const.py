"""Constants."""

from typing import Final

ATTR_CUM_PRICE = "cum_price"
ATTR_CUM_VALUE = "cum_value"
ATTR_END = "end"
ATTR_FN = "function"
ATTR_HPHC: Final = "hphc"
ATTR_INTERVALS = "intervals"
ATTR_OFFPEAK = "offpeak"
ATTR_PRICE: Final = "price"
ATTR_PRICES = "prices"
ATTR_STANDARD: Final = "standard"
ATTR_START = "start"
ATTR_TEMPO: Final = "tempo"
ATTR_PROD: Final = "production"
ATTR_CONSUM: Final = "consumption"
TEMPO_B: Final = "blue"
TEMPO_W: Final = "white"
TEMPO_R: Final = "red"
TEMPO_DAYS = (TEMPO_B, TEMPO_W, TEMPO_R)
SUBSCRIPTIONS = (ATTR_STANDARD, ATTR_HPHC, ATTR_TEMPO)
DEFAULT_SUBSCRIPTION: Final = ATTR_STANDARD
CONSUMPTION: Final = "consumption"
DAILY_CONSUM: Final = "daily_consumption"
DAILY_PROD: Final = "daily_production"
DETAIL_CONSUM: Final = "consumption_load_curve"
DETAIL_PROD: Final = "production_load_curve"
PRODUCTION: Final = "production"
CONF_ECOWATT = "ecowatt"
CONF_MAXPOWER = "max_power"
CONF_VALUE: Final = "value"
