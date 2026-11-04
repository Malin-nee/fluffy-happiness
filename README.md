# Pre-market Stock Scanner (สแกนหุ้นก่อนตลาดเปิด)

Runs every weekday morning before the US market opens and finds stocks that are **gapping up** in pre-market:

| Filter | Default | Override |
|---|---|---|
| Gap vs previous close | **> 5%** | `--min-gap` / `SCANNER_MIN_GAP_PCT` |
| Price per share | **> $3** | `--min-price` / `SCANNER_MIN_PRICE` |
| Pre-market volume | **> 50,000 shares** | `--min-volume` / `SCANNER_MIN_PM_VOLUME` |

**Data sources**

- **Yahoo Finance** (via `yfinance`): candidate tickers from Yahoo's predefined screeners
  (`day_gainers`, `small_cap_gainers`, `most_actives`, `aggressive_small_caps`) plus `watchlist.txt`;
  previous close from daily bars; pre-market price and volume from 1-minute bars (04:00–09:30 ET).
  Gap % = (latest pre-market price − previous close) / previous close.
- **Benzinga News API**: newest story for each match from the last 3 days, cut down to one sentence.
  Needs `BENZINGA_API_KEY`. Without a key, or if Benzinga has no story, the scanner uses the latest
  Yahoo Finance headline instead, and the `catalyst_source` field says which one was used.

## Usage

```bash
pip install -r requirements.txt
export BENZINGA_API_KEY=your_key      # optional but recommended
python -m premarket_scanner           # print table + save results/premarket_YYYY-MM-DD.json
python -m premarket_scanner --min-gap 8 --no-save -v
```

Example output:

```
PRE-MARKET SCANNER  2026-11-04  (generated 2026-11-04T08:17:05-05:00)
Criteria: gap > 5.0% | price > $3.00 | pre-market volume > 50,000
Matches: 2 of 214 tickers scanned

Ticker       Price    Gap %      PM Vol  Catalyst
------------------------------------------------------------------------------------------
CCC          $6.60  +20.00%     400,000  Gamma Therapeutics Shares Soar After FDA Approval.
AAA         $11.20  +12.00%      70,000  Alpha Corp Raises Full-Year Guidance After Q3 Beat.
```

## Daily JSON file

Each run writes `results/premarket_<YYYY-MM-DD>.json` (date in US Eastern time):

```json
{
  "scan_date": "2026-11-04",
  "generated_at": "2026-11-04T08:17:05-05:00",
  "criteria": {"min_gap_pct": 5.0, "min_price": 3.0, "min_premarket_volume": 50000},
  "universe_size": 214,
  "match_count": 1,
  "stocks": [
    {
      "ticker": "CCC", "name": "Gamma", "price": 6.6, "previous_close": 5.5,
      "gap_pct": 20.0, "premarket_volume": 400000,
      "catalyst": "Gamma Therapeutics Shares Soar After FDA Approval.",
      "catalyst_source": "Benzinga", "catalyst_headline": "...", "catalyst_url": "...",
      "catalyst_published": "..."
    }
  ]
}
```

## Running it every morning

**GitHub Actions (included):** `.github/workflows/premarket-scan.yml` runs Mon–Fri at 12:17 UTC
(08:17 ET in summer, 07:17 ET in winter), commits the day's JSON to `results/`, and puts the table in
the run summary. Add your key under *Settings → Secrets and variables → Actions* as `BENZINGA_API_KEY`.
You can also start it by hand from the Actions tab.

**Local cron alternative** (machine set to ET):

```cron
15 8 * * 1-5 cd /path/to/fluffy-happiness && BENZINGA_API_KEY=xxx python3 -m premarket_scanner >> scan.log 2>&1
```

## Notes / limits

- Yahoo's screeners list *yesterday's* movers, so a stock that gaps on overnight news but wasn't
  active yesterday can be missed. Add tickers you care about to `watchlist.txt`.
- Yahoo's unofficial endpoints can rate-limit or change; failures are logged and the run continues.
- US market holidays aren't skipped; on those days the file simply has no matches.

## Tests

```bash
pip install pytest && python -m pytest -q
```
