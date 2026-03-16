"""Public tools API for stock analysis strategies.

``tools/`` is the bottom layer — ZERO dependency on ``scripts/``.
Internal adapter ``_providers.py`` handles multi-source data fetching.

5 public tools (referenced by strategies via ``required_tools``)::

    get_daily_history          — historical OHLCV K-line data
    get_realtime_quote         — real-time stock quote
    get_technical_indicators   — MA, RSI, support/resistance, trend status
    search_stock_news          — news with impact classification
    get_sector_rankings        — A-share industry sector rankings

Internal dependency graph::

    _providers.py               (akshare, yfinance, pandas — data adapters)
    get_daily_history          → _providers
    get_realtime_quote         → _providers
    search_stock_news          → _providers
    get_sector_rankings        (standalone: akshare)
    get_technical_indicators   → get_daily_history + get_realtime_quote
"""

import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from tools.get_daily_history import get_daily_history  # noqa: E402
from tools.get_realtime_quote import get_realtime_quote  # noqa: E402
from tools.get_technical_indicators import get_technical_indicators  # noqa: E402
from tools.search_stock_news import search_stock_news  # noqa: E402
from tools.get_sector_rankings import get_sector_rankings  # noqa: E402

__all__ = [
    "get_daily_history",
    "get_realtime_quote",
    "get_technical_indicators",
    "search_stock_news",
    "get_sector_rankings",
]
