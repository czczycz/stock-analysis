# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare']
# ///
"""get_sector_rankings — A-share industry sector rankings by change percent.

Dependencies (upstream):
  akshare  — stock_board_industry_name_em()

Depended on by:
  (none — leaf tool consumed by strategies / pipeline)

Usage:
  uv run tools/get_sector_rankings.py [--limit 10]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List


def get_sector_rankings(limit: int = 10) -> List[Dict[str, Any]]:
    """Get A-share industry sector rankings by change percent.

    Uses AkShare ``stock_board_industry_name_em``.

    Args:
        limit: Number of top sectors to return (default 10)

    Returns:
        List of dicts with keys:
        ``sector_name, change_percent, turnover_rate, leading_stock``
        For non-A-share markets, returns an empty list.
    """
    try:
        import akshare as ak

        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return []

        col_map = {
            "板块名称": "sector_name",
            "涨跌幅": "change_percent",
            "换手率": "turnover_rate",
            "领涨股票": "leading_stock",
        }
        available = {k: v for k, v in col_map.items() if k in df.columns}

        results: List[Dict[str, Any]] = []
        for _, row in df.head(limit).iterrows():
            entry: Dict[str, Any] = {}
            for cn, en in available.items():
                val = row.get(cn)
                if en in ("change_percent", "turnover_rate"):
                    try:
                        val = round(float(val), 2)
                    except (TypeError, ValueError):
                        val = 0.0
                else:
                    val = str(val) if val is not None else ""
                entry[en] = val
            results.append(entry)

        return results
    except Exception as e:
        print(f"[get_sector_rankings] {e}", file=sys.stderr)
        return []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="get_sector_rankings tool")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    result = get_sector_rankings(limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
