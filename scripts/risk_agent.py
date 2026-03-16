# /// script
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
    """Fetch risk-specific data from AkShare/Tencent/yfinance."""
    from data_provider import (
        is_a_share, is_hk_stock, fetch_a_share_news, fetch_us_stock_news,
        fetch_a_share_realtime, fetch_hk_realtime, fetch_us_stock_realtime,
        resolve_ticker,
    )

    clean = ticker.strip().split(".")[0]
    all_news = []

    if is_a_share(clean):
        try:
            all_news = fetch_a_share_news(clean, limit=20)
        except Exception as e:
            print(f"[risk news] {e}", file=sys.stderr)
    else:
        try:
            tickers = resolve_ticker(ticker)
            all_news = fetch_us_stock_news(tickers["yahoo"], limit=20)
        except Exception as e:
            print(f"[risk news] {e}", file=sys.stderr)

    insider = _filter_news_by_category(all_news, RISK_CATEGORIES["insider"])[:3]
    earnings = _filter_news_by_category(all_news, RISK_CATEGORIES["earnings"])[:3]
    regulatory = _filter_news_by_category(all_news, RISK_CATEGORIES["regulatory"])[:3]
    lockup = _filter_news_by_category(all_news, RISK_CATEGORIES["lockup"])[:2]
    industry = _filter_news_by_category(all_news, RISK_CATEGORIES["industry"])[:2]

    valuation = {}
    if is_a_share(clean):
        try:
            quote = fetch_a_share_realtime(clean)
            if "error" not in quote:
                valuation = {
                    "pe_ratio": quote.get("pe_ratio", 0),
                    "pb_ratio": quote.get("pb_ratio", 0),
                    "market_cap_total": quote.get("market_cap_total", 0),
                    "turnover_rate": quote.get("turnover_rate", 0),
                    "source": "tencent_finance",
                }
        except Exception as e:
            print(f"[risk valuation tencent] {e}", file=sys.stderr)
    elif is_hk_stock(ticker):
        try:
            quote = fetch_hk_realtime(ticker)
            if "error" not in quote:
                valuation = {
                    "pe_ratio": quote.get("pe_ratio", 0),
                    "pb_ratio": quote.get("pb_ratio", 0),
                    "market_cap_total": quote.get("market_cap_total", 0),
                    "turnover_rate": quote.get("turnover_rate", 0),
                    "week52_high": quote.get("week52_high", 0),
                    "week52_low": quote.get("week52_low", 0),
                    "source": "tencent_finance",
                }
        except Exception as e:
            print(f"[risk valuation tencent hk] {e}", file=sys.stderr)
    else:
        try:
            tickers = resolve_ticker(ticker)
            quote = fetch_us_stock_realtime(tickers["yahoo"])
            if "error" not in quote:
                valuation = {
                    "pe_ratio": quote.get("pe_ratio", 0),
                    "pb_ratio": quote.get("pb_ratio", 0),
                    "market_cap": quote.get("market_cap", 0),
                    "fifty_two_week_high": quote.get("fifty_two_week_high", 0),
                    "fifty_two_week_low": quote.get("fifty_two_week_low", 0),
                    "source": "yfinance",
                }
        except Exception as e:
            print(f"[risk valuation yfinance] {e}", file=sys.stderr)

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
