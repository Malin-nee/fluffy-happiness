"""CLI: python -m premarket_scanner [options]"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import ScannerConfig
from .output import format_table, save_json
from .scanner import run_scan


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pre-market gap scanner (Yahoo Finance + Benzinga)")
    p.add_argument("--min-gap", type=float, help="minimum gap %% vs previous close (default 5)")
    p.add_argument("--min-price", type=float, help="minimum share price in USD (default 3)")
    p.add_argument("--min-volume", type=int, help="minimum pre-market volume (default 50000)")
    p.add_argument("--watchlist", type=Path, help="file with extra tickers, one per line")
    p.add_argument("--output-dir", type=Path, help="directory for daily JSON files (default results/)")
    p.add_argument("--no-save", action="store_true", help="print only, do not write JSON")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    cfg = ScannerConfig()
    if args.min_gap is not None:
        cfg.min_gap_pct = args.min_gap
    if args.min_price is not None:
        cfg.min_price = args.min_price
    if args.min_volume is not None:
        cfg.min_premarket_volume = args.min_volume
    if args.watchlist:
        cfg.watchlist_path = args.watchlist
    if args.output_dir:
        cfg.output_dir = args.output_dir

    result = run_scan(cfg)
    print(format_table(result))
    if not args.no_save:
        print(f"Saved: {save_json(result, cfg.output_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
