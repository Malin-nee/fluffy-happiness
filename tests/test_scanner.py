import json
from datetime import date, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from premarket_scanner import scanner, yahoo
from premarket_scanner.benzinga import BenzingaClient, one_sentence
from premarket_scanner.config import ScannerConfig
from premarket_scanner.output import format_table, save_json

NOW = datetime(2026, 11, 4, 8, 45, tzinfo=yahoo.NY)
DAY = NOW.date()


def daily_frame(closes):
    idx = pd.to_datetime(["2026-10-30", "2026-11-02", "2026-11-03"][-len(closes):])
    return pd.DataFrame({"Close": closes}, index=idx)


def intraday_frame(rows):
    """rows: list of (ny_time 'HH:MM', close, volume) on DAY."""
    idx = pd.DatetimeIndex([pd.Timestamp(f"2026-11-04 {t}", tz=yahoo.NY) for t, _, _ in rows]).tz_convert("UTC")
    return pd.DataFrame({"Close": [r[1] for r in rows], "Volume": [r[2] for r in rows]}, index=idx)


def multi(frames):
    return pd.concat(frames, axis=1, keys=list(frames), sort=True) if frames else pd.DataFrame()


def test_previous_close_ignores_today_row():
    df = pd.DataFrame({"Close": [10.0, 11.0, 99.0]}, index=pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04"]))
    assert yahoo.previous_close(df, DAY) == 11.0


def test_premarket_bars_excludes_regular_session():
    df = intraday_frame([("04:00", 1, 100), ("09:29", 2, 200), ("09:30", 3, 300)])
    bars = yahoo.premarket_bars(df, DAY)
    assert list(bars["Volume"]) == [100, 200]


def test_fetch_snapshots(monkeypatch):
    daily = multi({"AAA": daily_frame([9.0, 10.0]), "BBB": daily_frame([4.0, 4.0])})
    intra = multi({
        "AAA": intraday_frame([("07:00", 10.5, 30_000), ("08:44", 11.2, 40_000)]),
        "BBB": intraday_frame([("08:00", 4.1, 10_000)]),
    })
    calls = iter([daily, intra])
    monkeypatch.setattr(yahoo.yf, "download", lambda *a, **k: next(calls))
    snaps = {s.ticker: s for s in yahoo.fetch_snapshots(["AAA", "BBB"], now=NOW)}
    assert snaps["AAA"].price == 11.2
    assert snaps["AAA"].gap_pct == 12.0
    assert snaps["AAA"].premarket_volume == 70_000
    assert snaps["BBB"].gap_pct == 2.5


@pytest.mark.parametrize("snap,ok", [
    (yahoo.PremarketSnapshot("A", 11.2, 10, 12.0, 70_000), True),
    (yahoo.PremarketSnapshot("B", 2.5, 2, 25.0, 900_000), False),   # price too low
    (yahoo.PremarketSnapshot("C", 11.0, 10.6, 3.8, 900_000), False),  # gap too small
    (yahoo.PremarketSnapshot("D", 11.2, 10, 12.0, 50_000), False),  # volume not > 50k
])
def test_filters(snap, ok):
    assert scanner.passes_filters(snap, ScannerConfig(min_gap_pct=5, min_price=3, min_premarket_volume=50_000)) is ok


def test_one_sentence():
    assert one_sentence("Acme Inc. Reports Q3 Beat. Shares jump in premarket.") == "Acme Inc. Reports Q3 Beat."
    assert one_sentence("<p>FDA approves drug &amp; more</p>") == "FDA approves drug & more."
    assert one_sentence("") == ""


def test_benzinga_catalyst():
    session = MagicMock()
    session.get.return_value.json.return_value = [
        {"title": "XYZ Shares Soar After FDA Approval", "url": "https://benzinga.com/x", "created": "Wed, 04 Nov 2026"}
    ]
    cat = BenzingaClient("KEY", session=session).catalyst("XYZ", today=DAY)
    assert cat["sentence"] == "XYZ Shares Soar After FDA Approval."
    params = session.get.call_args.kwargs["params"]
    assert params["tickers"] == "XYZ" and params["token"] == "KEY" and params["dateFrom"] == "2026-11-01"


def test_run_scan_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setattr(yahoo, "screen_tickers", lambda *a: {"AAA": "Alpha", "BBB": "Beta", "CCC": "Gamma"})
    monkeypatch.setattr(yahoo, "fetch_snapshots", lambda tickers, names, now: [
        yahoo.PremarketSnapshot("AAA", 11.2, 10, 12.0, 70_000, "Alpha"),
        yahoo.PremarketSnapshot("BBB", 4.1, 4, 2.5, 10_000, "Beta"),
        yahoo.PremarketSnapshot("CCC", 6.6, 5.5, 20.0, 400_000, "Gamma"),
    ])
    monkeypatch.setattr(BenzingaClient, "catalyst", lambda self, t, *a: {
        "sentence": f"{t} news.", "headline": f"{t} news", "url": None, "published": None})
    cfg = ScannerConfig(benzinga_api_key="KEY", watchlist_path=tmp_path / "none.txt", output_dir=tmp_path)
    result = scanner.run_scan(cfg, now=NOW)

    assert [s["ticker"] for s in result["stocks"]] == ["CCC", "AAA"]  # sorted by gap desc
    assert result["stocks"][0]["catalyst_source"] == "Benzinga"
    path = save_json(result, tmp_path)
    assert path.name == "premarket_2026-11-04.json"
    assert json.loads(path.read_text())["match_count"] == 2
    table = format_table(result)
    assert "CCC" in table and "+20.00%" in table and "$6.60" in table
