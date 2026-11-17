# energy-market-insights

> How do renewables drive German electricity prices? Data pipeline, ML forecasting and an interactive dashboard based on SMARD data – with an optional LLM agent to ask questions in plain language.

![Status: work in progress](https://img.shields.io/badge/status-work%20in%20progress-orange)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

> **🚧 Work in progress.** This project is under active development. The features below are planned and are checked off as they are implemented. Nothing is runnable yet.

## Key question

**How does the share of renewable energy affect the German day-ahead electricity price, and can tomorrow's price be forecast?**

The project looks at two related questions:

1. **Explain:** How strong is the merit-order effect? How much does the day-ahead price (DE-LU bidding zone) drop as the share of wind and solar in the load rises, and when do negative prices occur?
2. **Forecast:** Can hourly load and the next day's price be forecast from information that is available *before* the day-ahead auction closes (calendar, past prices, published generation and load forecasts)? The results are always compared against a naive baseline.

## Features

- [ ] **Data ingestion:** incremental download of hourly data from the SMARD.de API (generation by source, grid load, day-ahead price DE-LU)
- [ ] **Storage:** SQLite database with raw observations and a cleaned hourly table; re-running the download doesn't duplicate data
- [ ] **Data cleaning:** complete UTC time index, DST handling, gap detection, limited interpolation with flags
- [ ] **Anomaly detection:** flagging of negative prices and statistical outliers (rolling robust z-score)
- [ ] **Analysis:** renewable share vs. price, quantification of the merit-order effect
- [ ] **Forecasting:** naive baseline and regression models (scikit-learn) for load and day-ahead price, evaluated with time-series backtests
- [ ] **Dashboard:** Flask web app with interactive Plotly charts (overview, renewables vs. price, anomalies, forecast)
- [ ] **AI Q&A (optional):** ask questions about the data in natural language, using an LLM agent whose function calls go only to predefined queries; it can be switched off, and the API key is read only from `.env`
- [ ] **Quality:** pytest test suite, linting with Ruff, CI with GitHub Actions
- [ ] **Deployment:** Docker image and Docker Compose setup

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
- Forecast generation and consumption (planned as forecast inputs)

Data is fetched at hourly resolution and stored in UTC. The dashboard shows it in local time (`Europe/Berlin`).

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
├── forecast.py   # baseline and regression models, backtesting
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

## Limitations & future work

_Coming soon._

## License

Code: [MIT](LICENSE). Data: © Bundesnetzagentur | SMARD.de, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
