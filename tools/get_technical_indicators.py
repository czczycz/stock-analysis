# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas', 'numpy', 'scipy']
# ///
"""get_technical_indicators — compute MA, RSI, support/resistance, trend status.

Dependencies (within tools/):
  tools/get_daily_history.py  — historical OHLCV data
  tools/get_realtime_quote.py — current price snapshot

Depended on by:
  scripts/pipeline.py, scripts/technical_agent.py, strategies (via required_tools)

Usage:
  uv run tools/get_technical_indicators.py TICKER [--days 120]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ---------------------------------------------------------------------------
# Pure computation helpers (no I/O)
# ---------------------------------------------------------------------------

def compute_ma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=window).mean()


def compute_rsi(series: pd.Series, periods: int = 14) -> float:
    """Relative Strength Index."""
    if len(series) < periods + 1:
        return 50.0
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True,
                        min_periods=periods).mean()
    rs = ma_up / ma_down
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(np.squeeze(val)) if pd.notna(val) else 50.0


def compute_indicators_from_dataframe(
    df: pd.DataFrame, realtime: dict,
) -> dict:
    """Compute all technical indicators from an OHLCV DataFrame.

    This is the pure-computation core. It takes pre-fetched data and
    returns a dict of indicators — no network calls.

    Args:
        df:       DataFrame with columns Open, High, Low, Close, Volume
                  and a DatetimeIndex.
        realtime: Real-time quote dict (attached to output as-is).

    Returns:
        Dict containing: current_price, ma5/10/20, ma_alignment,
        bias_ma5/20, rsi, volume_ratio, volume_status, trend_score,
        support, resistance, pattern, realtime_quote, recent_history.
    """
    if df.empty or len(df) < 5:
        return {"error": "Insufficient data"}

    close = df["Close"]
    volume = df["Volume"]
    latest = df.iloc[-1]

    current_price = float(np.squeeze(latest["Close"]))
    ma5 = (float(np.squeeze(compute_ma(close, 5).iloc[-1]))
           if len(close) >= 5 else current_price)
    ma10 = (float(np.squeeze(compute_ma(close, 10).iloc[-1]))
            if len(close) >= 10 else current_price)
    ma20 = (float(np.squeeze(compute_ma(close, 20).iloc[-1]))
            if len(close) >= 20 else current_price)

    if ma5 >= ma10 >= ma20:
        ma_alignment = "bullish"
    elif ma5 <= ma10 <= ma20:
        ma_alignment = "bearish"
    else:
        ma_alignment = "neutral"

    bias_ma5 = (current_price - ma5) / ma5 * 100 if ma5 > 0 else 0
    bias_ma20 = (current_price - ma20) / ma20 * 100 if ma20 > 0 else 0

    rsi = compute_rsi(close)

    vol_ma5 = (float(np.squeeze(volume.rolling(5).mean().iloc[-1]))
               if len(volume) >= 5 else 0)
    vol_ma20 = (float(np.squeeze(volume.rolling(20).mean().iloc[-1]))
                if len(volume) >= 20 else 0)
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
    supports: List[float] = []
    resistances: List[float] = []
    if len(close_vals) >= 10:
        min_idx = argrelextrema(close_vals, np.less_equal, order=5)[0]
        max_idx = argrelextrema(close_vals, np.greater_equal, order=5)[0]
        supports = [float(np.squeeze(close_vals[i]))
                    for i in min_idx[-3:] if close_vals[i] < current_price]
        resistances = [float(np.squeeze(close_vals[i]))
                       for i in max_idx[-3:] if close_vals[i] > current_price]

    support = min(supports) if supports else low_20
    resistance = max(resistances) if resistances else high_20

    body = abs(float(np.squeeze(latest["Close"]))
               - float(np.squeeze(latest["Open"])))
    total_range = (float(np.squeeze(latest["High"]))
                   - float(np.squeeze(latest["Low"])))
    upper_shadow = (float(np.squeeze(latest["High"]))
                    - max(float(np.squeeze(latest["Close"])),
                          float(np.squeeze(latest["Open"]))))
    lower_shadow = (min(float(np.squeeze(latest["Close"])),
                        float(np.squeeze(latest["Open"])))
                    - float(np.squeeze(latest["Low"])))

    pattern = "none"
    if total_range > 0:
        if lower_shadow > 2 * body and lower_shadow > upper_shadow:
            pattern = "hammer"
        elif upper_shadow > 2 * body and upper_shadow > lower_shadow:
            pattern = "shooting_star"
        elif volume_ratio > 1.8 and body / total_range > 0.6:
            prev_close = float(np.squeeze(df.iloc[-2]["Close"]))
            change = (float(np.squeeze(latest["Close"]))
                      - prev_close) / prev_close * 100
            if change > 3:
                pattern = "bullish_breakout"
            elif change < -3:
                pattern = "bearish_engulfing"

    recent_5 = df.tail(5)
    recent_history: List[Dict[str, Any]] = []
    for _, row in recent_5.iterrows():
        recent_history.append({
            "date": (str(row.name.date())
                     if hasattr(row.name, "date") else str(row.name)),
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


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------

def _history_to_dataframe(records: List[Dict]) -> pd.DataFrame:
    """Convert get_daily_history output to the DataFrame format expected
    by compute_indicators_from_dataframe."""
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["date"])
    df.set_index("Date", inplace=True)
    df = df.rename(columns={
        "open": "Open", "close": "Close",
        "high": "High", "low": "Low", "volume": "Volume",
    })
    for c in ("Open", "High", "Low", "Close", "Volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Close"])


def get_technical_indicators(ticker: str, days: int = 120) -> Dict[str, Any]:
    """Fetch history + realtime, compute all technical indicators.

    Calls ``get_daily_history`` and ``get_realtime_quote`` internally,
    then runs ``compute_indicators_from_dataframe`` and enriches with
    ``trend_status`` and ``support/resistance_levels``.

    Args:
        ticker: Stock code — ``600519`` (A-share), ``1810.HK``, ``AAPL``
        days:   Number of trading days for history (default 120)

    Returns:
        Dict with keys: current_price, ma5/10/20, ma_alignment, rsi,
        volume_ratio, volume_status, trend_score, trend_status,
        support, resistance, support_levels, resistance_levels,
        pattern, realtime_quote, recent_history.
    """
    from tools.get_daily_history import get_daily_history
    from tools.get_realtime_quote import get_realtime_quote

    history = get_daily_history(ticker, days=days)
    if not history:
        return {"_error": "No historical data available"}

    df = _history_to_dataframe(history)
    if df.empty or len(df) < 5:
        return {"_error": "Insufficient data after conversion"}

    realtime = get_realtime_quote(ticker)
    result = compute_indicators_from_dataframe(df, realtime)

    result["support_levels"] = [result["support"]]
    result["resistance_levels"] = [result["resistance"]]

    ts = result.get("trend_score", 50)
    if ts >= 70:
        result["trend_status"] = "STRONG_BULL"
    elif ts >= 55:
        result["trend_status"] = "BULL"
    elif ts >= 45:
        result["trend_status"] = "NEUTRAL"
    elif ts >= 30:
        result["trend_status"] = "BEAR"
    else:
        result["trend_status"] = "STRONG_BEAR"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="get_technical_indicators tool")
    parser.add_argument("ticker", help="Stock code (600519 / AAPL / 1810.HK)")
    parser.add_argument("--days", type=int, default=120)
    args = parser.parse_args()
    result = get_technical_indicators(args.ticker, days=args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
