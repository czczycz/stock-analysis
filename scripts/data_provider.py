# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas']
# ///
"""
Data Provider — CLI wrapper over tools.data_layer.

All core data-fetching logic lives in ``tools/data_layer.py``.
This script re-exports every public function for backward compatibility
and provides the CLI interface.

Commands:
  resolve-ticker CODE         Resolve stock code to ticker formats
  realtime CODE               Fetch real-time quote (Tencent / yfinance)
  news CODE [--limit N]       Fetch stock news (AkShare / yfinance)
"""

import json
import sys
import argparse
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# Re-export everything from the canonical tools.data_layer module
from tools._providers import (  # noqa: F401, E402
    MAX_RETRIES,
    RETRY_BACKOFF,
    resolve_ticker,
    is_a_share,
    is_hk_stock,
    fetch_a_share_history,
    fetch_a_share_realtime,
    fetch_hk_realtime,
    fetch_us_stock_realtime,
    fetch_realtime,
    fetch_a_share_news,
    fetch_us_stock_news,
    fetch_stock_news,
)


def main():
    parser = argparse.ArgumentParser(
        description="Data Provider (Tencent + AkShare + Yahoo)")
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
        print(json.dumps(resolve_ticker(args.code),
                         ensure_ascii=False, indent=2))
    elif args.command == "realtime":
        print(json.dumps(fetch_realtime(args.code),
                         ensure_ascii=False, indent=2))
    elif args.command == "news":
        print(json.dumps(fetch_stock_news(args.code, args.limit),
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
