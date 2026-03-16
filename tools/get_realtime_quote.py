# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""get_realtime_quote — fetch real-time stock quote.

Dependencies (within tools/):
  tools/data_layer.py  — Tencent Finance (A/HK) & yfinance (US) layer

Depended on by:
  tools/analyze_trend.py

Usage:
  uv run tools/get_realtime_quote.py TICKER
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def get_realtime_quote(ticker: str) -> Dict[str, Any]:
    """Fetch real-time stock quote (A-share / HK / US).

    A-share & HK via Tencent Finance, US/Global via yfinance.

    Args:
        ticker: Stock code — ``600519`` (A-share), ``1810.HK``, ``AAPL``

    Returns:
        Dict with market-dependent keys. Common keys include:
        ``name, price, change_pct, volume, pe, pb``
    """
    from tools._providers import fetch_realtime
    return fetch_realtime(ticker)


def main() -> None:
    parser = argparse.ArgumentParser(description="get_realtime_quote tool")
    parser.add_argument("ticker", help="Stock code (600519 / AAPL / 1810.HK)")
    args = parser.parse_args()
    result = get_realtime_quote(args.ticker)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
