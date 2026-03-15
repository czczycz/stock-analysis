# Stock Analysis Skill

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

[中文文档](README_zh.md)

An AI agent skill for multi-strategy stock analysis. Produces a structured **Decision Dashboard** (buy / hold / sell) through a configurable pipeline. Supports **A-shares, Hong Kong, and US equities**.

> Derived from [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) — re-architected as a zero-config agent skill that can be used directly by [Openclaw](https://github.com/openclaw/openclaw), [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), and other skill-compatible AI agents.

## Quick Start

1. Install [uv](https://docs.astral.sh/uv/)
2. Place this skill directory where your agent can access it
3. Ask the agent to analyze any stock:

```
Analyze 600519 for me
```

The agent runs the pipeline and returns a formatted Decision Dashboard. Here is a sample output for Kweichow Moutai (600519):

<details>
<summary>📊 Sample Output — Kweichow Moutai (600519)</summary>

```markdown
# Kweichow Moutai (600519) Analysis Report

## 🎯 Core Conclusion

| Item | Detail |
|------|--------|
| Summary | Short-term pressure, executive risk event pending digestion |
| Signal | 🟡 Hold Signal |
| Decision | **Hold** — Confidence: Medium |
| Sentiment | 38 / 100 |

**No position**: Wait for negative news to be absorbed; watch for stabilization at 1380 support
**Holding**: Hold for now; consider reducing if price breaks below 1380

---

## 📈 Data Perspective

**Trend**: Bearish MA alignment · Trend score 35 · ⚠️ Weak

| Indicator | Value |
|-----------|-------|
| Price | 1413.64 |
| MA5 / MA10 / MA20 | 1400.90 / 1407.30 / 1448.69 |
| RSI | 46.3 |
| Volume Ratio | 1.14 · Normal |
| Support / Resistance | 1323.69 / 1555.00 |

---

## 📰 Intelligence & Risk

**Sentiment**: Bearish

Key news:
- ❌ Moutai VP Jiang Yan placed under detention by supervisory commission
- ❌ Moutai CFO & Board Secretary Jiang Yan detained
- ❌ Chairman Chen Hua assumes Board Secretary duties

⚠️ **Risk Alert**: Senior executive detention is a major governance risk event

---

## 📋 Strategies Used

The following strategies were applied:
1. **Box Oscillation** (box_oscillation) — Identifies price range boundaries
2. **Shrink Pullback** (shrink_pullback) — Detects low-volume pullback to MA support

---

## 🎯 Battle Plan

| Level | Price |
|-------|-------|
| Ideal Buy | 1380 (box bottom support) |
| Secondary Buy | 1400 (near MA5) |
| Stop Loss | 1320 (below box range) |
| Take Profit | 1500 (near MA20 resistance) |

⚠️ AI-generated content for reference only. Not investment advice.
```

</details>

## Requirements

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** — script dependencies auto-install on first run
- **Platform**: Windows, Linux, macOS

No API keys or manual configuration needed. All data comes from free public sources (Tencent Finance, AkShare, yfinance).

## Pipeline Modes

The `PipelineManager` supports multiple analysis modes out of the box:

| Mode | Stages | Use Case |
|------|--------|----------|
| `full` | Technical → Intel → Risk → Strategy | Complete analysis **(default)** |
| `quick` | Technical → Strategy | Fast signal, skip news/risk |
| `news` | Intel → Risk | Sentiment & risk screening only |
| `technical` | Technical | Indicators only |

```bash
# Full analysis (default)
uv run scripts/pipeline.py analyze 601919

# Quick mode — technical + strategy only
uv run scripts/pipeline.py analyze 601919 --mode quick

# List all available modes
uv run scripts/pipeline.py modes
```

### Custom Modes

Register your own pipeline modes by combining available stages (`technical`, `intel`, `risk`, `strategy`):

```python
from pipeline import manager

manager.register_mode(
    name="risk_check",
    stages=["technical", "risk"],
    description="Technical + Risk — quick risk screening",
)
```

## Custom Strategies

Drop a `.yaml` file into `custom_strategies/` to add your own trading strategy. Same-name files override built-in ones. 11 built-in strategies are auto-selected by market regime.

```yaml
name: my_strategy
display_name: My Strategy
description: When to use this strategy
instructions: |
  Entry criteria, exit rules, position sizing...
```

See [`strategies/README.md`](strategies/README.md) for the full template.

## Disclaimer

This skill is for **educational and research purposes only**. It does not constitute investment advice. Always do your own due diligence before making any investment decisions. The authors assume no liability for any financial losses.
