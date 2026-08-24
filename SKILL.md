---
name: stock-selecter-pro
description: 覆盖A股/港股/美股的多源数据量化选股引擎，已实现17种选股策略（S01红肥绿瘦、S02上涨波段、S03回调缩量、S04横盘调整、S05 MACD底背离、S06高股息、S07低估值、S08放量突破、S09趋势分析、S10布林带下轨、S11筹码集中、S12现金流质量、S13 ROE杜邦筛选、S14费雪成长股、S15长期低位蓄力、S16海龟交易、S17动量策略），支持单策略、多策略组合筛选（union/intersection/weighted三种模式）。v1.0.3主流程支持A股/港股/美股三市场执行筛选（港股/美股技术面与估值策略可用，财务摘要/资金流策略如实不通过）。内置交互式新用户引导向导（真实API数据驱动）。触发词（精准触发，覆盖明确选股意图）：按策略名：ROE选股、ROE筛选、MACD选股、MACD筛选、MACD底背离、股息选股、高股息选股、估值选股、低估值、成长股筛选、费雪成长股、低位放量选股、长期低位选股、近期放量、趋势选股、形态选股、K线形态筛选、布林带选股、筹码集中选股、现金流质量、海龟策略、海龟选股、唐奇安通道、动量策略、动量选股、趋势跟踪选股按组合意图：组合选股、筛选股票、多策略选股、综合选股、并发选股、全部策略选股按结果要求：按ROE排名、按评分排名、按股息率排名、取交集、取并集按引导相关：选股引导、新手引导、选股向导、筛选向导明确排除（这些场景应激活其他skill）：- 任何包含具体股票代码/名称的个股分析请求- "帮我看看XX股票"、"XX公司怎么样"、"XX值不值得买"- "查一下行情"、"看资金流向"等纯数据查询
version: 1.0.3
compatibility: Python ≥3.10（仅标准库，零外部依赖）；Windows/Linux/macOS
metadata:
  language: zh-CN
  type: quant-screening
license: MIT
---

# 多策略量化筛选 Skill（stock-selecter-pro）v1.0.3

## 上架信息

- **展示名称**：多策略量化筛选
- **Slug**：stock-selecter-pro
- **版本**：1.0.3
- **短描述（≤200字）**：覆盖A股/港股/美股的多源数据量化选股引擎，内置17种真实可审计策略（量价形态/MACD/高股息/低估值/放量突破/趋势/布林带/筹码/现金流/ROE/费雪成长/海龟/动量等），支持并集/交集/加权组合、多周期验证，大盘环境由真实指数判定，A股全能力、港股/美股技术面与估值策略可用，输出回测胜率与文本/JSON/HTML三格式报告。数据均为公开接口真实返回，判定为确定性计算，不构成投资建议。

## 定位

覆盖 **A股/港股/美股** 的多源数据量化选股引擎。数据层以东方财富公开行情为主通道，K线多通道自动容灾（push2his 多节点 → 腾讯公开K线 → 新浪美股全历史），实时行情主/延迟节点自动切换，单通道不可达不影响结果产出；另含估值、资金流、板块与缓存并发层。

内置 **17 种真实可审计策略**：量价形态（红肥绿瘦/上涨波段/回调缩量/横盘调整）、MACD底背离、高股息、低估值、放量突破、趋势分析、布林带下轨反弹、筹码集中、现金流质量、ROE杜邦筛选、费雪成长股、长期低位蓄力、海龟交易（唐奇安通道突破）、动量策略。全部为确定性计算，同数据必同结果，无模型猜测、无编造补全。

