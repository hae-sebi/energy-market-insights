# energy-market-insights

> When should a business run its energy-intensive processes tomorrow, and how much does it save? Day-ahead price forecasting, load shifting and backtesting based on SMARD data, with an interactive dashboard and an optional LLM assistant.

![Status: work in progress](https://img.shields.io/badge/status-work%20in%20progress-orange)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

> **🚧 Work in progress.** This project is under active development. The features below are planned and are checked off as they are implemented. Nothing is runnable yet.

## Key question

**When should a business run its energy-intensive processes tomorrow, and how much does it save by doing so?**

The project combines three building blocks:

1. **Forecast:** Predict tomorrow's hourly day-ahead price (DE-LU bidding zone) *before* the auction closes, using SMARD's day-ahead forecasts for wind, solar and consumption (residual load). The forecast is judged by its MAE against a naive baseline and by whether it identifies the **cheapest hours** correctly.
2. **Schedule:** Place flexible loads (power, duration, time window, run continuously or split into blocks) into the cheapest hours.
3. **Evaluate:** Backtest over past months: **savings** vs. a fixed shift and **regret** vs. perfect price knowledge.

## Features

- [ ] **Feasibility check:** one year of data, scatter plot of price vs. renewable share, quick test model vs. baseline
- [ ] **Data ingestion:** incremental download from the SMARD.de API (generation by source, grid load, day-ahead price DE-LU, day-ahead generation and consumption forecasts)
- [ ] **Storage & cleaning:** SQLite storage; 15-minute prices (since 1 Oct 2025) are aggregated to hourly values; DST handling; gap flags
- [ ] **Anomaly detection:** negative prices and statistical outliers
- [ ] **Price forecast:** naive baseline vs. regression on forecast residual load, calendar and price lags, evaluated by MAE and top-k cheapest-hour hit rate
- [ ] **Load shifting:** flexible loads defined in YAML, sliding-window scheduler, optional shared power limit
- [ ] **Backtest:** savings vs. fixed shift and regret vs. perfect foresight over past months
- [ ] **Dashboard:** Flask + Plotly with tomorrow's plan, savings backtest, forecast quality and market context
- [ ] **AI assistant (optional):** questions in natural language, answered through fixed functions (`plan_fuer_morgen(last)`, `ersparnis(zeitraum)`, `negative_preise(zeitraum)`); it can be switched off, and the API key is read only from `.env`
- [ ] **Quality & deployment:** pytest, Ruff, GitHub Actions CI, Docker

## Tech stack

| Area | Tools |
|---|---|
| Language | Python 3.12 |
| Data | pandas, SQLite |
| Machine learning | scikit-learn |
| Web / visualization | Flask, Plotly |
| LLM agent (optional) | LLM API with function calling (tool use) |
| Testing & quality | pytest, pytest-cov, Ruff |
| CI | GitHub Actions |
| Deployment | Docker, Docker Compose |

## Data source

All market data comes from **[SMARD.de](https://www.smard.de)**, the electricity market data platform of the German Federal Network Agency (Bundesnetzagentur):

- Realized generation by energy source (Germany)
- Grid load / electricity consumption (Germany)
- Day-ahead wholesale price for the DE-LU bidding zone
- Day-ahead forecasts of generation (wind, solar) and consumption, used as forecast inputs

Since 1 October 2025, day-ahead prices are published in 15-minute resolution. All series are aggregated to hourly values (prices are averaged, energy quantities are summed). Timestamps are stored in UTC. The dashboard shows it in local time (`Europe/Berlin`).

**Attribution:** Bundesnetzagentur | SMARD.de, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Project structure (planned)

```
src/emi/
├── smard/        # SMARD API client and series definitions
├── db.py         # SQLite schema and data access
├── ingest.py     # incremental data download
├── cleaning.py   # cleaning and resampling
├── anomalies.py  # negative prices and outlier detection
├── features.py   # feature engineering
├── forecast.py   # baseline and regression price models
├── scheduling/   # load definitions (YAML), scheduler, savings backtest
├── queries.py    # shared query layer (dashboard + agent)
├── dashboard/    # Flask app and Plotly charts
├── assistant/    # optional LLM agent with function calling
└── cli.py        # command-line entry point
```

## Quickstart

_Coming soon._

## Configuration

_Coming soon._ Settings, including the optional LLM API key, will be read from environment variables or a local `.env` file, with a template in `.env.example`. Secrets are never committed.

## Methodology

_Coming soon:_ cleaning rules, outlier detection, forecast setup and leakage prevention.

## Results

_Coming soon._

## Limitations & next steps

- **Savings only cover the exchange price.** Grid fees (Netzentgelte), demand charges (Leistungspreis), levies and taxes aren't modeled, so actual savings on an electricity bill can differ. Modeling them is a planned next step.
- The scheduler works on a whole-hour grid and covers one day at a time.
- With a shared power limit, loads are placed by a greedy heuristic, not an exact optimizer (a MILP formulation is a possible next step).
- Dependencies between processes (one must finish before another starts) aren't modeled.

See [docs/PLAN.md](docs/PLAN.md) for the full project plan.

## License

Code: [MIT](LICENSE). Data: © Bundesnetzagentur | SMARD.de, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
