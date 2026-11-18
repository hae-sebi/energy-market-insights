"""Catalogue of the SMARD series used in this project.

SMARD identifies every data series by a numeric "filter ID" (e.g. 4169 = price).
This module gives each ID a readable name and some metadata, so the rest of the
code can write ``SERIES["price"].filter_id`` instead of a magic number.

All filter IDs were verified against the live API on 2026-11-18 (region DE-LU):

* Timestamps are UTC epoch milliseconds marking the *start* of an interval.
  Data files ("chunks") cover one week, starting Monday 00:00 Europe/Berlin.
* SMARD's ``hour`` series equal the aggregate of its ``quarterhour`` series:
  prices are the mean of the four quarter-hours, energy values (MWh) the sum
  (max. deviation 0.02, i.e. rounding only).
* ``fc_residual_load`` (4362) == ``fc_load`` (411) - ``fc_wind_solar`` (5097),
  and ``fc_wind_solar`` == ``fc_wind_onshore`` + ``fc_wind_offshore`` + ``fc_solar``.

Terms:

* **Residual load** - electricity demand minus wind and solar generation, i.e.
  what conventional power plants, storage and imports still have to cover.
  High residual load usually means high prices.
* **Forecast** (``fc_``) - day-ahead forecasts by the transmission system
  operators. Unlike ``actual`` values they are known *before* the price
  auction, so they may be used as model inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

REGION = "DE-LU"  # bidding zone Germany + Luxembourg (one common electricity price)

# What kind of data a series contains:
#   "price"    - result of the day-ahead auction (what we want to predict)
#   "actual"   - measured values, only known afterwards
#   "forecast" - predictions, already known before the auction
Kind = Literal["price", "actual", "forecast"]


# `@dataclass` generates the boilerplate (constructor, ==, readable print) from
# the field list below. `frozen=True` makes instances read-only, so nobody can
# accidentally change e.g. the filter ID of the price series at runtime.
@dataclass(frozen=True)
class Series:
    """Metadata of one SMARD data series."""

    key: str  # short name used in this project, e.g. "price"
    filter_id: int  # SMARD's numeric ID, e.g. 4169
    label: str  # human-readable name for plots and tables
    unit: Literal["EUR/MWh", "MWh"]  # price per MWh, or energy amount in MWh
    kind: Kind
    renewable: bool = False  # True for wind, solar, biomass, hydro, ...

    # `@property` makes this a computed attribute: written as
    # `series.aggregation` (no parentheses), but calculated on each access.
    @property
    def aggregation(self) -> Literal["mean", "sum"]:
        """How quarter-hour values combine into an hourly value.

        * Prices -> mean: four quarter-hours at 100 EUR/MWh give an hour at
          100 EUR/MWh, not 400.
        * Energy (MWh) -> sum: four quarter-hours with 1,000 MWh each give
          4,000 MWh in that hour.

        Note: this only *describes* the correct rule. The project currently uses
        SMARD's ready-made hourly series and does not aggregate on its own.
        """
        return "mean" if self.unit == "EUR/MWh" else "sum"


# The catalogue itself. The leading underscore marks `_ALL` as internal; use
# the `SERIES` dict below instead.
_ALL = [
    # Day-ahead auction result
    Series("price", 4169, "Day-ahead price DE-LU", "EUR/MWh", "price"),
    # Realised values (published with a delay of a few hours)
    Series("load", 410, "Grid load", "MWh", "actual"),
    Series("residual_load", 4359, "Residual load", "MWh", "actual"),
    Series("wind_onshore", 4067, "Wind onshore", "MWh", "actual", renewable=True),
    Series("wind_offshore", 1225, "Wind offshore", "MWh", "actual", renewable=True),
    Series("solar", 4068, "Photovoltaics", "MWh", "actual", renewable=True),
    Series("biomass", 4066, "Biomass", "MWh", "actual", renewable=True),
    Series("hydro", 1226, "Hydropower", "MWh", "actual", renewable=True),
    Series("other_renewable", 1228, "Other renewables", "MWh", "actual", renewable=True),
    Series("lignite", 1223, "Lignite", "MWh", "actual"),
    Series("hard_coal", 4069, "Hard coal", "MWh", "actual"),
    Series("gas", 4071, "Natural gas", "MWh", "actual"),
    Series("pumped_storage", 4070, "Pumped storage (generation)", "MWh", "actual"),
    Series("other_conventional", 1227, "Other conventional", "MWh", "actual"),
    # Nuclear (1224) is left out on purpose: the last German plants shut down in 2023.
    # Day-ahead forecasts by the transmission system operators
    Series("fc_load", 411, "Forecast: grid load", "MWh", "forecast"),
    Series("fc_residual_load", 4362, "Forecast: residual load", "MWh", "forecast"),
    Series("fc_wind_solar", 5097, "Forecast: wind + PV", "MWh", "forecast"),
    Series("fc_wind_onshore", 123, "Forecast: wind onshore", "MWh", "forecast"),
    Series("fc_wind_offshore", 3791, "Forecast: wind offshore", "MWh", "forecast"),
    Series("fc_solar", 125, "Forecast: photovoltaics", "MWh", "forecast"),
    Series("fc_generation", 122, "Forecast: total generation", "MWh", "forecast"),
]

# Lookup table: key -> Series, e.g. SERIES["price"].filter_id == 4169.
# Built with a "dict comprehension": {key: value for item in list}.
SERIES: dict[str, Series] = {s.key: s for s in _ALL}
