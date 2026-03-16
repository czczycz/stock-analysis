# 交易策略目录

本目录存放**内置策略文件**（YAML 格式）。Pipeline 的 `strategy` 阶段自动加载并匹配策略。

## 策略如何工作

```
技术指标 → 行情识别 → 策略匹配 → 策略下发（含 instructions + required_tools）
```

### 1. 行情识别（Regime Detection）

`strategy_manager.detect_regime()` 根据技术分析阶段输出的 `ma_alignment`、`trend_score`、`volume_status` 三个指标，自动将当前行情归类为以下五种之一：

| 行情（regime） | 触发条件 | 匹配策略 |
|----------------|----------|----------|
| `trending_up` | 均线多头 + trend_score ≥ 70 | bull_trend, volume_breakout, ma_golden_cross |
| `trending_down` | 均线空头 + trend_score ≤ 30 | shrink_pullback, bottom_volume |
| `sideways` | 中性排列 或 35 ≤ trend_score ≤ 65 | box_oscillation, shrink_pullback |
| `volatile` | 量能异常 + 趋势评分居中 | chan_theory, wave_theory |
| `sector_hot` | （由 LLM 综合判断触发） | dragon_head, emotion_cycle |

### 2. 策略匹配

每种行情预设了 2-3 个推荐策略。Pipeline 会从中取前 3 个，将完整的策略定义（`name`、`display_name`、`description`、`instructions`）下发给 LLM。

### 3. 策略评估

LLM 收到策略后：
1. 阅读每个策略的 `instructions`（自然语言编写的判断标准）
2. 对照 `technical` 阶段返回的数据，逐条检查是否满足入场条件
3. 根据策略中的「评分调整」建议调整 `sentiment_score`
4. 在最终报告的「策略使用」章节列出使用了哪些策略及评估结论

### 4. required_tools

每个策略声明了它需要的 `required_tools`。这些 tool 名称对应 `tools/` 目录下的公开工具：

| tool 名称 | 说明 |
|-----------|------|
| `get_daily_history` | 历史 K 线数据 |
| `get_realtime_quote` | 实时行情 |
| `get_technical_indicators` | 技术指标（MA / RSI / 支撑阻力） |
| `search_stock_news` | 新闻搜索 + 情感分类 |
| `get_sector_rankings` | A 股行业板块排名 |

在 `full` / `quick` 模式下，Pipeline 已经调用了 `get_technical_indicators`，其输出包含了 `get_daily_history` 和 `get_realtime_quote` 的数据。只有策略额外需要 `search_stock_news` 或 `get_sector_rankings` 时，LLM 才需要单独调用。

---

## 如何编写自定义策略

在 `custom_strategies/` 目录下创建 `.yaml` 文件即可，**无需编写代码**。同名策略会覆盖内置策略。

### 最简模板

```yaml
name: my_strategy
display_name: 我的策略
description: 简短描述策略用途

instructions: |
  你的策略描述...
  用自然语言写出判断标准、入场条件、出场条件等。
```

### 完整模板

```yaml
name: my_strategy
display_name: 我的策略
description: 简短描述策略适用的市场场景

# 策略分类：trend（趋势）、pattern（形态）、reversal（反转）、framework（框架）
category: trend

# 策略需要的 tools（对应 tools/ 下的公开工具）
required_tools:
  - get_daily_history
  - get_technical_indicators

# 策略详细说明（自然语言，支持 Markdown 格式）
instructions: |
  **我的策略名称**

  判断标准：

  1. **条件一**：
     - 使用 `get_technical_indicators` 检查均线排列...

  2. **条件二**：
     - 量能要求...

  评分调整：
  - 满足条件时建议的 sentiment_score 调整
```

---

## 内置策略一览

| ID | 名称 | 分类 | 适用行情 |
|----|------|------|----------|
| bull_trend | 默认多头趋势 | trend | trending_up |
| shrink_pullback | 缩量回踩 | trend | trending_down, sideways |
| volume_breakout | 放量突破 | trend | trending_up |
| ma_golden_cross | 均线金叉 | trend | trending_up |
| box_oscillation | 箱体震荡 | framework | sideways |
| bottom_volume | 底部放量 | reversal | trending_down |
| dragon_head | 龙头策略 | trend | sector_hot |
| emotion_cycle | 情绪周期 | framework | sector_hot |
| chan_theory | 缠论 | framework | volatile |
| wave_theory | 波浪理论 | framework | volatile |
| one_yang_three_yin | 一阳夹三阴 | pattern | - |