- **组合筛选**：并集/交集/加权三种模式，权重可自定义；支持多周期交叉验证。
- **大盘环境**：由三市场真实指数（MA/量能/市场宽度信号）判定多空，叠加环境系数动态调整评分，并输出"若…则…"条件式趋势研判。
- **市场能力边界如实**：A股全能力；港股/美股支持技术面与估值策略（S06 高股息三市场可用；S07 低估值因通过条件含 ROE 防线——ROE 来自财务摘要（仅A股），故港股/美股如实不通过），依赖财务摘要的策略（S12/S13/S14）因无公开数据如实判定不通过；S15（长期蓄力）为技术面核心（长期低位+横盘蓄力），资金流仅辅助加分，无资金流数据时仍如实判定、可独立通过。
- **历史回测**：K线逐日信号回放（无前视偏差），输出每策略历史胜率与平均收益，样本不足如实标注；可选本地档案库追踪筛选后表现。
- **三格式报告**：纯文本、JSON、自包含交互式 HTML（大盘仪表盘、策略统计、K线迷你图、行业热力图）。

以上结果均基于历史数据与公开接口实时数据，不代表未来表现，不构成投资建议。股市有风险，投资需谨慎。公开数据延迟约 3-5 分钟。

## 合规声明（强制执行）

1. 本 Skill 仅基于公开历史行情数据进行技术形态与基本面筛选匹配，不构成投资建议。
2. 所有输出必须标注数据来源（东方财富/腾讯/新浪公开接口）、数据时点与刷新频率。
3. 禁止使用「必涨」「稳赚」「买入」「推荐」等承诺性或诱导性用语。
4. 每份报告末尾必须附风险声明：「以上为技术形态与基本面筛选结果，不构成投资建议。股市有风险，投资需谨慎。请结合自身风险承受能力独立决策。」
5. 所有数值均为真实接口返回，严禁编造、补全、美化或篡改。

---

## 架构总览

```
stock-selecter-pro/
├── SKILL.md                    # 本文件
├── references/                 # 安装指南 / 规范对齐说明
├── scripts/
│   ├── config.py               # 全策略参数配置 + 多市场参数 + 性能参数
│   ├── run_screening.py        # 多市场主入口（--market A股/港股/美股/全部；共享 run_pipeline 流水线）
│   ├── data/                   # 数据层
│   │   ├── __init__.py         # 统一导出所有数据模块函数
│   │   ├── a_share.py          # A股候选池列表(含行业字段)/日周K线/批量并发
│   │   ├── fundamental.py      # 财务摘要/估值/批量基本面
│   │   ├── money_flow.py       # 主力资金净流入/连续流入判断
│   │   ├── sector.py           # 东方财富板块（BK）行业/概念涨幅排行
│   │   ├── hk_share.py         # 港股行情/列表/K线（主板+创业板）
│   │   └── us_share.py         # 美股行情/列表/K线（NYSE+NASDAQ）
│   ├── indicators/             # 技术指标库
│   │   ├── __init__.py         # 导出 MA/EMA/MACD/RSI/BOLL/ADX/ATR/均线排列
│   │   └── technical.py        # 标准技术指标（MACD/RSI/BOLL/均线/ADX/ATR）
│   ├── strategies/             # 策略层（全部真实代码，可审计）
│   │   ├── __init__.py         # STRATEGY_REGISTRY + 统一导入
│   │   ├── base.py             # StrategyResult + make_result
│   │   ├── s01_volume_price.py # S01-S04 量价形态（红肥绿瘦/上涨波段/回调缩量/横盘调整）
│   │   ├── s02_macd_divergence.py   # S05 MACD底背离
│   │   ├── s03_high_dividend.py     # S06 高股息策略
│   │   ├── s04_low_valuation.py     # S07 低估值策略
│   │   ├── s05_volume_breakout.py   # S08 放量突破
│   │   ├── s06_trend_analysis.py    # S09 趋势分析
│   │   ├── s07_bollinger.py         # S10 布林带下轨反弹
│   │   ├── s08_chip_concentration.py # S11 筹码集中度
│   │   ├── s09_cashflow_quality.py   # S12 现金流质量
│   │   ├── s10_roe_screening.py      # S13 ROE杜邦筛选
│   │   ├── s11_fisher_growth.py      # S14 费雪成长股
│   │   ├── s12_long_consolidation.py # S15 长期低位蓄力
│   │   ├── s13_turtle.py             # S16 海龟交易（唐奇安通道突破）
│   │   └── s14_momentum.py           # S17 动量策略
│   ├── composers/              # 策略组合引擎
│   │   ├── __init__.py
│   │   └── strategy_composer.py # union/intersection/weighted 三种模式
│   ├── reports/                # 报告生成层
│   │   ├── __init__.py
│   │   ├── text_report.py      # 纯文本报告
│   │   ├── json_report.py      # JSON 结构化数据
│   │   └── html_report.py      # 自包含交互式 HTML 可视化报告
│   ├── cache/                  # 缓存层
│   │   └── __init__.py         # KlineCacheManager（写入后至次日15:30前有效的K线内存+文件双层缓存）
│   ├── archive/                # 策略表现档案库（可选模块）
│   │   ├── __init__.py         # 导出 tracker / analytics / reporter
│   │   ├── schema.py           # SQLite 建表（screening_log / pick_performance / strategy_stats）
│   │   ├── tracker.py          # 筛选快照存档 + 收益回填
│   │   ├── analytics.py        # 策略统计聚合 + 排名
│   │   └── reporter.py         # text / json 档案报告生成
```

