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
Analyze 601919 for me
```

The agent runs the pipeline and returns a formatted Decision Dashboard.

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
