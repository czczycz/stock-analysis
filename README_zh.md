# Stock Analysis Skill — 多策略股票分析

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

[English](README.md)

一个 AI Agent Skill，用于多策略股票分析。通过可配置的流水线生成结构化的**决策看板**（买入 / 持有 / 卖出）。支持 **A 股、港股和美股**。

> 本项目改写自 [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)，重新架构为零配置的 Agent Skill，可直接被 [Openclaw](https://github.com/openclaw/openclaw)、[Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) 等支持 Skill 的 AI Agent 使用。

## 快速开始

1. 安装 [uv](https://docs.astral.sh/uv/)
2. 将本 Skill 目录放置在 Agent 可访问的路径下
3. 让 Agent 分析任意股票：

```
帮我分析一下 600519
```

Agent 会自动执行分析流水线，返回格式化的决策看板。以下是贵州茅台（600519）的示例输出：

<details>
<summary>📊 示例输出 — 贵州茅台（600519）</summary>

```markdown
# 贵州茅台（600519）分析报告

## 🎯 核心结论

| 项目 | 内容 |
|------|------|
| 一句话总结 | 短期承压震荡，高管风险事件待消化 |
| 信号类型 | 🟡 观望信号 |
| 决策建议 | **持有** — 置信度：中 |
| 情绪评分 | 38 / 100 |

**空仓建议**：等待负面消息消化，关注 1380 支撑位企稳后的低吸机会
**持仓建议**：暂时持有观望，若跌破 1380 考虑减仓

---

## 📈 数据透视

**趋势状态**：均线空头排列 · 趋势评分 35 · ⚠️ 偏弱

| 指标 | 数值 |
|------|------|
| 现价 | 1413.64 |
| MA5 / MA10 / MA20 | 1400.90 / 1407.30 / 1448.69 |
| RSI | 46.3 |
| 量比 | 1.14 · 正常 |
| 支撑位 / 阻力位 | 1323.69 / 1555.00 |

---

## 📰 情报与风险

**舆情倾向**：偏空

重要新闻：
- ❌ 贵州茅台：副总经理蒋焰被实施留置
- ❌ 贵州茅台财务总监、董事会秘书蒋焰被留置
- ❌ 贵州茅台：董事长陈华代行董秘职责

⚠️ **风险提示**：公司高管被留置属重大治理风险事件，短期情绪面承压

---

## 📋 策略使用

本次分析使用了以下策略：
1. **箱体震荡**（box_oscillation）— 识别价格箱体区间
2. **缩量回踩**（shrink_pullback）— 检测缩量回踩均线支撑信号

---

## 🎯 作战计划

| 点位 | 价格 |
|------|------|
| 理想买点 | 1380（箱体底部支撑） |
| 次优买点 | 1400（MA5 附近） |
| 止损位 | 1320（跌破箱体下沿） |
| 止盈位 | 1500（接近 MA20 阻力） |

⚠️ 以上内容由 AI 生成，仅供参考，不构成投资建议。
```

</details>

## 环境要求

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** — 脚本依赖在首次运行时自动安装
- **平台**：Windows、Linux、macOS

无需 API Key，无需手动配置。所有数据均来自免费公开数据源（腾讯财经、AkShare、yfinance）。

## 流水线模式

`PipelineManager` 内置多种分析模式：

| 模式 | 阶段 | 适用场景 |
|------|------|----------|
| `full` | 技术分析 → 情报 → 风险 → 策略 | 完整分析 **（默认）** |
| `quick` | 技术分析 → 策略 | 快速信号，跳过新闻和风险 |
| `news` | 情报 → 风险 | 仅情绪与风险筛查 |
| `technical` | 技术分析 | 仅技术指标 |

```bash
# 完整分析（默认）
uv run scripts/pipeline.py analyze 601919

# 快速模式 — 仅技术分析 + 策略
uv run scripts/pipeline.py analyze 601919 --mode quick

# 列出所有可用模式
uv run scripts/pipeline.py modes
```

### 自定义模式

通过组合可用阶段（`technical`、`intel`、`risk`、`strategy`）注册自定义流水线模式：

```python
from pipeline import manager

manager.register_mode(
    name="risk_check",
    stages=["technical", "risk"],
    description="技术分析 + 风险 — 快速风险筛查",
)
```

## 自定义策略

在 `custom_strategies/` 目录下放入 `.yaml` 文件即可添加自定义交易策略。同名文件会覆盖内置策略。11 种内置策略根据市场状态自动匹配。

```yaml
name: my_strategy
display_name: 我的策略
description: 策略适用场景描述
instructions: |
  入场条件、出场规则、仓位管理...
```

完整模板请参考 [`strategies/README.md`](strategies/README.md)。

## 免责声明

本 Skill 仅供**学习和研究使用**，不构成任何投资建议。在做出任何投资决策之前，请务必进行独立的尽职调查。作者不对任何经济损失承担责任。
