# Brent crude risk models: results

EIA Brent spot (Europe, FOB), 2021-01-04 to 2025-12-31, 1,263 daily prices.

## Descriptive statistics

|  | Price (USD/bbl) | Log return |
|---|---|---|
| Observations | 1263 | 1262 |
| Mean | 80.77 | 3.94% annualised |
| Std deviation | 14.02 | 35.14% annualised |
| Skewness | 1.06 | -0.53 |
| Excess kurtosis | 1.37 | 2.93 |
| Jarque-Bera | 331.9 | 505.7 |
| ADF statistic (p-value) | -2.30 (0.172), log price | -17.34 (0.000) |

## Calibration, training window 2021-01-04 to 2023-12-31 (756 prices)

| Parameter | GBM | OU on log price |
|---|---|---|
| Drift mu | 22.03% | - |
| Volatility sigma | 38.89% | 38.98% |
| Mean reversion kappa (per year) | - | 3.58 |
| Half-life | - | 49 trading days |
| Long-run level exp(theta) | - | 86.82 USD/bbl |
| kappa after Kendall bias correction | - | 2.24 (half-life 78 days) |

## Monte Carlo forecasts from 2023-12-29 (S0 = 77.69, 5,000 paths)

| Horizon | Model | Terminal mean | 75% band at horizon | Actual at horizon | RMSE of mean path | Days inside 75% band |
|---|---|---|---|---|---|---|
| 2024 | GBM | 97.26 | 57.12 - 142.20 | 74.58 | 12.06 | 100% |
| 2024 | OU | 87.48 | 73.47 - 102.52 | 74.58 | 8.28 | 94% |
| 2024-2025 | GBM | 121.44 | 54.99 - 197.23 | 61.35 | 30.70 | 100% |
| 2024-2025 | OU | 87.62 | 72.86 - 102.85 | 61.35 | 14.74 | 59% |
