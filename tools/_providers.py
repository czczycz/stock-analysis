# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""Internal data source adapters — NOT a public tool.

This module is prefixed with ``_`` because it is private infrastructure.
Public tools (get_daily_history, get_realtime_quote, etc.) depend on it;
it depends ONLY on external libraries. Do not import from scripts/.

Sources:
  - Tencent Finance (qt.gtimg.cn / web.ifzq.gtimg.cn): A-share & HK quotes + K-lines
  - AkShare: A-share news
  - yfinance: US/Global stocks, news, fundamentals, history fallback
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from typing import Any, Dict, List

MAX_RETRIES = 3
RETRY_BACKOFF = (1, 2, 4)

# ---------------------------------------------------------------------------
# Ticker resolution & helpers
# ---------------------------------------------------------------------------

def resolve_ticker(code: str) -> Dict[str, str]:
    """Resolve a stock code to ticker formats for different data sources."""
    raw = code.strip().upper()

    if raw.endswith(".HK"):
        num = raw.split(".")[0].lstrip("0") or "0"
        padded = num.zfill(5)
        return {
            "yahoo": f"{num}.HK",
            "akshare": padded,
            "market": "HK",
            "tencent": f"hk{padded}",
        }

    clean = raw.split(".")[0]
    if clean.isdigit() and len(clean) == 6:
        if clean.startswith("6"):
            return {"yahoo": f"{clean}.SS", "akshare": clean,
                    "market": "A-share (Shanghai)", "tencent": f"sh{clean}"}
        elif clean.startswith("0") or clean.startswith("3"):
            return {"yahoo": f"{clean}.SZ", "akshare": clean,
                    "market": "A-share (Shenzhen)", "tencent": f"sz{clean}"}
        return {"yahoo": clean, "akshare": clean, "market": "Unknown",
                "tencent": ""}
    return {"yahoo": raw if "." in raw else clean, "akshare": clean,
            "market": "US/Global", "tencent": ""}


def is_a_share(code: str) -> bool:
    clean = code.strip().split(".")[0]
    return clean.isdigit() and len(clean) == 6


def is_hk_stock(code: str) -> bool:
    return code.strip().upper().endswith(".HK")


# ---------------------------------------------------------------------------
# History (Tencent K-line)
# ---------------------------------------------------------------------------

def fetch_a_share_history(code: str, days: int = 120) -> List[Dict[str, Any]]:
    """Fetch A-share/HK daily K-line via Tencent Finance (web.ifzq.gtimg.cn).

    Forward-adjusted (qfq) prices. No API key needed.
    """
    tickers = resolve_ticker(code)
    tencent_code = tickers.get("tencent", "")
    if not tencent_code:
        return []

    import datetime as _dt
    end = _dt.datetime.now().strftime("%Y-%m-%d")
    start = (_dt.datetime.now() - _dt.timedelta(days=days + 60)).strftime(
        "%Y-%m-%d")
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={tencent_code},day,{start},{end},{days + 60},qfq")

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; StockAnalysis/1.0)",
                "Connection": "close",
            })
            resp = urllib.request.urlopen(req, timeout=10).read().decode(
                "utf-8")
            data = json.loads(resp)
            stock_data = data.get("data", {}).get(tencent_code, {})
            klines = (stock_data.get("qfqday")
                      or stock_data.get("day") or [])
            if not klines:
                return []
            results = []
            for k in klines:
                results.append({
                    "date": k[0],
                    "open": float(k[1]),
                    "close": float(k[2]),
                    "high": float(k[3]),
                    "low": float(k[4]),
                    "volume": float(k[5]) if len(k) > 5 else 0,
                })
            return results[-days:]
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                print(f"[tencent history] {e}", file=sys.stderr)
    return []


# ---------------------------------------------------------------------------
# Real-time quotes
# ---------------------------------------------------------------------------

def _tencent_quote_raw(tencent_code: str) -> str | None:
    """Fetch raw Tencent Finance quote string (shared by A-share & HK)."""
    url = f"http://qt.gtimg.cn/q={tencent_code}"
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; StockAnalysis/1.0)",
                "Connection": "close",
            })
            return urllib.request.urlopen(
                req, timeout=10).read().decode("gbk", errors="replace")
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                print(f"[tencent quote] {e}", file=sys.stderr)
    return None


def _parse_tencent_quote(
    code: str,
    float_fields: Dict[str, int],
    str_fields: Dict[str, tuple] | None = None,
) -> Dict[str, Any]:
    """Generic Tencent Finance quote parser.

    ``float_fields`` maps output key → field index.
    ``str_fields`` maps output key → (index, default) for string values.
    """
    tickers = resolve_ticker(code)
    tencent_code = tickers.get("tencent", "")
    if not tencent_code:
        return {"_error": f"Cannot resolve {code} for Tencent Finance"}

    resp = _tencent_quote_raw(tencent_code)
    if resp is None:
        return {"_error": "Tencent Finance request failed after retries"}

    m = re.search(r'"([^"]+)"', resp)
    if not m:
        return {"_error": "Failed to parse Tencent Finance response"}

    fields = m.group(1).split("~")
    if len(fields) < 50:
        return {"_error": f"Unexpected field count: {len(fields)}"}

    def _sf(idx: int, default: float = 0.0) -> float:
        try:
            return float(fields[idx])
        except (IndexError, ValueError):
            return default

    result: Dict[str, Any] = {
        "name": fields[1] if len(fields) > 1 else "",
        "code": fields[2] if len(fields) > 2 else code,
    }
    for key, idx in float_fields.items():
        result[key] = _sf(idx)
    if str_fields:
        for key, (idx, default) in str_fields.items():
            result[key] = fields[idx] if len(fields) > idx else default
    result["source"] = "tencent_finance"
    return result