---

## 真实策略清单（17种，全部代码可审计）

### 基础策略 (S01-S12)

| 编号 | 策略 | 策略文件 | 判定函数 | 依赖数据 |
|------|------|---------|---------|---------|
| S01 | 红肥绿瘦 | `strategies/s01_volume_price.py` | `check_s01_red_fat_green_thin` | 日K线 |
| S02 | 上涨波段 | `strategies/s01_volume_price.py` | `check_s02_rising_wave` | 日K线 |
| S03 | 回调缩量 | `strategies/s01_volume_price.py` | `check_s03_pullback_shrink` | 日K线 |
| S04 | 横盘调整 | `strategies/s01_volume_price.py` | `check_s04_sideways_consolidation` | 日K线 |
| S05 | MACD底背离 | `strategies/s02_macd_divergence.py` | `check_s05_macd_divergence` | 日K线 |
| S06 | 高股息策略 | `strategies/s03_high_dividend.py` | `check_s06_high_dividend` | 日K线 + 估值数据 |
| S07 | 低估值策略 | `strategies/s04_low_valuation.py` | `check_s07_low_valuation` | 日K线 + 估值数据 |
| S08 | 放量突破 | `strategies/s05_volume_breakout.py` | `check_s08_volume_breakout` | 日K线 |
| S09 | 趋势分析 | `strategies/s06_trend_analysis.py` | `check_s09_trend_analysis` | 日K线 |
| S10 | 布林带下轨反弹 | `strategies/s07_bollinger.py` | `check_s10_bollinger` | 日K线 |
| S11 | 筹码集中度 | `strategies/s08_chip_concentration.py` | `check_s11_chip_concentration` | 日K线 |
| S12 | 现金流质量 | `strategies/s09_cashflow_quality.py` | `check_s12_cashflow_quality` | 日K线 + 财务数据 |

### 进阶策略 (S13-S15)

| 编号 | 策略 | 策略文件 | 判定函数 | 依赖数据 | 创新点 |
|------|------|---------|---------|---------|--------|
| S13 | ROE杜邦筛选 | `strategies/s10_roe_screening.py` | `check_s13_roe_screening` | 日K线 + 财务数据 | ROE+盈利质量+杠杆健康 |
| S14 | 费雪成长股 | `strategies/s11_fisher_growth.py` | `check_s11_fisher_growth` | 日K线 + 财务数据 | PEG+成长性确认 |
| S15 | 长期低位蓄力 | `strategies/s12_long_consolidation.py` | `check_s15_long_consolidation` | 日K线（资金流辅助） | 深度回调+横盘蓄力+底部放量 |

### 趋势跟踪/动量策略 (S16-S17)

