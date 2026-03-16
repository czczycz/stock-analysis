# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""
Intel Agent — fetches news, research reports, and sentiment data.

Commands:
  fetch TICKER    Fetch news and intelligence, output JSON
  schema          Print the expected LLM output schema

Data sources:
  - akshare (stock_news_em): A-share news from public pages (no API key)
  - yfinance: US/Global stock news
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

OUTPUT_SCHEMA = {
    "signal": "strong_buy|buy|hold|sell|strong_sell",
    "confidence": "float 0.0-1.0",
    "reasoning": "str — 2-3 sentence summary of news/sentiment findings",
    "risk_alerts": ["str — list of detected risks"],
    "positive_catalysts": ["str — list of catalysts"],
    "sentiment_label": "very_positive|positive|neutral|negative|very_negative",
    "key_news": [
        {"title": "str", "impact": "positive|negative|neutral"}
    ],
}

RISK_KEYWORDS = ["减持", "业绩预亏", "业绩下滑", "亏损", "处罚", "监管", "立案",
                 "调查", "被查", "留置", "违规", "解禁", "诉讼", "退市", "ST",
                 "警示", "下跌", "暴跌", "风险", "债务", "违约", "担保", "纪委",
                 "审查", "问询", "罚款"]

POSITIVE_KEYWORDS = ["增持", "回购", "业绩增长", "业绩预增", "超预期", "新签订单",
                     "中标", "战略合作", "获批", "突破", "涨停", "利好", "分红",
                     "高送转", "研发", "创新", "龙头"]


def _classify_news(items: list) -> dict:
    """Classify news items into risk alerts and positive catalysts by keyword matching."""
    risk_alerts = []
    positive_catalysts = []
    classified = []

    for item in items:
        title = item.get("title", "")
        content = item.get("content", title)
        text = f"{title} {content}".lower()

        has_risk = any(kw in text for kw in RISK_KEYWORDS)
        has_positive = any(kw in text for kw in POSITIVE_KEYWORDS)

        if has_risk:
            impact = "negative"
            risk_alerts.append(title)
        elif has_positive:
            impact = "positive"
            positive_catalysts.append(title)
        else:
            impact = "neutral"

        classified.append({"title": title, "impact": impact,
                           "time": item.get("time", ""), "source": item.get("source", item.get("publisher", ""))})

    return {
        "risk_alerts": risk_alerts[:5],
        "positive_catalysts": positive_catalysts[:5],
        "classified_news": classified,
    }


def fetch_intel(ticker: str) -> dict:
    """Fetch news and intelligence from AkShare (A-share) or yfinance (US/HK/Global)."""
    from data_provider import is_a_share, fetch_a_share_news, fetch_us_stock_news, resolve_ticker

    all_news = []
    clean = ticker.strip().split(".")[0]

    if is_a_share(clean):
        try:
            all_news = fetch_a_share_news(clean, limit=15)
        except Exception as e:
            print(f"[akshare news] {e}", file=sys.stderr)
    else:
        try:
            tickers = resolve_ticker(ticker)
            all_news = fetch_us_stock_news(tickers["yahoo"], limit=15)
        except Exception as e:
            print(f"[yfinance news] {e}", file=sys.stderr)

    classification = _classify_news(all_news)

    general_news = classification["classified_news"][:5]
    research = [n for n in classification["classified_news"] if
                any(kw in n.get("title", "") for kw in ["研报", "机构", "评级", "研究", "analyst", "rating", "upgrade"])][:3]
    announcements = [n for n in classification["classified_news"] if
                     any(kw in n.get("title", "") for kw in ["公告", "业绩", "财报", "earnings", "announcement"])][:3]

    return {
        "general_news": general_news,
        "research_reports": research,
        "announcements": announcements,
        "risk_alerts": classification["risk_alerts"],
        "positive_catalysts": classification["positive_catalysts"],
        "total_items": len(all_news),
    }


def cmd_fetch(args):
    result = fetch_intel(args.ticker)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_schema(_args):
    print(json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Intel Agent — news & sentiment data")
    sub = parser.add_subparsers(dest="command")

    p_f = sub.add_parser("fetch", help="Fetch news/intel for a ticker")
    p_f.add_argument("ticker", help="Stock ticker / code")

    sub.add_parser("schema", help="Print LLM output schema")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"fetch": cmd_fetch, "schema": cmd_schema}[args.command](args)


if __name__ == "__main__":
    main()
