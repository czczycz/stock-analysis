# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""search_stock_news — fetch and classify stock news by impact.

Dependencies (within tools/):
  tools/data_layer.py  — AkShare (A-share) & yfinance (US/HK) news

Depended on by:
  (none — leaf tool consumed by intel_agent / risk_agent)

Usage:
  uv run tools/search_stock_news.py TICKER [--limit 10]
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

_NEG_KW = [
    "下跌", "暴跌", "减持", "处罚", "违规", "亏损", "退市", "预警",
    "调查", "起诉", "罚款", "下调", "利空", "风险", "留置", "被查",
    "涉嫌", "立案", "ST", "解禁", "诉讼", "债务", "违约",
    "decline", "loss", "penalty", "downgrade", "sell", "drop",
    "warning", "fraud", "investigation",
]

_POS_KW = [
    "上涨", "增持", "回购", "利好", "突破", "创新高", "盈利", "业绩增长",
    "中标", "合作", "上调", "买入", "超预期", "分红", "高送转", "获批",
    "龙头", "涨停",
    "upgrade", "surge", "growth", "beat", "buy", "raise", "breakthrough",
]


def classify_impact(title: str, content: str = "") -> str:
    """Classify a single news item's impact as positive/negative/neutral."""
    text = f"{title} {content}".lower()
    neg = sum(1 for kw in _NEG_KW if kw in text)
    pos = sum(1 for kw in _POS_KW if kw in text)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def search_stock_news(
    ticker: str, limit: int = 10,
) -> List[Dict[str, Any]]:
    """Fetch and classify stock news by impact.

    Args:
        ticker: Stock code — ``600519`` (A-share), ``1810.HK``, ``AAPL``
        limit:  Maximum number of news items to return (default 10)

    Returns:
        List of dicts, each with keys:
        ``title, content, time, source, url, impact``
        where *impact* is ``positive | negative | neutral``.
    """
    from tools._providers import fetch_stock_news

    raw = fetch_stock_news(ticker, limit=limit)
    results: List[Dict[str, Any]] = []

    for item in raw:
        title = item.get("title", "") or ""
        content = item.get("content", "") or ""

        results.append({
            "title": title,
            "content": content,
            "time": item.get("time", ""),
            "source": item.get("source", item.get("publisher", "")),
            "url": item.get("url", item.get("link", "")),
            "impact": classify_impact(title, content),
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="search_stock_news tool")
    parser.add_argument("ticker", help="Stock code (600519 / AAPL / 1810.HK)")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    result = search_stock_news(args.ticker, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