| 编号 | 策略 | 策略文件 | 判定函数 | 依赖数据 | 算法核心 |
|------|------|---------|---------|---------|---------|
| S16 | 海龟交易 | `strategies/s13_turtle.py` | `check_s16_turtle` | 日K线 | 唐奇安通道突破（收盘突破近20日最高）为核心通过条件；ADX趋势过滤 / MA60顺势 / 2*ATR止损参考为辅助加分 |
| S17 | 动量策略 | `strategies/s14_momentum.py` | `check_s17_momentum` | 日K线 | 近60日动量≥8%为核心通过条件；近20日动能延续 / MA60趋势背景 / RSI乖离过热过滤为辅助确认 |

> **策略判定函数签名**：所有策略函数入参为 `(klines, fundamental=None, money_flow=None)`，返回 `{"code", "name", "passed", "score", "signal_strength", "reasons", "details"}` 字典。

---

## 核心筛选流水线

### 阶段一：数据获取

- **A股**：`data/a_share.py` — 候选池列表（总市值降序，含行业字段）、日/周K线、批量并发获取
- **港股**：`data/hk_share.py` — 主板+创业板列表、日/周K线、批量获取
- **美股**：`data/us_share.py` — NYSE+NASDAQ列表、日K线、批量获取
- **基本面**：`data/fundamental.py` — 财务摘要（ROE/EPS/毛利率/净利率/资产负债率）、估值（PE/PB/PS/股息率/总市值）、批量获取
- **资金流**：`data/money_flow.py` — 个股主力资金净流入
- **板块**：`data/sector.py` — 东方财富板块分类（BK代码）行业/概念涨幅排行

**候选池口径（如实）**：full 模式下三市场统一按**总市值降序取前N近似**（A股默认 1000 / 港股美股默认 1000 / "全部"模式每市场 200），非指数成分精确匹配；已过滤 ST/退市/新股。A股候选池按市值排序而非当日涨跌幅排序，避免只覆盖当日大涨标的导致系统性漏筛。**按需取数**：仅当启用了对应依赖策略时才拉取估值（S06/S07/S14 的 PEG）、财务摘要（S07 的 ROE 防线、S12/S13/S14）、资金流（S15）；纯技术面策略组合（S01-S05/S08-S11/S16/S17）只拉K线，显著减少网络请求与耗时。

数据源：东方财富公开 HTTP API（`push2.eastmoney.com` / `push2his.eastmoney.com` / `datacenter-web.eastmoney.com` 财务摘要）为主通道，腾讯公开K线（`proxy.finance.qq.com`）与新浪美股（`stock.finance.sina.com.cn`）为容灾备选，请求间隔自动控制防封。

**网络健壮性（真实故障切换）**：
- 实时接口（列表/行情/估值）经 `data/_http.py` 共享客户端请求，主节点不可达时自动切换官方备用延迟节点 `push2delay.eastmoney.com`（延迟约3分钟，字段一致）。
- 历史K线接口（push2his）自动尝试多编号节点（79/92/91/无编号），首个返回有效数据的节点即用；全部节点不可达时自动切换备选公开通道：A股/港股走腾讯公开K线（proxy.finance.qq.com 优先，web.ifzq 触发风控时轮询备用入口），美股走新浪美股全历史日K（腾讯接口对美股仅返回首末两条，不可用）。备选通道输出与东财同构的K线字段（缺省字段如实置0，涨跌幅由收盘价序列真实计算），确保回测与技术面策略真实可用。
- 报告头部如实标注本次实际使用的数据通道（实时通道 + K线通道）；延迟节点下部分能力真实受限时（如美股候选池、资金流历史深度）会明确提示，不伪造数据、不静默。

### 阶段二：多策略并行判定

调用 `strategies/__init__.py` 中的 `STRATEGY_REGISTRY` 获取全部策略，通过 `run_screening.py` 的 `--strategies` 参数可指定启用的策略子集。每只股票并发执行所有启用策略的判定函数，支持 `--multi-period` 多周期验证。

**市场能力差异（如实）**：

| 市场 | K线 | 周线 | 基本面 | 资金流 |
|------|-----|------|--------|--------|
| A股 | 日K线 ✅ | ✅ | ✅ | ✅（抽样） |
| 港股 | 日K线 ✅ | ✅ | ❌ 无公开数据 | ❌ 无公开数据 |
| 美股 | 日K线 ✅ | ❌ 无公开数据 | ❌ 无公开数据 | ❌ 无公开数据 |

