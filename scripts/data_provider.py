# /// script
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""
Data Provider — multi-source financial data fetcher (no API keys needed).

Sources:
  - Tencent Finance (qt.gtimg.cn): real-time A-share quotes
  - AkShare: A-share history, news, stock info
  - yfinance: US/Global stocks, news, fundamentals

Commands:
  resolve-ticker CODE         Resolve stock code to ticker formats
  realtime CODE               Fetch A-share real-time quote (Tencent)
  news CODE [--limit N]       Fetch stock news (AkShare for A-shares, Yahoo for US)

Also importable by sibling scripts via sys.path.
"""

import io
import json
import re
import sys
import time
import argparse
import urllib.request
from typing import Any, Dict, List

MAX_RETRIES = 3
RETRY_BACKOFF = (1, 2, 4)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def resolve_ticker(code: str) -> Dict[str, str]:
    """Resolve a stock code to ticker formats for different data sources."""
    raw = code.strip().upper()

    if raw.endswith(".HK") or raw.endswith(".HK"):
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
            return {"yahoo": f"{clean}.SS", "akshare": clean, "market": "A-share (Shanghai)",
                    "tencent": f"sh{clean}"}
        elif clean.startswith("0") or clean.startswith("3"):
            return {"yahoo": f"{clean}.SZ", "akshare": clean, "market": "A-share (Shenzhen)",
                    "tencent": f"sz{clean}"}
        return {"yahoo": clean, "akshare": clean, "market": "Unknown", "tencent": ""}
    return {"yahoo": raw if "." in raw else clean, "akshare": clean, "market": "US/Global", "tencent": ""}


def is_a_share(code: str) -> bool:
    clean = code.strip().split(".")[0]
    return clean.isdigit() and len(clean) == 6


def is_hk_stock(code: str) -> bool:
    return code.strip().upper().endswith(".HK")


def fetch_a_share_history(code: str, days: int = 120) -> List[Dict[str, Any]]:
    """Fetch A-share daily K-line via Tencent Finance (web.ifzq.gtimg.cn).

    Returns list of dicts with keys: date, open, close, high, low, volume.
    Uses forward-adjusted (qfq) prices. No API key needed.
    """
    tickers = resolve_ticker(code)
    tencent_code = tickers.get("tencent", "")
    if not tencent_code:
        return []

    import datetime as _dt
    end = _dt.datetime.now().strftime("%Y-%m-%d")
    start = (_dt.datetime.now() - _dt.timedelta(days=days + 60)).strftime("%Y-%m-%d")
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={tencent_code},day,{start},{end},{days + 60},qfq")

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; StockAnalysis/1.0)",
                "Connection": "close",
            })
            resp = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
            data = json.loads(resp)
            stock_data = data.get("data", {}).get(tencent_code, {})
            klines = stock_data.get("qfqday") or stock_data.get("day") or []
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


def fetch_a_share_realtime(code: str) -> Dict[str, Any]:
    """Fetch real-time A-share quote from Tencent Finance (qt.gtimg.cn).

    No API key needed. Returns dict with price, volume, PE, PB, etc.
    """
    tickers = resolve_ticker(code)
    tencent_code = tickers.get("tencent", "")
    if not tencent_code:
        return {"error": f"Cannot resolve {code} for Tencent Finance"}

    url = f"http://qt.gtimg.cn/q={tencent_code}"
    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; StockAnalysis/1.0)",
                "Connection": "close",
            })
            resp = urllib.request.urlopen(req, timeout=10).read().decode("gbk", errors="replace")
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                return {"error": f"Tencent Finance request failed after {MAX_RETRIES} retries: {e}"}

    m = re.search(r'"([^"]+)"', resp)
    if not m:
        return {"error": "Failed to parse Tencent Finance response"}

    fields = m.group(1).split("~")
    if len(fields) < 50:
        return {"error": f"Unexpected field count: {len(fields)}"}

    def _safe_float(idx, default=0.0):
        try:
            return float(fields[idx])
        except (IndexError, ValueError):
            return default

    return {
        "name": fields[1] if len(fields) > 1 else "",
        "code": fields[2] if len(fields) > 2 else code,
        "price": _safe_float(3),
        "yesterday_close": _safe_float(4),
        "open": _safe_float(5),
        "volume_lots": _safe_float(6),
        "high": _safe_float(33),
        "low": _safe_float(34),
        "volume_lots_2": _safe_float(36),
        "amount_wan": _safe_float(37),
        "turnover_rate": _safe_float(38),
        "pe_ratio": _safe_float(39),
        "amplitude": _safe_float(43),
        "market_cap_circulating": _safe_float(44),
        "market_cap_total": _safe_float(45),
        "pb_ratio": _safe_float(46),
        "upper_limit": _safe_float(47),
        "lower_limit": _safe_float(48),
        "volume_ratio": _safe_float(49),
        "change_amount": _safe_float(31),
        "change_percent": _safe_float(32),
        "source": "tencent_finance",
    }


def fetch_hk_realtime(code: str) -> Dict[str, Any]:
    """Fetch real-time HK stock quote from Tencent Finance (qt.gtimg.cn).

    HK field layout differs from A-shares — uses dedicated mapping.
    """
    tickers = resolve_ticker(code)
    tencent_code = tickers.get("tencent", "")
    if not tencent_code:
        return {"error": f"Cannot resolve {code} for Tencent Finance HK"}

    url = f"http://qt.gtimg.cn/q={tencent_code}"
    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; StockAnalysis/1.0)",
                "Connection": "close",
            })
            resp = urllib.request.urlopen(req, timeout=10).read().decode("gbk", errors="replace")
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
            else:
                return {"error": f"Tencent Finance HK request failed: {e}"}

    m = re.search(r'"([^"]+)"', resp)
    if not m:
        return {"error": "Failed to parse Tencent Finance HK response"}

    fields = m.group(1).split("~")
    if len(fields) < 50:
        return {"error": f"Unexpected field count: {len(fields)}"}

    def _sf(idx, default=0.0):
        try:
            return float(fields[idx])
        except (IndexError, ValueError):
            return default

    return {
        "name": fields[1] if len(fields) > 1 else "",
        "code": fields[2] if len(fields) > 2 else code,
        "price": _sf(3),
        "yesterday_close": _sf(4),
        "open": _sf(5),
        "volume": _sf(6),
        "high": _sf(33),
        "low": _sf(34),
        "amount": _sf(37),
        "pe_ratio": _sf(39),
        "amplitude": _sf(43),
        "market_cap_circulating": _sf(44),
        "market_cap_total": _sf(45),
        "turnover_rate": _sf(50),
        "pb_ratio": _sf(58),
        "week52_high": _sf(48),
        "week52_low": _sf(49),
        "change_amount": _sf(31),
        "change_percent": _sf(32),
        "currency": fields[75] if len(fields) > 75 else "HKD",
        "source": "tencent_finance",
    }


def fetch_us_stock_realtime(ticker: str) -> Dict[str, Any]:
    """Fetch real-time US/Global stock quote via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        return {
            "name": info.get("shortName", info.get("longName", ticker)),
            "code": ticker,
            "price": info.get("currentPrice", info.get("regularMarketPrice", 0)),
            "yesterday_close": info.get("previousClose", 0),
            "open": info.get("open", info.get("regularMarketOpen", 0)),
            "high": info.get("dayHigh", info.get("regularMarketDayHigh", 0)),
            "low": info.get("dayLow", info.get("regularMarketDayLow", 0)),
            "volume": info.get("volume", info.get("regularMarketVolume", 0)),
            "pe_ratio": info.get("trailingPE", 0),
            "pb_ratio": info.get("priceToBook", 0),
            "market_cap": info.get("marketCap", 0),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0),
            "source": "yfinance",
        }
    except Exception as e:
        return {"error": f"yfinance quote failed: {e}"}


