# /// script
# requires-python = ">=3.10"
# dependencies = ['requests']
# ///
"""is_stock_hot — check if a stock is a leading stock in today's top sectors.

A stock is considered "hot" if its name appears as the leading_stock
in the top 10 industry boards OR top 10 concept boards on East Money.

Data sources (in priority order):
  1. East Money push2 API via requests  — comprehensive, real-time
  2. Sina Finance via urllib             — fallback, ~50 traditional sectors

Depended on by:
  scripts/strategy_manager.py (detect_regime → sector_hot)
  scripts/pipeline.py (_run_strategy)

Usage:
  uv run tools/is_stock_hot.py STOCK_NAME
  uv run tools/is_stock_hot.py 贵州茅台
  uv run tools/is_stock_hot.py 农发种业
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from typing import Any, Dict, List

MAX_RETRIES = 3
RETRY_BACKOFF = (1, 2, 4)

_EM_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_EM_BOARD_FS = {
    "industry": "m:90+t:2+f:!50",
    "concept": "m:90+t:3+f:!50",
}
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
    "Accept": "*/*",
}

_SINA_URL = "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php"


# ---------------------------------------------------------------------------
# Internal: fetch sector rankings
# ---------------------------------------------------------------------------

def _fetch_em_top(board_type: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch top sectors from East Money push2 API."""
    try:
        import requests as _req
    except ImportError:
        return []

    fs = _EM_BOARD_FS.get(board_type, _EM_BOARD_FS["industry"])
    params = {
        "np": 1, "fltt": 2, "invt": 2, "fs": fs,
        "fields": "f3,f14,f128",
        "fid": "f3", "pn": 1, "pz": limit, "po": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = _req.get(
                _EM_URL, params=params, headers=_EM_HEADERS, timeout=10)
            r.raise_for_status()
            results: List[Dict[str, Any]] = []
            for item in r.json().get("data", {}).get("diff", []):
                try:
                    chg = round(float(item.get("f3", 0)), 2)
                except (TypeError, ValueError):
                    chg = 0.0
                results.append({
                    "sector_name": str(item.get("f14", "")),
                    "change_percent": chg,
                    "leading_stock": str(item.get("f128", "")),
                    "board_type": board_type,
                })
            return results
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                print(f"[is_stock_hot/em/{board_type}] {e}", file=sys.stderr)
    return []


def _fetch_sina_top(limit: int = 10) -> List[Dict[str, Any]]:
    """Fallback: Sina Finance (~50 traditional industry sectors)."""
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(_SINA_URL, headers={
                "User-Agent": "Mozilla/5.0 (compatible; StockAnalysis/1.0)",
                "Referer": "https://finance.sina.com.cn/",
            })
            resp = urllib.request.urlopen(req, timeout=10).read().decode(
                "gbk", errors="replace")
            m = re.search(r"=\s*(\{.+\})", resp, re.DOTALL)
            if not m:
                return []
            raw: dict = json.loads(m.group(1))
            items: List[Dict[str, Any]] = []
            for v in raw.values():
                parts = v.split(",")
                if len(parts) < 13:
                    continue
                try:
                    chg = round(float(parts[5]), 2)
                except (ValueError, IndexError):
                    chg = 0.0
                items.append({
                    "sector_name": parts[1],
                    "change_percent": chg,
                    "leading_stock": parts[12],
                    "board_type": "industry",
                })
            items.sort(key=lambda x: x["change_percent"], reverse=True)
            return items[:limit]
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                print(f"[is_stock_hot/sina] {e}", file=sys.stderr)
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_stock_hot(stock_name: str) -> Dict[str, Any]:
    """Check if a stock is a leading stock in today's top sectors.

    Fetches the top 10 industry boards and top 10 concept boards.
    If ``stock_name`` appears as the ``leading_stock`` of any of them,
    the stock is considered "hot".

    Args:
        stock_name: Stock name (e.g. ``"贵州茅台"``, ``"农发种业"``).

    Returns:
        Dict with keys:
        - ``is_hot``: bool
        - ``matched_sectors``: list of matched sector dicts
        - ``hot_sectors``: full list of top sectors (industry + concept)
    """
    if not stock_name:
        return {"is_hot": False, "matched_sectors": [], "hot_sectors": []}

    industry = _fetch_em_top("industry", 10)
    concept = _fetch_em_top("concept", 10)

    if not industry and not concept:
        industry = _fetch_sina_top(10)

    hot_sectors = industry + concept
    matched = [
        s for s in hot_sectors
        if stock_name in s.get("leading_stock", "")
    ]
    return {
        "is_hot": len(matched) > 0,
        "matched_sectors": matched,
        "hot_sectors": hot_sectors,
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="is_stock_hot tool")
    parser.add_argument("stock_name", help="Stock name (e.g. 贵州茅台)")
    args = parser.parse_args()
    result = is_stock_hot(args.stock_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