港股/美股标的缺少财务摘要/资金流数据时，S12/S13/S14 将如实判定为不通过（不伪造数值）；S07 低估值因通过条件含 ROE 防线（ROE 仅A股财务摘要有），在港股/美股如实不通过；S15（长期低位蓄力）的资金流辅助条件不可用，技术面核心条件（长期低位+横盘蓄力）仍如实判定、可独立通过；估值策略 S06 三市场可用。建议港股/美股使用技术面策略 S01-S05、S08-S11、S15、S16-S17（S16 海龟交易 / S17 动量策略均为纯K线技术面）与估值策略 S06。命令行会在执行前给出提示。

### 阶段三：组合引擎

调用 `composers/strategy_composer.py` 中的 `compose()` 函数，支持三种模式：

- **union**（并集）：任一策略通过即入选
- **intersection**（交集）：全部策略通过才入选
- **weighted**（加权）：`Σ(策略得分 × 策略权重) / Σ权重 × 10`，权重通过 `--weights "S01=0.15,S05=0.25,..."` 配置；入选需同时满足「综合得分 ≥ 3.0」且「至少一个策略真实通过核心条件」（防止仅靠辅助加分、核心条件全不满足的标的入选）

综合评分说明（`composers/strategy_composer.py`）：加权模式综合得分按上述公式在 0-10 区间内计算；主流程在组合得分基础上叠加 **大盘环境系数**（多头 1.05 / 震荡 0.85 / 空头 0.65，取自 `config.py` 的 `MARKET_*_COEFFICIENT`）得到最终评分。本版本不包含行业景气加成项。

### 阶段四：报告生成

三种输出格式，通过 `--format` 参数切换：

1. **纯文本报告**（`reports/text_report.py`）：含大盘环境、策略通过率统计、筛选结果排序、行业分布、风险声明
2. **JSON 结构化数据**（`reports/json_report.py`）：标准 Schema，便于程序化消费
3. **HTML 可视化报告**（`reports/html_report.py`）：自包含单文件，含大盘仪表盘、策略统计、可排序表格、K线迷你图、行业热力图、风险声明，纯 CSS/JS 无外部依赖

---

## 使用方式

```
cd scripts
# A股完整能力（含基本面/资金流策略）
python run_screening.py \
  --market A股              \  # A股|港股|美股|全部
  --mode full               \  # full=全市场候选（v1.0.3 仅支持 full）
  --strategies S01,S05,S07 \  # 指定策略，默认全部
  --strategy-mode weighted  \  # union|intersection|weighted
  --weights "S01=0.15,S05=0.25,S07=0.20" \
  --multi-period            \  # 启用多周期交叉验证（日+周线确认）
  --output ./output         \  # 输出目录
  --format all              \  # text|json|html|all
  --no-cache                \  # 禁用缓存
  --top 20                     # 输出前N只
  --cap 3000                   # 单市场候选池上限（默认 1000，放大覆盖更多标的，耗时增加）
  --all-cap 300                # "全部"市场模式每市场取样上限（默认 200）

# 港股/美股（技术面与估值策略可用，财务摘要/资金流策略如实不通过）
python run_screening.py --market 港股 --strategies S01,S05,S08 --top 20
python run_screening.py --market 美股 --strategy-mode weighted --weights "S01=0.2,S05=0.3,S08=0.2" --top 20
python run_screening.py --market 全部 --format html --output ./reports --top 30
```

未通过 `--market` 指定且处于交互终端时，每次运行会先弹出轻量市场询问：
`[1] A股  [2] 港股  [3] 美股  [4] 全部  [q] 退出（Enter 默认 A股）`；
非交互终端（如定时任务/管道）自动跳过询问，使用默认市场。

---

## Agent / 自动化调用执行指引（强制执行）

本 Skill 由智能体（Agent）代为执行时，**必须**遵循以下规则，否则会触发交互式引导阻塞或全量无谓耗时：

