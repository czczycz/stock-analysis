# 交易策略目录

本目录存放**内置策略文件**（YAML 格式）。Skill 启动时自动加载此目录下所有 `.yaml` 文件。

## 如何编写自定义策略

在 `custom_strategies/` 目录下创建 `.yaml` 文件即可，**无需编写代码**。
同名策略会覆盖内置策略。

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

# 策略需要的数据类型（文档用途），可选
required_tools:
  - price_history
  - technical_analysis

# 策略详细说明（自然语言，支持 Markdown 格式）
instructions: |
  **我的策略名称**

  判断标准：

  1. **条件一**：
     - 检查均线排列...

  2. **条件二**：
     - 量能要求...

  评分调整：
  - 满足条件时建议的 sentiment_score 调整
```

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