def fetch_a_share_news(code: str, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch A-share stock news via AkShare (stock_news_em).

    No API key needed — uses public web pages.
    """
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


def fetch_us_stock_news(ticker: str, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch US/HK/Global stock news via yfinance.

    Handles both legacy flat format and newer nested ``content`` format.
    """
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


def fetch_realtime(code: str) -> Dict[str, Any]:
    """Fetch real-time quote — auto-selects source based on stock type."""
    if is_a_share(code):
        return fetch_a_share_realtime(code)
    if is_hk_stock(code):
        return fetch_hk_realtime(code)
    return fetch_us_stock_realtime(resolve_ticker(code)["yahoo"])


def main():
    parser = argparse.ArgumentParser(description="Data Provider (Tencent + AkShare + Yahoo)")
    sub = parser.add_subparsers(dest="command")

    p_r = sub.add_parser("resolve-ticker", help="Resolve stock code")
    p_r.add_argument("code")

    p_rt = sub.add_parser("realtime", help="Fetch real-time quote")
    p_rt.add_argument("code")

    p_n = sub.add_parser("news", help="Fetch stock news")
    p_n.add_argument("code")
    p_n.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "resolve-ticker":
        print(json.dumps(resolve_ticker(args.code), ensure_ascii=False, indent=2))
    elif args.command == "realtime":
        print(json.dumps(fetch_realtime(args.code), ensure_ascii=False, indent=2))
    elif args.command == "news":
        print(json.dumps(fetch_stock_news(args.code, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
