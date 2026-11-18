# energy-market-insights

> **Can a business plan tomorrow's energy-intensive processes before the day-ahead prices are known, and how much does it save by doing so?**

![Status: work in progress](https://img.shields.io/badge/status-work%20in%20progress-orange)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**🚧 Work in progress:** features are being built step by step and checked off below.

## Motivation

German day-ahead electricity prices vary a lot within a single day. They drop when wind and solar output is high and can even turn negative. Many businesses have loads that can be moved in time, such as compressors, cooling, drying, batch production or charging electric vehicle fleets. A business that buys at exchange-linked prices can lower its energy costs by moving these loads into cheap hours. This also helps the grid absorb renewable power.

This project forecasts tomorrow's prices, schedules flexible loads into the cheapest hours, and uses backtests on past data to check how much money that would actually have saved.

### Why forecast prices that get published anyway?

Tomorrow's prices are set in an auction that closes today at 12:00 and are published at around 12:45. From then on no forecast is needed, and the planner simply uses the real prices.

Many decisions have to be made earlier, though. A business that buys directly on the exchange must submit its bids before 12:00. Shifts, staff and materials are often planned in the morning of the day before. This project forecasts tomorrow's prices **before the auction** from SMARD data, so that planning can start early:

| time of planning | prices used by the planner |
|---|---|
| before the prices for tomorrow are published | price **forecast** |
| once the prices for tomorrow are published (from ~12:45) | **actual** day-ahead prices |

Every plan states which of the two it is based on. The backtest measures how much deciding before the auction costs compared with planning on the actual prices.

## First result: feasibility check

Before building the full project, a short notebook checked whether the idea works at all: **[notebooks/00_feasibility.ipynb](notebooks/00_feasibility.ipynb)** (about 5 minutes to read, with all charts).

On 26 weeks of unseen data (May–Nov 2026), a simple model using only information available before the auction was compared with the rule of thumb *"tomorrow's prices are the same as today's"*. The task was to pick the 4 cheapest hours of each day for a flexible load:

| method | average error (€/MWh) | cheapest 4 hours found | price paid for those 4 hours (€/MWh) |
|---|---|---|---|
| rule of thumb | 36.3 | 3.0 of 4 | 67.8 |
| **model** | **28.6** | **3.4 of 4** | **63.4** |
| perfect knowledge of prices | 0 | 4 of 4 | 61.8 |

The average price of all hours was 139.5 €/MWh. A load planned with the model pays less than half of that, and only about 1.6 €/MWh more than with perfect knowledge. **Result: go.**

## Planned features

- [x] **Feasibility check:** one year of SMARD data, price vs. forecast residual load, simple model vs. rule of thumb: go ([notebook](notebooks/00_feasibility.ipynb))
- [ ] **Data pipeline:** incremental download from SMARD, stored in SQLite, cleaned and checked for anomalies (including negative prices)
- [ ] **Price forecast:** regression on SMARD's day-ahead forecasts for wind, solar and consumption (residual load), evaluated by MAE against a naive baseline and by how well it identifies the cheapest hours
- [ ] **Load shifting:** flexible loads defined in YAML (power, duration, time window, run in one block or split), scheduled with a sliding window, optional shared power limit; uses the actual prices once published and the forecast before
- [ ] **Backtest:** savings vs. a fixed shift, and regret vs. planning on the actual prices (the cost of deciding before the auction), over past months
- [ ] **Dashboard:** Flask + Plotly showing tomorrow's plan, savings and forecast quality
- [ ] **AI assistant (optional):** questions in natural language, answered through fixed functions (`plan_fuer_morgen`, `ersparnis`, `negative_preise`); it can be switched off, and the API key is read only from `.env`
- [ ] **Quality & deployment:** pytest, Ruff, GitHub Actions, Docker

## Tech stack

Python 3.12 · pandas · scikit-learn · SQLite · Flask · Plotly · pytest · Ruff · GitHub Actions · Docker

## Data source

All market data comes from **[SMARD.de](https://www.smard.de)**, the electricity market data platform of the German Federal Network Agency: day-ahead prices (DE-LU), grid load, generation by source, and day-ahead forecasts for generation and consumption.

> **Note on resolution:** Since 1 October 2025, day-ahead prices are published in 15-minute resolution. To keep the series comparable, all data is aggregated to hourly values (prices are averaged, energy quantities are summed).

Source: Bundesnetzagentur | SMARD.de, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Limitations

- **Savings refer to the exchange price only.** Grid fees (*Netzentgelte*), demand charges (*Leistungspreis*), levies and taxes aren't modeled, so actual savings on an electricity bill can differ. Adding them is a planned next step.
- **One day ahead only.** SMARD's forecasts for wind, solar and consumption cover the next day only, so the planner looks no further than tomorrow.
- **Forecast availability.** Planning before the auction assumes that SMARD's forecasts for tomorrow are online before 12:00. SMARD doesn't record when a forecast was published, so this is still being checked.
- Loads are scheduled on a whole-hour grid, one day at a time, without dependencies between processes.

## Next steps

- **Multi-day planning with weather forecasts:** forecast prices for the next 2–7 days from weather forecasts for wind and solar (e.g. Open-Meteo). Then loads could also be moved to another day.
- **Full electricity costs:** grid fees, demand charges, levies and taxes.
- **Exact optimisation** (MILP) for several loads sharing a power limit.

## Development

This project is developed with [Claude Code](https://claude.com/claude-code) as an AI pair programmer. The detailed project plan is in [docs/PLAN.md](docs/PLAN.md).

```bash
conda env create -f environment.yml   # creates the "emi" env and installs the package (editable, with dev tools)
conda activate emi
cp .env.example .env                  # optional: adjust settings
pytest && ruff check .
```

## License

Code: [MIT](LICENSE). Data: © Bundesnetzagentur | SMARD.de, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
