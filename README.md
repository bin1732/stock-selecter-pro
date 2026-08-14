# Stock Selecter Pro
## 多策略量化筛选

**Multi-strategy quantitative stock screening engine — 17 strategies across A-shares, Hong Kong, and US markets. Union/intersection/weighted combination modes, multi-period verification, and HTML visual reports. All code auditable, all data from public APIs.**
**多源数据量化选股引擎——覆盖A股/港股/美股，17种选股策略，支持并集/交集/加权组合与多周期验证，生成HTML可视化报告。全部代码可审计，全部数据来自公开API。**

---

## ✨ Features | 特性

- 📊 **17 Strategies** — Volume-price patterns, MACD, high dividend, low valuation, breakout, trend, Bollinger, chip concentration, cash flow quality, ROE DuPont, Fisher growth, turtle trading, momentum, and more
  17种策略：量价形态、MACD底背离、高股息、低估值、放量突破、趋势分析、布林带、筹码集中度、现金流质量、ROE杜邦、费雪成长、海龟交易、动量等
- 🌏 **3 Markets** — A-shares, Hong Kong, US stocks (with real capability differences clearly stated)
  三市场覆盖：A股、港股、美股（如实标注各市场数据能力边界）
- 🧩 **3 Combination Modes** — Union (any pass), Intersection (all pass), Weighted (scored by weights)
  三种组合模式：并集、交集、加权评分
- 📈 **Multi-Period Verification** — Daily + weekly cross-validation for stronger signals
  多周期验证：日线+周线交叉验证，信号更可靠
- 📄 **3 Report Formats** — Text, JSON, and interactive HTML with mini-charts and heatmaps
  三种报告格式：纯文本、JSON、交互式HTML（含迷你图和热力图）
- 🗄️ **Strategy Archive** — Optional SQLite-based performance tracking with backfill analytics
  策略表现档案：可选SQLite本地存储，回测分析胜率与收益
- 🛡️ **Transparent & Auditable** — All strategy code in plain Python, no black boxes, deterministic results
  透明可审计：全部策略源码可读，无黑盒，结果可复现
- 🔄 **Robust Data Source** — Eastmoney public API primary, Tencent/Sina as automatic failover
  健壮数据源：东方财富为主通道，腾讯/新浪自动故障切换
- 🧭 **Smart Guide** — Interactive 7-step onboarding wizard with real API connectivity tests
  智能引导：7步交互式向导，真实API连通性测试

## 🚀 Quick Start | 快速开始

### Installation in Coze / OpenClaw | 在扣子/OpenClaw中安装

```bash
# Via CLI
skillhub install stock-selecter-pro

# Or download the ZIP and extract to your skills directory
```

### Usage | 使用

```bash
cd scripts

# A-shares full screening
python run_screening.py --market A股 --mode hs300

# Hong Kong with technical strategies
python run_screening.py --market 港股 --strategies S01,S05,S08 --top 20

# US stocks with weighted mode
python run_screening.py --market 美股 --strategy-mode weighted --weights "S01=0.2,S05=0.3,S08=0.2"

# HTML report output
python run_screening.py --market 全部 --format html --output ./reports --top 30
```

## 📖 Strategy List | 策略清单

| ID | Strategy | Type | Data Source |
|----|----------|------|-------------|
| S01 | Red Fat Green Thin (volume-price) | Technical | Daily K-line |
| S02 | Rising Wave | Technical | Daily K-line |
| S03 | Pullback Shrinkage | Technical | Daily K-line |
| S04 | Sideways Consolidation | Technical | Daily K-line |
| S05 | MACD Bullish Divergence | Technical | Daily K-line |
| S06 | High Dividend | Fundamental | K-line + Valuation |
| S07 | Low Valuation | Fundamental | K-line + Valuation |
| S08 | Volume Breakout | Technical | Daily K-line |
| S09 | Trend Analysis | Technical | Daily K-line |
| S10 | Bollinger Lower Bounce | Technical | Daily K-line |
| S11 | Chip Concentration | Technical | Daily K-line |
| S12 | Cash Flow Quality | Fundamental | K-line + Financial |
| S13 | ROE DuPont Screening | Fundamental | K-line + Financial |
| S14 | Fisher Growth Stocks | Fundamental | K-line + Financial |
| S15 | Long-term Bottom Accumulation | Technical | K-line + Money Flow |
| S16 | Turtle Trading (Donchian) | Trend | Daily K-line |
| S17 | Momentum Strategy | Trend | Daily K-line |

## 📄 License | 许可证

MIT License — see [LICENSE](LICENSE) for details.

---

> ⚠️ **Risk Disclaimer: This tool provides technical and fundamental screening results only. It does not constitute investment advice. Stock markets carry risks; invest cautiously based on your own research and risk tolerance.**
>
> 风险声明：以上为技术形态与基本面筛选结果，不构成投资建议。股市有风险，投资需谨慎。

> ⚠️ **This repository is an open-source placeholder version. Future versions will be closed-source.**
>
> 本仓库为开源占位版本，后续版本将闭源。
