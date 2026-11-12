# Brent-WTI spread: results

EIA daily spot prices, 2016-01-07 to 2026-02-11, 2,493 common dates (20 Apr 2020 removed: negative WTI spot print).

## Descriptive statistics (USD/bbl)

|  | Spread level | Daily change |
|---|---|---|
| obs | 2,493.000 | 2,492.000 |
| mean | 4.096 | 0.003 |
| std | 2.716 | 0.950 |
| min | -5.660 | -10.750 |
| max | 14.370 | 7.180 |
| skew | 0.324 | -0.579 |
| excess_kurtosis | 0.041 | 10.672 |
| jarque_bera | 43.776 | 11,912.346 |

## Unit-root and cointegration tests

| Series | ADF stat | p-value | lags (AIC) | 1% critical |
|---|---|---|---|---|
| log Brent | -3.33 | 0.0137 | 22 | -3.43 |
| log WTI | -3.30 | 0.0150 | 21 | -3.43 |
| Spread | -4.02 | 0.0013 | 25 | -3.43 |

Engle-Granger (log Brent on log WTI): stat -3.90, p-value 0.0099.

## Ornstein-Uhlenbeck calibration (daily steps)

| Period | Obs | Mean | Std | kappa /day | Half-life (days) | theta | sigma /sqrt(day) |
|---|---|---|---|---|---|---|---|
| Full sample | 2493 | 4.10 | 2.72 | 0.0633 | 10.9 | 4.14 | 0.965 |
| 2016 - 2019 | 993 | 4.31 | 3.39 | 0.0400 | 17.4 | 4.47 | 0.954 |
| 2020 - May 2023 | 839 | 3.82 | 2.55 | 0.0887 | 7.8 | 3.79 | 1.073 |
| Jun 2023 - Feb 2026 | 661 | 4.12 | 1.45 | 0.1711 | 4.1 | 4.14 | 0.855 |

## Z-score backtest (1,000 bbl of spread)

Rule: 252-day z-score, enter at +/-2.0, exit at 0.0, cost 0.02 USD/bbl per position change.

| Metric | Next-close execution | Same-close execution |
|---|---|---|
| Sharpe ratio | 0.66 | 1.01 |
| P&L per year (USD) | 6,895 | 10,622 |
| Max drawdown (USD) | -9,130 | -9,130 |
| Trades | 27 | 27 |
| Hit rate | 0.88 | 1.00 |
| Avg holding (days) | 33.6 | 33.6 |
| Time in market | 0.40 | 0.40 |

### Sharpe ratio sensitivity, next-close execution (rows: window, columns: entry z)

| Window | 1.5 | 2.0 | 2.5 |
|---|---|---|---|
| 20 | 0.31 | 0.26 | 0.13 |
| 60 | 0.71 | 0.76 | 0.50 |
| 126 | 0.60 | 0.54 | 0.53 |
| 252 | 0.54 | 0.66 | 0.64 |

### Same grid, same-close execution

| Window | 1.5 | 2.0 | 2.5 |
|---|---|---|---|
| 20 | 1.98 | 1.70 | 1.28 |
| 60 | 1.55 | 1.54 | 1.09 |
| 126 | 1.41 | 1.32 | 1.15 |
| 252 | 1.07 | 1.01 | 0.81 |

## Options on the spread, 21 trading days to expiry

Spread on 2026-02-11: 6.72 USD/bbl. Normal volatility (60-day realised): 10.21 USD/bbl/sqrt(yr). Brent vol 31.1%, WTI vol 27.6%, correlation 0.875. OU since 2023-06-01: half-life 4.1 days, theta 4.14; expected spread at expiry 4.21 (sd 1.46) versus a random-walk sd of 2.95, i.e. an OU-consistent normal vol of 5.06 instead of 10.21. All prices use today's spread as the forward. Discount rate 4% (assumed).

| Option | Random-walk vol (Bachelier) | Two legs (Kirk) | OU-consistent vol (Bachelier) |
|---|---|---|---|
| put 6.50 | 1.066 | 1.139 | 0.478 |
| put 5.00 | 0.509 | 0.556 | 0.086 |
| call 8.50 | 0.492 | 0.577 | 0.079 |

Strategies priced with the random-walk vol (cost) and the OU-consistent vol:

| Strategy | Cost (random-walk vol) | Value (OU vol) | Break-even(s) | Max profit | Max loss |
|---|---|---|---|---|---|
| Bear put spread | 0.557 | 0.392 | 5.94 | 0.94 | -0.557 |
| Long strangle | 1.001 | 0.164 | 4.00 / 9.50 | open-ended | -1.001 |
