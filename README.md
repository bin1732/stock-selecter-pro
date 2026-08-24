# Stock Selecter Pro
## 多策略量化筛选

**Multi-strategy quantitative stock screening engine — 17 strategies across A-shares, Hong Kong, and US markets. Union/intersection/weighted combination modes, multi-period verification, and HTML visual reports. All data from public APIs.**
**多源数据量化选股引擎——覆盖A股/港股/美股，17种选股策略，支持并集/交集/加权组合与多周期验证，生成HTML可视化报告。全部数据来自公开API。**

---

## ✨ Features | 特性

### 三市场覆盖
- **A股**：全能力（17种策略全部可用）
- **港股/美股**：技术面与估值策略可用；依赖财务摘要的策略如实判定不通过

### 17 种选股策略
量价形态（红肥绿瘦/上涨波段/回调缩量/横盘调整）、MACD底背离、高股息、低估值、放量突破、趋势分析、布林带下轨反弹、筹码集中、现金流质量、ROE杜邦筛选、费雪成长股、长期低位蓄力、海龟交易（唐奇安通道突破）、动量策略。

### 组合与验证
- **三种组合模式**：并集 / 交集 / 加权评分
- **多周期交叉验证**：日/周/月多周期信号叠加
- **大盘环境系数**：基于真实指数的多空判定，动态调整策略权重

### 数据层
- 东方财富公开行情主通道
- K线多通道自动容灾（push2his 多节点 → 腾讯公开K线 → 新浪美股全历史）
- 实时行情主/延迟节点自动切换
- 单通道不可达不影响结果产出

### 输出格式
- 纯文本报告
- JSON 结构化输出
- 自包含交互式 HTML（大盘仪表盘、策略统计、K线迷你图、行业热力图）

---

## ⚠️ 风险提示 | Risk Disclaimer

本技能仅用于数据展示与研究参考，**不构成任何投资建议**。股市有风险，投资需谨慎。所有数据均来自公开接口，不对数据准确性与完整性做保证。

This tool is for research and reference only and **does not constitute investment advice**. All data is sourced from public APIs.

---

## 📄 License | 许可证

MIT License — see [LICENSE](LICENSE) for details.
