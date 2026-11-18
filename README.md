# energy-market-insights

> **When should a business run its energy-intensive processes tomorrow, and how much does it save by doing so?**

![Status: work in progress](https://img.shields.io/badge/status-work%20in%20progress-orange)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**🚧 Work in progress:** features are being built step by step and checked off below.

## Motivation

German day-ahead electricity prices vary a lot within a single day. They drop when wind and solar output is high and can even turn negative. Many businesses have loads that can be moved in time, such as compressors, cooling, drying, batch production or charging electric vehicle fleets. A business that buys at exchange-linked prices can lower its energy costs by moving these loads into cheap hours. This also helps the grid absorb renewable power.

This project forecasts tomorrow's prices, schedules flexible loads into the cheapest hours, and uses backtests on past data to check how much money that would actually have saved.

## Planned features

- [x] **Feasibility check:** one year of SMARD data, price vs. forecast residual load, simple model vs. rule of thumb: go ([notebook](notebooks/00_feasibility.ipynb))
- [ ] **Data pipeline:** incremental download from SMARD, stored in SQLite, cleaned and checked for anomalies (including negative prices)
- [ ] **Price forecast:** regression on SMARD's day-ahead forecasts for wind, solar and consumption (residual load), evaluated by MAE against a naive baseline and by how well it identifies the cheapest hours
- [ ] **Load shifting:** flexible loads defined in YAML (power, duration, time window, run in one block or split), scheduled with a sliding window, optional shared power limit
- [ ] **Backtest:** savings vs. a fixed shift and regret vs. perfect price knowledge over past months
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
- Loads are scheduled on a whole-hour grid, one day at a time, without dependencies between processes.

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
