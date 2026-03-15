# Stock Analysis Skill — 多策略股票分析

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

[English](README.md)

一个 AI Agent Skill，用于多策略股票分析。通过可配置的流水线生成结构化的**决策看板**（买入 / 持有 / 卖出）。支持 **A 股、港股和美股**。

> 本项目改写自 [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)，重新架构为零配置的 Agent Skill，可直接被 [Cursor](https://www.cursor.com/)、[Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) 等支持 Skill 的 AI Agent 使用。

## 快速开始

1. 安装 [uv](https://docs.astral.sh/uv/)
2. 将本 Skill 目录放置在 Agent 可访问的路径下
3. 让 Agent 分析任意股票：

```
帮我分析一下 601919
```

Agent 会自动执行分析流水线，返回格式化的决策看板。

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
