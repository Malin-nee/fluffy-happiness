"""Scanner settings. Every value can be overridden with an environment variable."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


DEFAULT_SCREENS = ("day_gainers", "small_cap_gainers", "most_actives", "aggressive_small_caps")


@dataclass
class ScannerConfig:
    min_gap_pct: float = field(default_factory=lambda: _env_float("SCANNER_MIN_GAP_PCT", 5.0))
    min_price: float = field(default_factory=lambda: _env_float("SCANNER_MIN_PRICE", 3.0))
    min_premarket_volume: int = field(default_factory=lambda: _env_int("SCANNER_MIN_PM_VOLUME", 50_000))
    # Yahoo Finance predefined screeners used to build the candidate universe.
    screens: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            s.strip() for s in os.getenv("SCANNER_SCREENS", ",".join(DEFAULT_SCREENS)).split(",") if s.strip()
        )
    )
    screen_size: int = field(default_factory=lambda: _env_int("SCANNER_SCREEN_SIZE", 100))
    # Optional extra tickers, one per line (lines starting with # are ignored).
    watchlist_path: Path = field(default_factory=lambda: Path(os.getenv("SCANNER_WATCHLIST", "watchlist.txt")))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("SCANNER_OUTPUT_DIR", "results")))
    benzinga_api_key: str | None = field(default_factory=lambda: os.getenv("BENZINGA_API_KEY") or None)
    # How far back (days) to look for a news catalyst.
    news_lookback_days: int = field(default_factory=lambda: _env_int("SCANNER_NEWS_LOOKBACK_DAYS", 3))
