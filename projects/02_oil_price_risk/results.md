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

## One-day VaR backtest, 2022-02-10 to 2025-12-31 (982 days, same window for every model)

Exceedance rates for a long and a short position; Kupiec tests coverage, Christoffersen tests independence (p < 0.05 rejects the model).

| Model | Conf. | Long: breaches | Kupiec p | Indep. p | Short: breaches | Kupiec p | Indep. p |
|---|---|---|---|---|---|---|---|
| EWMA normal, lambda 0.9 | 95% | 6.72% | 0.018 | 0.448 | 4.58% | 0.543 | 0.962 |
| EWMA normal, lambda 0.94 | 95% | 6.42% | 0.051 | 0.623 | 3.97% | 0.126 | 0.718 |
| EWMA normal, lambda 0.97 | 95% | 6.11% | 0.122 | 0.480 | 4.18% | 0.223 | 0.824 |
| Historical simulation, 250 d | 95% | 5.09% | 0.895 | 0.048 | 5.09% | 0.895 | 0.372 |
| Filtered HS, lambda 0.94 | 95% | 5.70% | 0.323 | 0.319 | 5.19% | 0.782 | 0.660 |
| EWMA normal, lambda 0.9 | 99% | 1.73% | 0.037 | 0.295 | 1.63% | 0.069 | 0.466 |
| EWMA normal, lambda 0.94 | 99% | 1.73% | 0.037 | 0.295 | 1.12% | 0.710 | 0.108 |
| EWMA normal, lambda 0.97 | 99% | 1.83% | 0.019 | 0.041 | 1.02% | 0.954 | 0.086 |
| Historical simulation, 250 d | 99% | 1.22% | 0.499 | 0.007 | 1.53% | 0.123 | 0.223 |
| Filtered HS, lambda 0.94 | 99% | 1.12% | 0.710 | 0.108 | 1.53% | 0.123 | 0.223 |
