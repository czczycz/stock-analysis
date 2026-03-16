# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""get_daily_history — fetch historical OHLCV K-line data.

Dependencies (within tools/):
  tools/data_layer.py  — Tencent Finance & yfinance data layer

Depended on by:
  tools/analyze_trend.py

Usage:
  uv run tools/get_daily_history.py TICKER [--days 120]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def get_daily_history(ticker: str, days: int = 120) -> List[Dict[str, Any]]:
    """Fetch daily OHLCV K-line data for any market.

    Priority: Tencent Finance (A-share / HK) → yfinance (all markets).

    Args:
        ticker: Stock code — ``600519`` (A-share), ``1810.HK``, ``AAPL``
        days:   Number of trading days to retrieve (default 120)

    Returns:
        List of dicts, each with keys:
        ``date, open, high, low, close, volume``
    """
    from tools._providers import is_a_share, is_hk_stock, fetch_a_share_history

    if is_a_share(ticker) or is_hk_stock(ticker):
        records = fetch_a_share_history(ticker, days=days)
        if records:
            return records

    try:
        import pandas as pd
        import yfinance as yf
        from tools._providers import resolve_ticker

        yf_ticker = (resolve_ticker(ticker)["yahoo"]
                     if is_a_share(ticker) else ticker)
        months = max(days // 20, 1)
        df = yf.download(yf_ticker, period=f"{months}mo", interval="1d",
                         progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        records: list = []
        for idx, row in df.iterrows():
            date_str = (idx.strftime("%Y-%m-%d")
                        if hasattr(idx, "strftime") else str(idx)[:10])
            records.append({
                "date": date_str,
                "open": round(float(row.get("Open", 0)), 2),
                "high": round(float(row.get("High", 0)), 2),
                "low": round(float(row.get("Low", 0)), 2),
                "close": round(float(row.get("Close", 0)), 2),
                "volume": int(float(row.get("Volume", 0))),
            })
        return records[-days:]
    except Exception as e:
        print(f"[get_daily_history] yfinance fallback failed: {e}",
              file=sys.stderr)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="get_daily_history tool")
    parser.add_argument("ticker", help="Stock code (600519 / AAPL / 1810.HK)")
    parser.add_argument("--days", type=int, default=120)
    args = parser.parse_args()
    result = get_daily_history(args.ticker, days=args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
