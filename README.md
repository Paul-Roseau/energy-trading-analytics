![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![pandas](https://img.shields.io/badge/pandas-2.1%2B-150458)
![statsmodels](https://img.shields.io/badge/statsmodels-0.14%2B-4051B5)
![Data](https://img.shields.io/badge/Data-EIA%20public-2E7D32)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

# Energy Trading Analytics

**Python toolkit for energy market analysis: Brent-WTI spread trading, oil price risk models and physical storage economics**

Built on public EIA data, no Bloomberg Terminal required.

---

## Overview

This repository groups **three projects on crude oil and refined products markets**. Each project is a standalone Python script that reads the EIA data and produces its charts and result tables.

The core idea is to:

 **Turn energy market analyses into reproducible Python tools: tested, documented and runnable by anyone on public data.**

| Project | Description | Main Tools |
|---|---|---|
| [Brent-WTI Spread Trading](projects/01_brent_wti_spread) | Mean-reversion analysis of the Brent-WTI spread, z-score strategy backtest, options on the spread | ADF, Engle-Granger, Ornstein-Uhlenbeck, Bachelier, Kirk |
| [Oil Price Risk Models](projects/02_oil_price_risk) | Monte Carlo price forecasts and one-day VaR backtesting on Brent | GBM, OU, EWMA, Historical & Filtered HS, Kupiec, Christoffersen |
| [Storage Arbitrage Calculator](projects/03_storage_arbitrage) | Sell-now vs store decision for a hedged diesel cargo in contango | Cash-and-carry P&L, break-evens, decision map |

![Brent-WTI spread](projects/01_brent_wti_spread/figures/prices_and_spread.png)

---

## Key Results

| Project | Result |
|---|---|
| Brent-WTI Spread | Half-life down from **17 to 4 trading days** since WTI Midland joined Dated Brent (June 2023) |
| Brent-WTI Spread | Z-score strategy: **Sharpe 0.66** at next-close execution vs 1.01 at same-close execution |
| Oil Price Risk | OU beats GBM on forecast error (RMSE **8.3 vs 12.1** USD/bbl over 2024) |
| Oil Price Risk | **Filtered Historical Simulation** is the only VaR model passing both backtests at 99% |
| Storage Arbitrage | 6.50 USD/t of contango does not pay for storage + 5% financing: storing wins only below **1.67%** |

---

## Project Structure

```
energy-trading-analytics/
├── data/                              # EIA daily spot prices (Brent, WTI)
├── projects/
│   ├── 01_brent_wti_spread/
│   │   ├── brent_wti_spread.py        # Stats, OU calibration, z-score backtest, spread options
│   │   ├── figures/
│   │   └── results.md
│   ├── 02_oil_price_risk/
│   │   ├── oil_price_risk.py          # GBM vs OU Monte Carlo, VaR models and backtests
│   │   ├── figures/
│   │   └── results.md
│   └── 03_storage_arbitrage/
│       ├── storage_calculator.py      # Sell-now vs store P&L, break-evens, scenarios
│       ├── example_case.json          # Inputs of the example case
│       ├── figures/
│       └── results.md
├── scripts/update_data.py             # Refresh the EIA data
└── requirements.txt
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/Paul-Roseau/energy-trading-analytics.git
cd energy-trading-analytics

# Install dependencies
pip install -r requirements.txt
```

## Running the Projects

```bash
python projects/01_brent_wti_spread/brent_wti_spread.py
python projects/02_oil_price_risk/oil_price_risk.py
python projects/03_storage_arbitrage/storage_calculator.py
```

Each script writes its charts to `figures/` and its tables to `results.md`.

---

## Data

* **Source**: U.S. Energy Information Administration (EIA), daily spot prices
* **Series**: Europe Brent (FOB) and WTI (Cushing)
* **Access**: [datahub.io oil-prices package](https://github.com/datasets/oil-prices)
* **Licence**: public domain
* Refresh with `python scripts/update_data.py`

---

## Technology Stack

* **Python**
* **pandas / NumPy**: data handling
* **SciPy / statsmodels**: statistics and econometrics
* **Matplotlib**: charts

---

## Author

**Paul Roseau** | MSc Energy Management, ESCP Business School

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Profile-0077B5?style=flat&logo=linkedin)](https://www.linkedin.com/in/paul-roseau-ba6a96174)
[![GitHub](https://img.shields.io/badge/GitHub-Portfolio-181717?style=flat&logo=github)](https://github.com/Paul-Roseau)
