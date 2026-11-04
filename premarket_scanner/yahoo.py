"""Yahoo Finance access: candidate tickers, previous close and pre-market bars."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


@dataclass
class PremarketSnapshot:
    ticker: str
    price: float
    previous_close: float
    gap_pct: float
    premarket_volume: int
    name: str | None = None


def screen_tickers(screens: Iterable[str], size: int = 100) -> dict[str, str | None]:
    """Return {ticker: company name} from Yahoo Finance predefined screeners."""
    found: dict[str, str | None] = {}
    for screen in screens:
        try:
            result = yf.screen(screen, count=size)
        except Exception as exc:  # network / schema errors shouldn't kill the run
            log.warning("Yahoo screener %r failed: %s", screen, exc)
            continue
        for quote in (result or {}).get("quotes", []):
            symbol = quote.get("symbol")
            if symbol and quote.get("quoteType", "EQUITY") == "EQUITY":
                found.setdefault(symbol, quote.get("shortName") or quote.get("longName"))
    return found


def load_watchlist(path: Path) -> list[str]:
    if not path.exists():
        return []
    tickers = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip().upper()
        if line and _TICKER_RE.match(line):
            tickers.append(line)
    return tickers


def _ticker_frame(df: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Extract one ticker's OHLCV frame from a (possibly multi-index) yf.download result."""
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        for level in range(df.columns.nlevels):
            if ticker in df.columns.get_level_values(level):
                sub = df.xs(ticker, axis=1, level=level)
                return sub.dropna(how="all")
        return None
    return df.dropna(how="all")


def _to_ny(index: pd.Index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(NY)


def previous_close(daily: pd.DataFrame | None, session_day: date) -> float | None:
    """Last daily close strictly before the trading session being scanned."""
    if daily is None or daily.empty or "Close" not in daily:
        return None
    closes = daily["Close"].dropna()
    days = pd.DatetimeIndex(closes.index).date
    closes = closes[days < session_day]
    return float(closes.iloc[-1]) if not closes.empty else None


def premarket_bars(intraday: pd.DataFrame | None, session_day: date) -> pd.DataFrame | None:
    """1-minute bars of `session_day` that print before the 09:30 ET open."""
    if intraday is None or intraday.empty:
        return None
    ny_index = _to_ny(intraday.index)
    mask = (ny_index.date == session_day) & (ny_index.time < MARKET_OPEN)
    bars = intraday[mask]
    return bars if not bars.empty else None


def fetch_snapshots(
    tickers: list[str], names: dict[str, str | None] | None = None, now: datetime | None = None
) -> list[PremarketSnapshot]:
    """Download pre-market data for all tickers in two bulk Yahoo requests."""
    if not tickers:
        return []
    names = names or {}
    session_day = (now or datetime.now(NY)).astimezone(NY).date()
    common = dict(group_by="ticker", auto_adjust=False, progress=False, threads=True)
    daily = yf.download(tickers, period="10d", interval="1d", **common)
    intraday = yf.download(tickers, period="1d", interval="1m", prepost=True, **common)

    snapshots = []
    for ticker in tickers:
        prev = previous_close(_ticker_frame(daily, ticker), session_day)
        bars = premarket_bars(_ticker_frame(intraday, ticker), session_day)
        if not prev or bars is None:
            continue
        last = bars["Close"].dropna()
        if last.empty:
            continue
        price = float(last.iloc[-1])
        volume = int(bars["Volume"].fillna(0).sum())
        snapshots.append(
            PremarketSnapshot(
                ticker=ticker,
                price=round(price, 4),
                previous_close=round(prev, 4),
                gap_pct=round((price - prev) / prev * 100, 2),
                premarket_volume=volume,
                name=names.get(ticker),
            )
        )
    return snapshots


def yahoo_headline(ticker: str) -> str | None:
    """Most recent Yahoo Finance headline (fallback when Benzinga has nothing)."""
    try:
        items = yf.Ticker(ticker).news or []
    except Exception as exc:
        log.debug("Yahoo news failed for %s: %s", ticker, exc)
        return None
    for item in items:
        content = item.get("content", item)
        title = content.get("title")
        if title:
            return title
    return None