1. **始终追加 `--no-guide`**：交互式引导向导依赖终端实时输入，Agent 场景下会阻塞等待数分钟。
   ```bash
   python run_screening.py --no-guide --market A股 --top 20 --format all
   ```
2. **显式指定 `--market`**：不要留空让 `_quick_prompt` 询问（Agent 环境无交互输入时按默认 A股 执行，与用户意图可能不符）。
3. **按需缩小范围**：默认 full 模式拉取 A股前1000只、港股全市场、美股全市场的列表与K线，耗时约 1-2 分钟；若用户只要技术面结果，用 `--strategies S01,S05,S08` 等子集可跳过估值/财务/资金流请求；若只需少量结果，`--top 10` 可减少展示但不会减少全市场拉取。
4. **明确输出格式**：Agent 需要结构化结果时用 `--format json`（JSON 含 `total_passed` 真实通过总数与逐标的 `strategy_results`）；面向用户展示用 `--format text` 或 `html`。
5. **数据时效**：K线缓存写入后至次日 15:30 前有效（当日收盘后重复提问直接命中缓存，不再全量重拉）；需要强制刷新时用 `--no-cache`。
6. **同一交易日多次提问**：不要重复执行同参数全量命令——缓存已命中，重复命令仅浪费 Agent 轮次。
7. **回测与存档为可选**：`--backtest`（历史K线信号回放，抽样20只×500日）与 `--track`（本地SQLite存档）会增加耗时，仅在用户明确要求时启用。
8. **如实引用结果**：报告中的 `total_passed` 是未截断的真实通过数；展示名单可能按 `--top` 截断，向用户汇报时区分"通过 X 只，展示前 N 只"。

---

## 新用户交互式引导向导

### 概述

Skill 内置交互式引导向导（`scripts/guide.py`），新用户首次运行 `run_screening.py` 时自动启动。引导流程通过**东方财富公开API实时获取真实数据**作为每一步的建议依据，绝不编造数值。

**引导关闭方式**：引导完成并执行筛选后写入标记文件（`~/.stock_selecter_pro_guide_done`），下次运行自动跳过；亦可通过 `--no-guide` 跳过。引导中任一环节输入 `q` 退出 / `n` 取消则**不写标记**，下次仍会引导。

**每次运行的合规引导**：即使引导已关闭，每次运行仍会提供合规提示与轻量市场询问（明确区分 A股/港股/美股/全部），确保用户明确知晓所选市场与数据能力边界后再执行筛选。

### 引导流程（7步）

| 步骤 | 名称 | 说明 | 数据来源 |
|------|------|------|---------|
| 1 | 欢迎页 | 展示Skill功能、17种策略概览、风险提示 | 配置与策略注册表 |
| 2 | 环境检测 | 真实调用6个东方财富API接口测试连通性 | `push2.eastmoney.com` / `push2his.eastmoney.com` |
| 3 | 市场选择 | 查询A股/港股/美股当前可获取的真实股票数量 | 三大市场列表接口实时查询 |
| 4 | 策略适配 | 按所选市场获取对应指数真实K线（A股:上证+深证 / 港股:恒生+国企 / 美股:道琼斯+纳指），MA均线判断多空，智能适配策略组合 | 对应市场指数近60日K线（`config.INDEX_SECIDS`） |
| 5 | 参数配置 | 引导设置输出格式、TOP-N、策略模式、多周期等 | 配置项 |
| 6 | 执行确认 | 预览完整配置并执行筛选 | 继承引导预设参数 |
| 7 | 档案追踪 | 询问是否开启策略表现档案库（本地SQLite，可选） | 本地配置项 |

### 设计原则

- **不强制起点**：用户可从任意环节切入（`--step market_select`）
- **自由导航**：每步可跳过 (`s`)、返回 (`b`)、退出 (`q`)
- **真实数据驱动**：环境检测、市场数量、策略适配全部基于API实时返回
- **非强制**：`--no-guide` 跳过、标记文件记忆"下次不再显示"

