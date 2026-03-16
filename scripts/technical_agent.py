# /// script
# requires-python = ">=3.10"
# dependencies = ['yfinance', 'pandas', 'numpy', 'scipy']
# ///
"""
Technical Agent — fetches market data and computes technical indicators.

Commands:
  fetch TICKER      Fetch quote + history, compute MA/RSI/volume, output JSON
  schema            Print the expected LLM output schema

Data sources:
  - Tencent Finance (qt.gtimg.cn): real-time A-share quote (no API key)
  - yfinance: historical OHLCV for all markets (A-share, US, HK)
"""

import io
import json
import sys
import argparse
from pathlib import Path

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

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


def _is_a_share(ticker: str) -> bool:
    clean = ticker.split(".")[0]
    return clean.isdigit() and len(clean) == 6


def _fetch_history_tencent(ticker: str, days: int = 120) -> pd.DataFrame:
    """Fetch A-share history via Tencent Finance K-line API (primary source)."""
    from data_provider import fetch_a_share_history
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


def _fetch_history_yfinance(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Fetch history via yfinance (fallback source)."""
    import yfinance as yf
    from data_provider import resolve_ticker
    yf_ticker = resolve_ticker(ticker)["yahoo"] if _is_a_share(ticker) else ticker
    df = yf.download(yf_ticker, period=period, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Close"])


def _is_hk_stock(ticker: str) -> bool:
    return ticker.strip().upper().endswith(".HK")


def _fetch_history(ticker: str) -> pd.DataFrame:
    """Fetch historical OHLCV. Tencent Finance first for A-shares/HK, yfinance as fallback."""
    if _is_a_share(ticker) or _is_hk_stock(ticker):
        df = _fetch_history_tencent(ticker)
        if not df.empty and len(df) >= 5:
            return df
        print("[technical] Tencent K-line empty, falling back to yfinance",
              file=sys.stderr)
    return _fetch_history_yfinance(ticker)


def _fetch_realtime(stock_code: str) -> dict:
    """Fetch real-time quote via Tencent Finance (A-share/HK) or yfinance (US/Global)."""
    try:
        from data_provider import (fetch_a_share_realtime, fetch_hk_realtime,
                                   fetch_us_stock_realtime, is_a_share, is_hk_stock, resolve_ticker)
        if is_a_share(stock_code):
            return fetch_a_share_realtime(stock_code)
        elif is_hk_stock(stock_code):
            return fetch_hk_realtime(stock_code)
        else:
            tickers = resolve_ticker(stock_code)
            return fetch_us_stock_realtime(tickers["yahoo"])
    except Exception as e:
        print(f"[realtime quote] {e}", file=sys.stderr)
    return {}


def compute_ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def compute_rsi(series: pd.Series, periods: int = 14) -> float:
    if len(series) < periods + 1:
        return 50.0
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    rs = ma_up / ma_down
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(np.squeeze(val)) if pd.notna(val) else 50.0


def compute_technical_data(df: pd.DataFrame, realtime: dict) -> dict:
    """Compute all technical indicators from OHLCV dataframe."""
    if df.empty or len(df) < 5:
        return {"error": "Insufficient data"}

    close = df["Close"]
    volume = df["Volume"]
    latest = df.iloc[-1]

    current_price = float(np.squeeze(latest["Close"]))
    ma5 = float(np.squeeze(compute_ma(close, 5).iloc[-1])) if len(close) >= 5 else current_price
    ma10 = float(np.squeeze(compute_ma(close, 10).iloc[-1])) if len(close) >= 10 else current_price
    ma20 = float(np.squeeze(compute_ma(close, 20).iloc[-1])) if len(close) >= 20 else current_price

    if ma5 >= ma10 >= ma20:
        ma_alignment = "bullish"
    elif ma5 <= ma10 <= ma20:
        ma_alignment = "bearish"
    else:
        ma_alignment = "neutral"

    bias_ma5 = (current_price - ma5) / ma5 * 100 if ma5 > 0 else 0
    bias_ma20 = (current_price - ma20) / ma20 * 100 if ma20 > 0 else 0

    rsi = compute_rsi(close)

    vol_ma5 = float(np.squeeze(volume.rolling(5).mean().iloc[-1])) if len(volume) >= 5 else 0
    vol_ma20 = float(np.squeeze(volume.rolling(20).mean().iloc[-1])) if len(volume) >= 20 else 0
    current_vol = float(np.squeeze(latest["Volume"]))
    volume_ratio = current_vol / vol_ma5 if vol_ma5 > 0 else 1.0
    vol_ratio_20 = current_vol / vol_ma20 if vol_ma20 > 0 else 1.0

    if volume_ratio > 1.8:
        volume_status = "heavy"
    elif volume_ratio < 0.6:
        volume_status = "light"
    else:
        volume_status = "normal"

    trend_score = 50.0
    if ma_alignment == "bullish":
        trend_score += 15
    elif ma_alignment == "bearish":
        trend_score -= 15
    if rsi > 60:
        trend_score += min(20, (rsi - 50) * 0.5)
    elif rsi < 40:
        trend_score -= min(20, (50 - rsi) * 0.5)
    if volume_status == "heavy" and bias_ma5 > 0:
        trend_score += 5
    trend_score = max(0, min(100, trend_score))

    high_20 = float(np.squeeze(df["High"].tail(20).max()))
    low_20 = float(np.squeeze(df["Low"].tail(20).min()))

    from scipy.signal import argrelextrema
    close_vals = close.values
    supports, resistances = [], []
    if len(close_vals) >= 10:
        min_idx = argrelextrema(close_vals, np.less_equal, order=5)[0]
        max_idx = argrelextrema(close_vals, np.greater_equal, order=5)[0]
        supports = [float(np.squeeze(close_vals[i])) for i in min_idx[-3:] if close_vals[i] < current_price]
        resistances = [float(np.squeeze(close_vals[i])) for i in max_idx[-3:] if close_vals[i] > current_price]

    support = min(supports) if supports else low_20
    resistance = max(resistances) if resistances else high_20

    body = abs(float(np.squeeze(latest["Close"])) - float(np.squeeze(latest["Open"])))
    total_range = float(np.squeeze(latest["High"])) - float(np.squeeze(latest["Low"]))
    upper_shadow = float(np.squeeze(latest["High"])) - max(float(np.squeeze(latest["Close"])), float(np.squeeze(latest["Open"])))
    lower_shadow = min(float(np.squeeze(latest["Close"])), float(np.squeeze(latest["Open"]))) - float(np.squeeze(latest["Low"]))

    pattern = "none"
    if total_range > 0:
        if lower_shadow > 2 * body and lower_shadow > upper_shadow:
            pattern = "hammer"
        elif upper_shadow > 2 * body and upper_shadow > lower_shadow:
            pattern = "shooting_star"
        elif volume_ratio > 1.8 and body / total_range > 0.6:
            change = (float(np.squeeze(latest["Close"])) - float(np.squeeze(df.iloc[-2]["Close"]))) / float(np.squeeze(df.iloc[-2]["Close"])) * 100
            if change > 3:
                pattern = "bullish_breakout"
            elif change < -3:
                pattern = "bearish_engulfing"

    recent_5 = df.tail(5)
    recent_history = []
    for _, row in recent_5.iterrows():
        recent_history.append({
            "date": str(row.name.date()) if hasattr(row.name, "date") else str(row.name),
            "open": round(float(np.squeeze(row["Open"])), 2),
            "high": round(float(np.squeeze(row["High"])), 2),
            "low": round(float(np.squeeze(row["Low"])), 2),
            "close": round(float(np.squeeze(row["Close"])), 2),
            "volume": int(float(np.squeeze(row["Volume"]))),
        })

    return {
        "current_price": round(current_price, 2),
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "ma_alignment": ma_alignment,
        "bias_ma5": round(bias_ma5, 2),
        "bias_ma20": round(bias_ma20, 2),
        "rsi": round(rsi, 1),
        "volume_ratio": round(volume_ratio, 2),
        "vol_ratio_20d": round(vol_ratio_20, 2),
        "volume_status": volume_status,
        "trend_score": round(trend_score),
        "high_20d": round(high_20, 2),
        "low_20d": round(low_20, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "pattern": pattern,
        "realtime_quote": realtime,
        "recent_history": recent_history,
    }


def cmd_fetch(args):
    ticker = args.ticker.strip()
    realtime = _fetch_realtime(ticker)
    df = _fetch_history(ticker)
    result = compute_technical_data(df, realtime)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_schema(_args):
    print(json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Technical Agent — data fetch + indicators")
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
