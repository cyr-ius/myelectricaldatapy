"""Constants."""

from typing import Final

ATTR_CUM_PRICE = "cum_price"
ATTR_CUM_VALUE = "cum_value"
ATTR_END = "end"
ATTR_FN = "function"
ATTR_HPHC = "hphc"
ATTR_INTERVALS = "intervals"
ATTR_OFFPEAK = "offpeak"
ATTR_PRICE: Final = "price"
ATTR_PRICES = "prices"
ATTR_STANDARD = "standard"
ATTR_START = "start"
ATTR_TEMPO = "tempo"
TEMPO_DAYS = ("blue", "white", "red")
SUBSCRIPTIONS = (ATTR_STANDARD, ATTR_HPHC, ATTR_TEMPO)
DEFAULT_SUBSCRIPTION = ATTR_STANDARD
CONSUMPTION: Final = "consumption"
DAILY_CONSUM: Final = "daily_consumption"
DAILY_PROD: Final = "daily_production"
DETAIL_CONSUM: Final = "consumption_load_curve"
DETAIL_PROD: Final = "production_load_curve"
PRODUCTION: Final = "production"
