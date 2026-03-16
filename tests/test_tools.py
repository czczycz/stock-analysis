"""Unit tests for tools/ package.

Run:  uv run -m pytest tests/test_tools.py -v

Tests are split into:
  - Pure logic tests (no network, always run)
  - Integration tests (require network, marked with @pytest.mark.network)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


# ── classify_impact (pure logic, no network) ──────────────────────────

class TestClassifyImpact:
    """Test news impact classification — keyword matching logic."""

    def test_negative_keywords(self):
        from tools.search_stock_news import classify_impact
        assert classify_impact("公司暴跌10%，面临处罚风险") == "negative"

    def test_positive_keywords(self):
        from tools.search_stock_news import classify_impact
        assert classify_impact("业绩增长超预期，获机构买入评级") == "positive"

    def test_neutral_when_balanced(self):
        from tools.search_stock_news import classify_impact
        assert classify_impact("市场表现平稳") == "neutral"

    def test_english_negative(self):
        from tools.search_stock_news import classify_impact
        assert classify_impact("Stock drop on fraud investigation") == "negative"

    def test_english_positive(self):
        from tools.search_stock_news import classify_impact
        assert classify_impact("Earnings beat expectations, surge ahead") == "positive"

    def test_empty_string(self):
        from tools.search_stock_news import classify_impact
        assert classify_impact("") == "neutral"

    def test_content_contributes(self):
        from tools.search_stock_news import classify_impact
        assert classify_impact("公司公告", "减持计划公布，涉嫌违规") == "negative"


# ── trend_status mapping (pure logic) ─────────────────────────────────

class TestTrendStatus:
    """Test trend_score → trend_status mapping in analyze_trend."""

    def _compute_status(self, score: int) -> str:
        if score >= 70:
            return "STRONG_BULL"
        elif score >= 55:
            return "BULL"
        elif score >= 45:
            return "NEUTRAL"
        elif score >= 30:
            return "BEAR"
        else:
            return "STRONG_BEAR"

    @pytest.mark.parametrize("score,expected", [
        (100, "STRONG_BULL"),
        (70, "STRONG_BULL"),
        (69, "BULL"),
        (55, "BULL"),
        (54, "NEUTRAL"),
        (45, "NEUTRAL"),
        (44, "BEAR"),
        (30, "BEAR"),
        (29, "STRONG_BEAR"),
        (0, "STRONG_BEAR"),
    ])
    def test_boundaries(self, score: int, expected: str):
        assert self._compute_status(score) == expected


# ── get_daily_history (mocked) ────────────────────────────────────────

class TestGetDailyHistory:
    """Test get_daily_history with mocked data_provider."""

    def test_returns_list_of_dicts_for_a_share(self):
        mock_records = [
            {"date": "2025-01-02", "open": 10.0, "high": 11.0,
             "low": 9.5, "close": 10.5, "volume": 100000},
        ]
        with patch("tools.get_daily_history.get_daily_history") as mock_fn:
            mock_fn.return_value = mock_records
            result = mock_fn("600519", days=5)
            assert isinstance(result, list)
            assert result[0]["date"] == "2025-01-02"
            assert set(result[0].keys()) == {
                "date", "open", "high", "low", "close", "volume"
            }

    def test_empty_on_failure(self):
        with patch("tools.get_daily_history.get_daily_history") as mock_fn:
            mock_fn.return_value = []
            assert mock_fn("INVALID") == []


# ── get_realtime_quote (mocked) ───────────────────────────────────────

class TestGetRealtimeQuote:
    def test_returns_dict(self):
        mock_quote = {"name": "贵州茅台", "price": 1800.0, "change_pct": 1.5}
        with patch("tools.get_realtime_quote.get_realtime_quote") as mock_fn:
            mock_fn.return_value = mock_quote
            result = mock_fn("600519")
            assert isinstance(result, dict)
            assert "price" in result


# ── get_technical_indicators (mocked) ─────────────────────────────────

class TestGetTechnicalIndicators:
    def test_error_when_no_history(self):
        with patch("tools.get_daily_history.get_daily_history", return_value=[]):
            from tools.get_technical_indicators import get_technical_indicators
            result = get_technical_indicators("INVALID")
            assert "_error" in result

    def test_has_trend_status_field(self):
        mock_history = [
            {"date": f"2025-01-{d:02d}", "open": 10.0, "high": 11.0,
             "low": 9.0, "close": 10.5, "volume": 100000}
            for d in range(1, 21)
        ]
        mock_tech = {
            "support": 9.0,
            "resistance": 11.0,
            "trend_score": 65,
            "ma5": 10.3,
            "ma10": 10.1,
            "ma20": 10.0,
        }
        with patch("tools.get_daily_history.get_daily_history",
                    return_value=mock_history), \
             patch("tools.get_realtime_quote.get_realtime_quote",
                   return_value={"price": 10.5}), \
             patch("tools.get_technical_indicators.compute_indicators_from_dataframe",
                   return_value=mock_tech):
            from tools.get_technical_indicators import get_technical_indicators
            result = get_technical_indicators("600519")
            assert result["trend_status"] == "BULL"
            assert result["support_levels"] == [9.0]
            assert result["resistance_levels"] == [11.0]


# ── get_sector_rankings (mocked) ──────────────────────────────────────

class TestGetSectorRankings:
    def test_returns_list_on_success(self):
        import pandas as pd
        mock_df = pd.DataFrame({
            "板块名称": ["半导体", "新能源"],
            "涨跌幅": [3.5, 2.1],
            "换手率": [1.2, 0.8],
            "领涨股票": ["中芯国际", "宁德时代"],
        })
        with patch("akshare.stock_board_industry_name_em",
                    return_value=mock_df):
            from tools.get_sector_rankings import get_sector_rankings
            result = get_sector_rankings(limit=2)
            assert len(result) == 2
            assert result[0]["sector_name"] == "半导体"
            assert result[0]["change_percent"] == 3.5

    def test_returns_empty_on_exception(self):
        with patch("akshare.stock_board_industry_name_em",
                    side_effect=Exception("API down")):
            from tools.get_sector_rankings import get_sector_rankings
            assert get_sector_rankings() == []


# ── search_stock_news (mocked) ────────────────────────────────────────

class TestSearchStockNews:
    def test_classifies_news(self):
        mock_raw = [
            {"title": "公司业绩大增超预期", "content": "", "time": "2025-01-01",
             "source": "新浪", "url": "http://example.com"},
            {"title": "股价暴跌引发退市预警", "content": "", "time": "2025-01-02",
             "source": "东财", "url": "http://example.com/2"},
        ]
        with patch("tools._providers.fetch_stock_news",
                    return_value=mock_raw):
            from tools.search_stock_news import search_stock_news
            result = search_stock_news("600519", limit=5)
            assert len(result) == 2
            assert result[0]["impact"] == "positive"
            assert result[1]["impact"] == "negative"


# ── network integration tests ─────────────────────────────────────────

network = pytest.mark.skipif(
    "--network" not in sys.argv,
    reason="Network tests skipped (pass --network to run)"
)


@network
class TestNetworkIntegration:
    """Require network — run with: uv run -m pytest tests/test_tools.py --network -v"""

    def test_get_daily_history_a_share(self):
        from tools.get_daily_history import get_daily_history
        result = get_daily_history("600519", days=5)
        assert len(result) > 0
        assert "close" in result[0]

    def test_get_realtime_quote_a_share(self):
        from tools.get_realtime_quote import get_realtime_quote
        result = get_realtime_quote("600519")
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_technical_indicators_a_share(self):
        from tools.get_technical_indicators import get_technical_indicators
        result = get_technical_indicators("600519", days=30)
        assert "trend_status" in result

    def test_search_stock_news_a_share(self):
        from tools.search_stock_news import search_stock_news
        result = search_stock_news("600519", limit=3)
        assert isinstance(result, list)

    def test_get_daily_history_us(self):
        from tools.get_daily_history import get_daily_history
        result = get_daily_history("AAPL", days=5)
        assert len(result) > 0

    def test_get_daily_history_hk(self):
        from tools.get_daily_history import get_daily_history
        result = get_daily_history("1810.HK", days=5)
        assert len(result) > 0
