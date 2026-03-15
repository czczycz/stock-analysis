---
name: stock_analysis
description: >
  Multi-strategy stock analysis producing a structured Decision Dashboard.
  Configurable pipeline modes: full / quick / news / technical.
  Supports A-shares, HK, and US equities. 11 built-in trading strategies
  plus user-defined custom strategies. No API keys required.
license: Apache-2.0
compatibility: Python 3.10+, uv | Windows, Linux, macOS
allowed-tools: Read Shell(uv run *, python *)
---

# Stock Analysis

Configurable stock analysis pipeline producing a **Decision Dashboard**
(buy / hold / sell).

```
Technical → Intel → Risk → Strategy → Decision
```

**Zero configuration** — free, keyless data sources (Tencent Finance, AkShare, yfinance).
Works on **Windows, Linux, and macOS**.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (dependencies auto-install on first run)

## Path Convention

`SD` = `<this skill directory>/scripts` — used in all commands below.

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

Users can register custom modes programmatically via `PipelineManager.register_mode()`.

### Output Keys

The JSON returned by `analyze` contains:

| Key | Content |
|-----|---------|
| `technical` | MA5/10/20, RSI-14, volume ratio, trend score, support/resistance, K-line pattern, recent history |
| `intel` | News headlines, risk alerts, positive catalysts |
| `risk` | Risk categories (insider/earnings/regulatory/lockup/industry), PE/PB valuation |
| `strategy` | Detected market regime, up to 3 recommended strategies with full instructions |
| `dashboard_schema` | Decision Dashboard JSON schema for output reference |

Keys only appear for stages included in the selected mode.

### Other Commands

```bash
uv run "SD/pipeline.py" schema    # Print Decision Dashboard JSON schema
```

---

## LLM Task

After calling `pipeline.py analyze`, interpret ALL returned data and produce
the final answer as a **formatted Markdown report** using the template below.

### Interpretation Rules

**Signal weighting** (without strategies): Technical 40%, Intel 30%, Risk 30%.
With strategies: Technical 30%, Intel 25%, Risk 25%, Strategy 20%.

**Scoring**: 80–100 buy (high conviction), 60–79 buy, 40–59 hold, 20–39 sell, 0–19 sell (major risk).

**Risk veto**: If any risk flag has severity "high" or `veto_buy: true`, cap the final signal at "hold".

**Strategy evaluation**: For each recommended strategy, check whether entry
conditions are met against the technical data. Adjust the score accordingly.

### Output Template

Replace all `{...}` placeholders with real values. Omit sections with no data.

---BEGIN TEMPLATE---

```markdown
# {stock_name} — 决策看板

> {one_sentence_conclusion}

## 📊 综合评分：{sentiment_score}/100 | {signal_type} | 置信度：{confidence_level}

{analysis_summary}

---

## 🎯 核心结论

| | 建议 |
|---|---|
| ⏰ 时效性 | {time_sensitivity} |
| 🈳 空仓 | {no_position_advice} |
| 📦 持仓 | {has_position_advice} |

---

## 📈 数据透视

### 趋势状态

| 指标 | 值 |
|------|------|
| 均线排列 | {ma_alignment} |
| 趋势评分 | {trend_score}/100 |
| 多头确认 | {is_bullish} |

### 价格位置

| 指标 | 值 |
|------|------|
| 当前价 | {current_price} |
| MA5 / MA10 / MA20 | {ma5} / {ma10} / {ma20} |
| MA5 乖离率 | {bias_ma5}%（{bias_status}） |
| 支撑位 | {support_level} |
| 阻力位 | {resistance_level} |

### 量能分析

| 指标 | 值 |
|------|------|
| 量比 | {volume_ratio} |
| 换手率 | {turnover_rate}% |
| 量能状态 | {volume_status} |

---

## 📰 情报研判

**情绪倾向**：{sentiment_label}

**正面催化**：
- {positive_catalyst_1}
- ...

**风险预警**：
- {risk_alert_1}
- ...

**关键新闻**：

| 标题 | 影响 |
|------|------|
| {news_title} | {impact} |

---

## ⚔️ 作战计划

### 狙击点位

| 点位 | 价格 |
|------|------|
| 🎯 理想买点 | {ideal_buy} |
| 🔄 次优买点 | {secondary_buy} |
| 🛑 止损位 | {stop_loss} |
| 🏁 止盈位 | {take_profit} |

### 仓位策略

| | 内容 |
|---|---|
| 建议仓位 | {suggested_position} |
| 入场计划 | {entry_plan} |
| 风控措施 | {risk_control} |

### 操作清单

- {checklist_item_1}
- {checklist_item_2}
- ...

---

## 📋 策略使用

{strategies_section}
<!-- If strategy stage was included in the pipeline mode, list which strategies
     were used. Example:

     本次分析使用了以下策略：
     1. **箱体震荡**（box_oscillation）— 识别价格箱体区间
     2. **缩量回踩**（shrink_pullback）— 检测缩量回踩均线支撑信号

     If no strategy stage was run (e.g. mode=news or mode=technical):

     本次分析未使用任何策略。
-->

---

## ⚠️ 风险提示

{risk_warning}

> **免责声明**：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
```

---END TEMPLATE---

---

## Strategies

11 built-in strategies in `strategies/`, auto-selected by market regime:

| Regime | Strategies |
|--------|------------|
| trending_up | bull_trend, volume_breakout, ma_golden_cross |
| trending_down | shrink_pullback, bottom_volume |
| sideways | box_oscillation, shrink_pullback |
| volatile | chan_theory, wave_theory |
| sector_hot | dragon_head, emotion_cycle |

### Custom Strategies

Drop a `.yaml` file into `custom_strategies/` — auto-loaded on next run.
Same-name files override built-in strategies.

Minimum template:

```yaml
name: my_strategy
display_name: My Strategy
description: When to use this strategy
instructions: |
  Entry criteria, exit rules, position sizing...
```

See `strategies/README.md` for the full template.