### CLI 控制

```bash
# 跳过引导直接执行
python run_screening.py --no-guide

# 强制启动引导
python run_screening.py --guide

# 从指定步骤启动引导
python guide.py --step strategy_recommend
```

### 配置项

```python
# config.py
GUIDE_ENABLED = True            # 全局引导开关
GUIDE_SKIP_ON_FLAGFILE = True   # 引导完成后写标记文件，下次跳过
GUIDE_FLAGFILE = ".stock_selecter_pro_guide_done"  # 标记文件名（位于 HOME 目录）
```

### 环境检测接口清单

引导步骤2会依次测试以下6个东方财富公开API：

| 接口 | URL | 验证方式 |
|------|-----|---------|
| A股列表 | `push2.eastmoney.com/api/qt/clist/get?fs=m:0+t:6,...` | 检查返回 total 字段 |
| 实时行情 | `push2.eastmoney.com/api/qt/ulist.np` | 检查贵州茅台+平安银行实时行情 |
| 日K线 | `79.push2his.eastmoney.com/api/qt/stock/kline/get` | 检查贵州茅台日K线 |
| 港股列表 | `push2.eastmoney.com/api/qt/clist/get?fs=m:128+t:3,...` | 检查返回 total 字段 |
| 美股列表 | `push2.eastmoney.com/api/qt/clist/get?fs=m:105+t:3,...` | 检查返回 total 字段 |
| 估值数据 | `push2.eastmoney.com/api/qt/stock/get` | 检查贵州茅台估值字段 |

### 策略适配逻辑

引导步骤4按当前所选市场（A股:上证000001+深证399001 / 港股:恒生HSI+国企HSCEI / 美股:道琼斯DJI+纳斯达克IXIC；"全部"模式以A股大盘为参考）取对应指数真实近60日K线，计算 MA5/MA20/MA60 判断大盘多空：

- **多头**（MA5 > MA20 > MA60）：适配趋势跟踪类策略（S01/S02/S08/S09/S14/S16/S17）
- **空头**（MA5 < MA20 < MA60）：适配底部反转+防御类策略（S05/S10/S15/S06/S07）
- **震荡**（均线交织）：适配回调+估值安全类策略（S03/S04/S06/S07/S01）

所有适配均基于真实指数数据计算，不做主观判断。

---

## 数据源声明

| 接口 | URL | 用途 |
|------|-----|------|
| 行情列表 | `push2.eastmoney.com/api/qt/clist/get` | A股/港股/美股全市场列表 |
| 实时快照 | `push2.eastmoney.com/api/qt/ulist.np` | 股票实时行情 |
| 日K线 | `79.push2his.eastmoney.com/api/qt/stock/kline/get` | 日/周K线（主通道） |
| K线备选 | `proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get` | A股/港股K线备选通道（push2his不可达时自动切换） |
| K线备选 | `stock.finance.sina.com.cn/usstock/api/jsonp.php/...US_MinKService.getDailyK` | 美股全历史日K备选通道 |
| 估值数据 | `push2.eastmoney.com/api/qt/stock/get` | PE/PB/PS/股息率/总市值 |
| 财务摘要 | `datacenter-web.eastmoney.com/api/data/v1/get`（reportName=`RPT_F10_FINANCE_MAINFINADATA`） | ROE/EPS/毛利率/净利率等（仅A股） |
| 档案回测 | `79.push2his.eastmoney.com/api/qt/stock/kline/get` | 获取最新收盘价用于收益率计算 |

行情/列表/估值接口均为东方财富公开行情 API（push2his 不可达时K线自动切换腾讯/新浪公开通道），无需认证，数据延迟 3-5 分钟（非 Level-2）。

---

## 策略表现档案库

### 概述

策略表现档案库是一个**可选模块**，用于追踪每次筛选结果的真实市场表现。数据全部存储在本地 SQLite 数据库中，**绝不上传**。

### 功能

