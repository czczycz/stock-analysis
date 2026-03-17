---
name: stock-analysis
description: >
  Multi-strategy stock analysis producing a structured Decision Dashboard.
  Use when user asks to "analyze a stock", "分析股票", "evaluate TICKER",
  "give me a buy/sell signal", "股票决策", or mentions stock codes like
  "601919", "AAPL", "00700.HK". Supports A-shares, HK, and US equities.
  11 built-in strategies, 4 pipeline modes (full/quick/news/technical).
  No API keys required.
---

# Stock Analysis

Configurable stock analysis pipeline producing a **Decision Dashboard**
(buy / hold / sell).

```
Technical → Intel → Risk → Strategy → Decision
```

**Zero configuration** — free, keyless data sources (Tencent Finance, AkShare, yfinance).

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (dependencies auto-install on first run)

## Architecture

```
tools/       ← bottom layer
scripts/     ← upper layer (CLI wrappers, depends on tools/)
strategies/  ← YAML strategy definitions
references/  ← detailed docs loaded on demand
```

## Path Convention

- `SD` = `<this skill directory>/scripts`
- `TD` = `<this skill directory>/tools`

---

## Usage

### Run Analysis

```bash
uv run "SD/pipeline.py" analyze TICKER
```

Pass a 6-digit code for A-shares (`601919`) or a ticker symbol for US stocks (`AAPL`).

### Pipeline Modes

```bash
uv run "SD/pipeline.py" analyze TICKER --mode MODE
uv run "SD/pipeline.py" modes
```

| Mode | Stages | Use Case |
|------|--------|----------|
| `full` | Technical → Intel → Risk → Strategy | Complete analysis **(default)** |
| `quick` | Technical → Strategy | Fast signal, skip news/risk |
| `news` | Intel → Risk | Sentiment & risk screening only |
| `technical` | Technical | Indicators only |

### Output Keys

| Key | Content |
|-----|---------|
| `technical` | MA, RSI, volume ratio, trend score, support/resistance, K-line pattern |
| `intel` | News headlines, risk alerts, positive catalysts |
| `risk` | Risk categories, PE/PB valuation |
| `strategy` | Detected market regime, up to 3 recommended strategies |
| `dashboard_schema` | Decision Dashboard JSON schema |

Keys only appear for stages included in the selected mode.

### Other Commands

```bash
uv run "SD/pipeline.py" schema    # Print Decision Dashboard JSON schema
```

---

## LLM Task

After calling `pipeline.py analyze`, interpret ALL returned data and produce
the final answer as a **formatted Markdown report**.

**Signal weighting** (without strategies): Technical 40 %, Intel 30 %, Risk 30 %.
With strategies: Technical 30 %, Intel 25 %, Risk 25 %, Strategy 20 %.

**Scoring**: 80–100 buy (high conviction) / 60–79 buy / 40–59 hold / 20–39 sell / 0–19 sell (major risk).

**Risk veto**: If any risk flag has severity "high" or `veto_buy: true`, cap the final signal at "hold".

**Strategy evaluation**: For each recommended strategy, check entry conditions
against the technical data and adjust the score accordingly.

> Read `references/output-template.md` for the full Decision Dashboard
> Markdown template with all placeholders.

---

## Tools

Five tools under `tools/`, each runnable standalone via `uv run "TD/<name>.py"`:

| Tool | Purpose |
|------|---------|
| `get_daily_history` | Historical OHLCV K-line data |
| `get_realtime_quote` | Real-time stock quote |
| `get_technical_indicators` | MA, RSI, support/resistance, trend status |
| `search_stock_news` | News with impact classification |
| `is_stock_hot` | Check if stock is leading in hot sectors |

> Read `references/tools-reference.md` for CLI usage, return schemas, and
> the internal dependency graph.

---

## Strategies

11 built-in strategies in `strategies/`, auto-selected by market regime:

| Regime | Strategies |
|--------|------------|
| `sector_hot` | dragon_head, emotion_cycle |
| `trending_up` | bull_trend, volume_breakout, ma_golden_cross |
| `trending_down` | shrink_pullback, bottom_volume |
| `sideways` | box_oscillation, shrink_pullback |
| `volatile` | chan_theory, wave_theory |

Custom strategies: drop a `.yaml` into `custom_strategies/` — auto-loaded, same-name overrides built-in.

> Read `references/strategies-guide.md` for regime detection logic,
> strategy evaluation flow, required_tools, and the full YAML template.
