# references/agent-skills-spec.md — Agent Skills 规范对齐说明

> 本 skill 遵循 Agent Skills 规范（agentskills.io）。本文说明 frontmatter 字段与渐进披露用法，供宿主正确加载、用户理解结构。

## frontmatter 字段

| 字段 | 值 | 说明 |
|------|-----|------|
| `name` | `stock-selecter-pro` | 唯一标识；安装目录名须与其一致（见 installation-guide.md） |
| `description` | 见 SKILL.md | 触发依据：能力 + 触发词 + 明确排除（个股分析/纯数据查询走其他能力） |
| `version` | 1.0.4 | 版本号 |
| `compatibility` | Python ≥3.10 / 标准库零依赖 / Windows·Linux·macOS | 环境要求 |
| `metadata` | language: zh-CN / type: quant-screening | 附加元信息 |

## 渐进披露（四阶段）

1. **发现（Advertise）**：宿主只读 `name` + `description`，判定是否需要触发（含明确排除场景）。
2. **激活（Load）**：触发后读 SKILL.md 全文，获取架构、17 策略清单、筛选流水线与使用方式。
3. **参考（References）**：按需读取安装指南 / 规范说明（本 skill 规则与配置均集中在 SKILL.md 与 scripts/config.py）。
4. **执行（Scripts）**：调用 `scripts/run_screening.py` 执行筛选（`--no-guide --market A股 --top 20 --format json` 为 Agent 标准调用）。

## 目录约定

- `SKILL.md`：定位、17 策略清单、筛选流水线、使用方式、Agent 执行指引、数据源声明、风险声明。
- `references/`：安装指南 / 规范对齐说明。
- `scripts/`：可执行引擎（Python ≥3.10 标准库零依赖；数据层/指标层/策略层/组合层/报告层/缓存/档案库）。
- 本地数据：档案库 SQLite（`scripts/archive/stock_selecter.db`）与引导标记文件，随使用产生，不随 skill 分发。

## 触发纪律

- description 触发词命中才触发；明确排除场景（含具体股票代码/名称的个股分析、纯行情/资金流查询）不触发，走宿主常规能力。
- Agent 执行必须遵循 SKILL.md「Agent / 自动化调用执行指引」（--no-guide、显式 --market、按需缩小范围等）。
- 回答模式遵循 SKILL.md「回答模式（人性化双模式）」：用户明确要简洁时用简单回答（结论式 + 风险提示），否则用标准回答（完整报告）；两模式可随时切换。
