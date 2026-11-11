# Data

| File | Series | Unit | First date |
|---|---|---|---|
| `brent_spot_daily.csv` | Europe Brent spot price FOB (EIA series RBRTE) | USD per barrel | 20 May 1987 |
| `wti_spot_daily.csv` | Cushing, OK WTI spot price FOB (EIA series RWTC) | USD per barrel | 2 January 1986 |

**Source.** U.S. Energy Information Administration, *Petroleum & Other Liquids, Spot Prices*, retrieved on 11 November 2026 (last observation 3 November 2026) through the datahub.io [`oil-prices`](https://github.com/datasets/oil-prices) data package.

**Licence.** U.S. government publications are in the public domain; EIA asks users to cite the source. The data-package work is released under the Open Data Commons Public Domain Dedication and License (PDDL).

**Caveats.** Spot assessments, not exchange settlement prices. The two series follow different holiday calendars and must be joined on the date. WTI printed -36.98 USD/bbl on 20 April 2020.

Refresh with:

```bash
python scripts/update_data.py
```

The studies use fixed date windows, so a refresh only changes their results if EIA revises history.
