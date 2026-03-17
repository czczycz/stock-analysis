# Tools Reference

Five independent tools live under `tools/`. Each can be run standalone
via `uv run "TD/<name>.py"` or imported in Python (`from tools import <name>`).
Strategies declare which tools they need in `required_tools`. During analysis,
the LLM may call these tools directly to evaluate strategy entry conditions.

`tools/` is the **bottom layer** — it depends only on external libraries
(akshare, yfinance, pandas, numpy, scipy) and has **zero dependency on scripts/**.

## Internal Dependency Graph

```
_providers.py               (INTERNAL — akshare, yfinance, pandas)
get_daily_history          → _providers
get_realtime_quote         → _providers
search_stock_news          → _providers
is_stock_hot               (standalone: East Money via requests, Sina fallback)
get_technical_indicators   → get_daily_history + get_realtime_quote
```

## Tool Details

| Tool | CLI | Returns |
|------|-----|---------|
| `get_daily_history` | `uv run "TD/get_daily_history.py" TICKER [--days 120]` | `[{date, open, high, low, close, volume}, …]` |
| `get_realtime_quote` | `uv run "TD/get_realtime_quote.py" TICKER` | `{name, price, change_pct, volume, pe, pb, …}` |
| `get_technical_indicators` | `uv run "TD/get_technical_indicators.py" TICKER [--days 120]` | `{ma5, ma10, ma20, rsi, trend_score, trend_status, support_levels, resistance_levels, pattern, …}` |
| `search_stock_news` | `uv run "TD/search_stock_news.py" TICKER [--limit 10]` | `[{title, content, time, source, url, impact}, …]` — impact: positive / negative / neutral |
| `is_stock_hot` | `uv run "TD/is_stock_hot.py" STOCK_NAME` | `{is_hot, matched_sectors: [{sector_name, change_percent, board_type}, …], hot_sectors: […]}` |

## Using Tools with Strategies

When the `strategy` stage recommends a strategy (e.g. `shrink_pullback`),
check its `required_tools` field and call the corresponding tools to verify
whether entry conditions are met. Example flow:

1. Pipeline returns `strategy.recommended[0].name = "shrink_pullback"`
   with `required_tools: [get_daily_history, get_technical_indicators, get_realtime_quote]`
2. Call each tool to get fresh data:
   ```bash
   uv run "TD/get_daily_history.py" 600519
   uv run "TD/get_technical_indicators.py" 600519
   uv run "TD/get_realtime_quote.py" 600519
   ```
3. Evaluate the strategy's `instructions` against the tool outputs
4. Incorporate the evaluation result into the final report's **策略使用** section

> **Note**: In `full` / `quick` modes the pipeline already calls `get_technical_indicators`
> internally, so `technical` data is available without extra tool calls. Only
> invoke additional tools when a strategy requires data not present in the
> pipeline output (e.g. `search_stock_news` or `is_stock_hot`).
