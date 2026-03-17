# /// script
# requires-python = ">=3.10"
# dependencies = ['yfinance', 'pandas', 'numpy', 'scipy']
# ///
"""
Technical Agent — CLI wrapper over tools.technical + tools.data_layer.

All core computation lives in ``tools/technical.py``.
Data fetching uses ``tools/data_layer.py`` and ``tools/get_daily_history.py``.

Commands:
  fetch TICKER      Fetch quote + history, compute MA/RSI/volume, output JSON
  schema            Print the expected LLM output schema
"""

import json
import sys
import argparse

from _bootstrap import bootstrap; bootstrap()  # noqa: E702

import pandas as pd

from tools.get_technical_indicators import (  # noqa: F401, E402
    compute_indicators_from_dataframe as compute_technical_data,
    compute_ma, compute_rsi,
)
from tools._providers import (  # noqa: E402
    is_a_share, is_hk_stock, resolve_ticker,
    fetch_a_share_history, fetch_realtime,
)

OUTPUT_SCHEMA = {
    "signal": "strong_buy|buy|hold|sell|strong_sell",
    "confidence": "float 0.0-1.0",
    "reasoning": "str — 2-3 sentence summary",
    "key_levels": {
        "support": "float",
        "resistance": "float",
        "stop_loss": "float",
    },
    "trend_score": "int 0-100",
    "ma_alignment": "bullish|neutral|bearish",
    "volume_status": "heavy|normal|light",
    "pattern": "str — detected pattern or none",
}


def _fetch_history_tencent(ticker: str, days: int = 120) -> pd.DataFrame:
    """Fetch A-share/HK history via Tencent Finance K-line API."""
    records = fetch_a_share_history(ticker, days=days)
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["date"])
    df.set_index("Date", inplace=True)
    df = df.rename(columns={"open": "Open", "close": "Close",
                             "high": "High", "low": "Low", "volume": "Volume"})
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Close"])


def _fetch_history_yfinance(ticker: str,
                            period: str = "6mo") -> pd.DataFrame:
    """Fetch history via yfinance (fallback source)."""
    import yfinance as yf
    yf_ticker = (resolve_ticker(ticker)["yahoo"]
                 if is_a_share(ticker) else ticker)
    df = yf.download(yf_ticker, period=period, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Close"])


def _fetch_history(ticker: str) -> pd.DataFrame:
    """Tencent Finance first for A-shares/HK, yfinance as fallback."""
    if is_a_share(ticker) or is_hk_stock(ticker):
        df = _fetch_history_tencent(ticker)
        if not df.empty and len(df) >= 5:
            return df
        print("[technical] Tencent K-line empty, falling back to yfinance",
              file=sys.stderr)
    return _fetch_history_yfinance(ticker)


def cmd_fetch(args):
    ticker = args.ticker.strip()
    realtime = fetch_realtime(ticker)
    df = _fetch_history(ticker)
    result = compute_technical_data(df, realtime)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_schema(_args):
    print(json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Technical Agent — data fetch + indicators")
    sub = parser.add_subparsers(dest="command")

    p_f = sub.add_parser("fetch", help="Fetch technical data for a ticker")
    p_f.add_argument("ticker", help="Stock ticker / code")

    sub.add_parser("schema", help="Print LLM output schema")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"fetch": cmd_fetch, "schema": cmd_schema}[args.command](args)


if __name__ == "__main__":
    main()
