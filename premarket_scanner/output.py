"""Console table + daily JSON file."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path


def format_table(result: dict, catalyst_width: int = 70) -> str:
    c = result["criteria"]
    header = (
        f"PRE-MARKET SCANNER  {result['scan_date']}  (generated {result['generated_at']})\n"
        f"Criteria: gap > {c['min_gap_pct']}% | price > ${c['min_price']:.2f} | "
        f"pre-market volume > {c['min_premarket_volume']:,}\n"
        f"Matches: {result['match_count']} of {result['universe_size']} tickers scanned\n"
    )
    if not result["stocks"]:
        return header + "\nNo stocks matched the criteria today.\n"

    cols = f"{'Ticker':<8}{'Price':>10}{'Gap %':>9}{'PM Vol':>12}  Catalyst"
    lines = [header, cols, "-" * (len(cols) + catalyst_width - 8)]
    indent = " " * 41
    for s in result["stocks"]:
        wrapped = textwrap.wrap(s["catalyst"], catalyst_width) or [""]
        lines.append(
            f"{s['ticker']:<8}{'$' + format(s['price'], ',.2f'):>10}{'+' + format(s['gap_pct'], '.2f') + '%':>9}"
            f"{s['premarket_volume']:>12,}  {wrapped[0]}"
        )
        lines.extend(indent + w for w in wrapped[1:])
    return "\n".join(lines) + "\n"


def save_json(result: dict, output_dir: Path) -> Path:
    """Write results/premarket_YYYY-MM-DD.json (one file per scan date)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"premarket_{result['scan_date']}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return path
