"""Core scan: build universe -> fetch pre-market data -> filter -> attach catalysts."""

from __future__ import annotations

import logging
from datetime import datetime

from . import yahoo
from .benzinga import BenzingaClient, one_sentence
from .config import ScannerConfig

log = logging.getLogger(__name__)

NO_CATALYST = "No recent news catalyst found."


def passes_filters(snap: yahoo.PremarketSnapshot, cfg: ScannerConfig) -> bool:
    return (
        snap.gap_pct > cfg.min_gap_pct
        and snap.price > cfg.min_price
        and snap.premarket_volume > cfg.min_premarket_volume
    )


def find_catalyst(ticker: str, cfg: ScannerConfig, client: BenzingaClient | None, today) -> dict:
    if client:
        news = client.catalyst(ticker, cfg.news_lookback_days, today)
        if news:
            return {**news, "source": "Benzinga"}
    headline = yahoo.yahoo_headline(ticker)
    if headline:
        return {"sentence": one_sentence(headline), "headline": headline, "url": None,
                "published": None, "source": "Yahoo Finance"}
    return {"sentence": NO_CATALYST, "headline": None, "url": None, "published": None, "source": None}


def run_scan(cfg: ScannerConfig | None = None, now: datetime | None = None) -> dict:
    cfg = cfg or ScannerConfig()
    now = (now or datetime.now(yahoo.NY)).astimezone(yahoo.NY)

    names = yahoo.screen_tickers(cfg.screens, cfg.screen_size)
    for t in yahoo.load_watchlist(cfg.watchlist_path):
        names.setdefault(t, None)
    tickers = sorted(names)
    log.info("Scanning %d candidate tickers", len(tickers))

    snapshots = yahoo.fetch_snapshots(tickers, names, now=now)
    hits = sorted((s for s in snapshots if passes_filters(s, cfg)), key=lambda s: s.gap_pct, reverse=True)
    log.info("%d of %d tickers with pre-market data passed filters", len(hits), len(snapshots))

    if not cfg.benzinga_api_key:
        log.warning("BENZINGA_API_KEY not set - falling back to Yahoo Finance headlines for catalysts")
    client = BenzingaClient(cfg.benzinga_api_key) if cfg.benzinga_api_key else None

    stocks = []
    for s in hits:
        cat = find_catalyst(s.ticker, cfg, client, now.date())
        stocks.append({
            "ticker": s.ticker,
            "name": s.name,
            "price": round(s.price, 2),
            "previous_close": round(s.previous_close, 2),
            "gap_pct": s.gap_pct,
            "premarket_volume": s.premarket_volume,
            "catalyst": cat["sentence"],
            "catalyst_source": cat["source"],
            "catalyst_headline": cat["headline"],
            "catalyst_url": cat["url"],
            "catalyst_published": cat["published"],
        })

    return {
        "scan_date": now.date().isoformat(),
        "generated_at": now.isoformat(timespec="seconds"),
        "criteria": {
            "min_gap_pct": cfg.min_gap_pct,
            "min_price": cfg.min_price,
            "min_premarket_volume": cfg.min_premarket_volume,
        },
        "universe_size": len(tickers),
        "match_count": len(stocks),
        "stocks": stocks,
    }