| 功能 | 说明 |
|------|------|
| 筛选快照 | 每次筛选执行时自动记录：市场环境、启用策略、候选数量、通过标的详情 |
| 回测验证 | 7 个自然日后自动获取真实收盘价，计算 1 周 / 1 月收益率 |
| 聚合统计 | 按策略维度聚合计算：胜率、平均收益、最佳标的、运行次数 |
| 档案报告 | 生成 text/json 格式的策略表现报告，含排名、近期摘要、覆盖统计 |

### 使用方式

```bash
# 开启追踪（筛选完成后自动存档）
python run_screening.py --track

# 回填收益 + 刷新统计 + 执行筛选
python run_screening.py --analyze

# 回填 + 刷新 + 存档（组合使用）
python run_screening.py --track --analyze

# 仅生成档案报告（不执行筛选）
python run_screening.py --archive-report --format text
python run_screening.py --archive-report --format json
```

**交互式引导**：新用户引导第 7 步会询问是否开启档案追踪，选是后每次筛选自动存档。

### 数据安全

- **纯本地存储**：所有数据写入本地 SQLite 文件，不联网上传
- **可随时重置**：删除 `archive/stock_selecter.db` 即清除所有档案数据，不影响核心功能
- **默认关闭**：默认不开启，需用户通过引导第 7 步或 `--track` 参数主动启用
- **不修改策略权重**：仅提供统计数据供参考，不自动调整策略参数

### 数据库表结构

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `screening_log` | 筛选执行记录 | run_id, market, strategy_ids, candidate_count, passed_count |
| `pick_performance` | 入选标的跟踪 | stock_code, stock_name, strategy_id, snapshot_price, return_1w, return_1m |
| `strategy_stats` | 策略聚合统计 | strategy_id, win_rate_1w, win_rate_1m, avg_score, best_pick_code |

---

## 已知限制

1. **数据延迟**：东方财富公开接口为免费数据，存在 3-5 分钟延迟，非 Level-2 实时数据
2. **财报滞后**：基本面数据基于最新已披露财报，滞后 1-4 个月
3. **港股/美股覆盖限制**：仅覆盖东方财富接口可访问的标的，部分小盘股/粉单市场不在覆盖范围
4. **港股/美股数据能力边界**：港股无财务摘要/资金流公开数据（K线与周线可用），美股无财务摘要/资金流/周线公开数据（仅日K线可用）；依赖财务摘要的策略（S12/S13/S14）在港股/美股如实判定不通过，S07 因通过条件含 ROE 防线（仅A股财务数据）在港股/美股如实不通过，S15 资金流辅助条件不可用（技术面核心仍如实判定），不伪造数值；估值策略 S06 与纯技术面策略（S01-S05/S08-S11/S15/S16-S17）三市场可用
5. **接口稳定性**：东方财富公开接口非官方 API，存在接口变更风险；所有接口调用均标注 URL 和参数，变更时便于定位修复。K线接口已内置腾讯/新浪公开备选通道，单通道不可达时自动切换，不影响回测与技术面策略
6. **S12 现金流质量**策略依赖财务数据API，部分字段可能因接口返回格式变化而取不到值，此时策略结果中会标注为实际数据不满足阈值而非假数据

---

## 风险声明（强制执行）

> **以上为技术形态与基本面筛选结果，不构成投资建议。股市有风险，投资需谨慎。请结合基本面与自身风险承受能力独立决策。**

---

## 审计与可复现性

- 所有策略代码均位于 `scripts/strategies/*.py`，函数名以 `check_` 开头，无外部依赖
- 所有数据获取函数均标注数据源 URL 与参数说明，位于 `scripts/data/*.py`
- 所有判定逻辑为纯数学运算，无随机性，同数据必同结果
- 配置参数全部集中在 `scripts/config.py`，可自定义所有策略阈值
- 缓存机制位于 `scripts/cache/__init__.py`，使用 `--no-cache` 强制刷新
- 一键自检：`python scripts/validate.py`（frontmatter 合规 / 版本一致性 / 引用完整性 / 策略注册表一致性 / 语法 / 表面话术）

*（说明内容以实际代码与市场数据为准，仅供参考）*