_A_SHARE_FLOAT_FIELDS: Dict[str, int] = {
    "price": 3, "yesterday_close": 4, "open": 5, "volume_lots": 6,
    "high": 33, "low": 34, "volume_lots_2": 36, "amount_wan": 37,
    "turnover_rate": 38, "pe_ratio": 39, "amplitude": 43,
    "market_cap_circulating": 44, "market_cap_total": 45, "pb_ratio": 46,
    "upper_limit": 47, "lower_limit": 48, "volume_ratio": 49,
    "change_amount": 31, "change_percent": 32,
}

_HK_FLOAT_FIELDS: Dict[str, int] = {
    "price": 3, "yesterday_close": 4, "open": 5, "volume": 6,
    "high": 33, "low": 34, "amount": 37, "pe_ratio": 39,
    "amplitude": 43, "market_cap_circulating": 44, "market_cap_total": 45,
    "turnover_rate": 50, "pb_ratio": 58, "week52_high": 48, "week52_low": 49,
    "change_amount": 31, "change_percent": 32,
}

_HK_STR_FIELDS: Dict[str, tuple] = {
    "currency": (75, "HKD"),
}


def fetch_a_share_realtime(code: str) -> Dict[str, Any]:
    """Fetch real-time A-share quote from Tencent Finance."""
    return _parse_tencent_quote(code, _A_SHARE_FLOAT_FIELDS)


def fetch_hk_realtime(code: str) -> Dict[str, Any]:
    """Fetch real-time HK stock quote from Tencent Finance."""
    return _parse_tencent_quote(code, _HK_FLOAT_FIELDS, _HK_STR_FIELDS)


def fetch_us_stock_realtime(ticker: str) -> Dict[str, Any]:
    """Fetch real-time US/Global stock quote via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        return {
            "name": info.get("shortName", info.get("longName", ticker)),
            "code": ticker,
            "price": info.get("currentPrice",
                              info.get("regularMarketPrice", 0)),
            "yesterday_close": info.get("previousClose", 0),
            "open": info.get("open", info.get("regularMarketOpen", 0)),
            "high": info.get("dayHigh",
                             info.get("regularMarketDayHigh", 0)),
            "low": info.get("dayLow", info.get("regularMarketDayLow", 0)),
            "volume": info.get("volume",
                               info.get("regularMarketVolume", 0)),
            "pe_ratio": info.get("trailingPE", 0),
            "pb_ratio": info.get("priceToBook", 0),
            "market_cap": info.get("marketCap", 0),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0),
            "source": "yfinance",
        }
    except Exception as e:
        return {"_error": f"yfinance quote failed: {e}"}


def fetch_realtime(code: str) -> Dict[str, Any]:
    """Fetch real-time quote — auto-selects source based on stock type."""
    if is_a_share(code):
        return fetch_a_share_realtime(code)
    if is_hk_stock(code):
        return fetch_hk_realtime(code)
    return fetch_us_stock_realtime(resolve_ticker(code)["yahoo"])


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def fetch_a_share_news(code: str, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch A-share stock news via AkShare (stock_news_em)."""
    import akshare as ak
    clean = code.strip().split(".")[0]
    for attempt in range(MAX_RETRIES):
        try:
            df = ak.stock_news_em(symbol=clean)
            results = []
            for _, row in df.head(limit).iterrows():
                results.append({
                    "title": str(row.get("新闻标题", "")),
                    "content": str(row.get("新闻内容", ""))[:300],
                    "time": str(row.get("发布时间", "")),
                    "source": str(row.get("文章来源", "")),
                    "url": str(row.get("新闻链接", "")),
                })
            return results
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                print(f"[akshare news] {e}", file=sys.stderr)
    return []


def fetch_us_stock_news(ticker: str,
                        limit: int = 10) -> List[Dict[str, str]]:
    """Fetch US/HK/Global stock news via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        news = t.news or []
        results = []
        for item in news[:limit]:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or {}
            if content:
                provider = content.get("provider") or {}
                click_url = content.get("clickThroughUrl") or {}
                results.append({
                    "title": content.get("title", ""),
                    "publisher": provider.get("displayName", ""),
                    "link": click_url.get("url", ""),
                    "time": content.get("pubDate", ""),
                })
            else:
                results.append({
                    "title": item.get("title", ""),
                    "publisher": item.get("publisher", ""),
                    "link": item.get("link", ""),
                    "time": str(item.get("providerPublishTime", "")),
                })
        return results
    except Exception as e:
        print(f"[yfinance news] {e}", file=sys.stderr)
        return []


def fetch_stock_news(code: str, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch stock news — auto-selects source based on stock type."""
    if is_a_share(code):
        return fetch_a_share_news(code, limit)
    tickers = resolve_ticker(code)
    return fetch_us_stock_news(tickers["yahoo"], limit)
