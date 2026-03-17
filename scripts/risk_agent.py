# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""
Risk Agent — fetches risk-specific data for screening.

Commands:
  fetch TICKER [--intel-json JSON]   Fetch risk data, output JSON
  schema                             Print the expected LLM output schema

Data sources:
  - akshare (stock_news_em): A-share risk-related news (no API key)
  - Tencent Finance (qt.gtimg.cn): real-time PE/PB valuation (no API key)
  - yfinance: US/Global fundamentals and news
"""

import json
import sys
import argparse

from _bootstrap import bootstrap; bootstrap()  # noqa: E702

OUTPUT_SCHEMA = {
    "risk_level": "high|medium|low|none",
    "risk_score": "int 0-100",
    "flags": [
        {
            "category": "insider|earnings|regulatory|industry|lockup|valuation|technical",
            "severity": "high|medium|low",
            "description": "str — clear description of the risk",
            "source": "str — where this information came from",
        }
    ],
    "veto_buy": "bool — true if risk is severe enough to veto buy signals",
    "reasoning": "str — 2-3 sentence overall risk assessment",
    "signal_adjustment": "none|downgrade_one|downgrade_two|veto",
}

RISK_CATEGORIES = {
    "insider": ["减持", "股东减持", "高管减持", "大股东减持", "质押", "insider sell",
                "增减持", "持股变动"],
    "earnings": ["业绩预告", "业绩预亏", "业绩变脸", "亏损", "业绩下滑", "营收下降",
                  "earnings warning", "profit warning", "miss", "下修"],
    "regulatory": ["监管", "处罚", "立案调查", "违规", "罚款", "被查", "留置",
                    "纪委", "审查", "问询", "警示函", "退市", "ST", "风险警示",
                    "SEC", "investigation", "penalty", "fine", "fraud"],
    "lockup": ["解禁", "限售股", "锁定期", "lock-up", "lockup expiration"],
    "industry": ["行业政策", "行业监管", "政策风险", "sector risk", "policy risk",
                  "政策收紧", "行业整顿"],
}


def _filter_news_by_category(news_items: list, keywords: list) -> list:
    """Filter news items that match any keyword in the category."""
    results = []
    for item in news_items:
        text = f"{item.get('title', '')} {item.get('content', '')}".lower()
        if any(kw.lower() in text for kw in keywords):
            results.append(item)
    return results


def fetch_risk_data(ticker: str) -> dict:
    """Fetch risk-specific data via shared tools layer."""
    from tools import search_stock_news, get_realtime_quote

    all_news = search_stock_news(ticker, limit=20)
    raw_news = [{"title": n.get("title", ""), "content": n.get("content", ""),
                 "time": n.get("time", ""), "source": n.get("source", ""),
                 "url": n.get("url", "")}
                for n in all_news]

    insider = _filter_news_by_category(raw_news, RISK_CATEGORIES["insider"])[:3]
    earnings = _filter_news_by_category(raw_news, RISK_CATEGORIES["earnings"])[:3]
    regulatory = _filter_news_by_category(raw_news, RISK_CATEGORIES["regulatory"])[:3]
    lockup = _filter_news_by_category(raw_news, RISK_CATEGORIES["lockup"])[:2]
    industry = _filter_news_by_category(raw_news, RISK_CATEGORIES["industry"])[:2]

    valuation: dict = {}
    try:
        quote = get_realtime_quote(ticker)
        if "_error" not in quote:
            valuation = {
                "pe_ratio": quote.get("pe_ratio", 0),
                "pb_ratio": quote.get("pb_ratio", 0),
                "source": quote.get("source", ""),
            }
            for key in ("market_cap_total", "market_cap", "turnover_rate",
                        "week52_high", "week52_low",
                        "fifty_two_week_high", "fifty_two_week_low"):
                v = quote.get(key)
                if v is not None and v != 0:
                    valuation[key] = v
    except Exception as e:
        print(f"[risk valuation] {e}", file=sys.stderr)

    return {
        "insider_activity": insider,
        "earnings_warnings": earnings,
        "regulatory_issues": regulatory,
        "lockup_expirations": lockup,
        "industry_risks": industry,
        "valuation": valuation,
        "total_news_scanned": len(all_news),
    }


def cmd_fetch(args):
    result = fetch_risk_data(args.ticker)
    if args.intel_json:
        try:
            result["existing_intel"] = json.loads(args.intel_json)
        except json.JSONDecodeError:
            pass
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_schema(_args):
    print(json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Risk Agent — risk screening data")
    sub = parser.add_subparsers(dest="command")

    p_f = sub.add_parser("fetch", help="Fetch risk data for a ticker")
    p_f.add_argument("ticker", help="Stock ticker / code")
    p_f.add_argument("--intel-json", default=None, help="Existing intel data JSON to reuse")

    sub.add_parser("schema", help="Print LLM output schema")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"fetch": cmd_fetch, "schema": cmd_schema}[args.command](args)


if __name__ == "__main__":
    main()
