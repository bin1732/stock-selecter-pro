"""数据层：多市场行情、基本面、资金流、板块数据获取。

基于东方财富公开API，纯HTTP请求，无认证依赖，合规合法。
所有数据均为公开行情数据，不涉及内幕或非公开信息。

模块清单（全部真实存在，可审计）：
- a_share.py:  A股行情/列表/多周期K线/批量并发/实时快照
- fundamental.py: 财务摘要/估值/批量基本面
- money_flow.py:  主力资金/北向资金/大单流向
- sector.py:      行业板块/概念板块排行及成分股
- hk_share.py:    港股行情/列表/K线（主板+创业板）
- us_share.py:    美股行情/列表/K线（NYSE+NASDAQ）
"""

# ── A股行情（全部函数在 a_share.py 中真实存在）──
from .a_share import (
    fetch_all_a_share_codes,
    fetch_daily_kline,
    fetch_batch_klines_parallel,
    fetch_minute_kline,
    fetch_weekly_kline,
    fetch_monthly_kline,
    get_realtime_quotes,
)

# ── 基本面（全部函数在 fundamental.py 中真实存在）──
from .fundamental import (
    fetch_financial_summary,
    fetch_valuation,
    fetch_fundamental_batch,
)

# ── 资金流 ──
from .money_flow import (
    fetch_stock_money_flow,
    fetch_north_bound_flow,
    fetch_continuous_inflow,
)

# ── 板块 ──
from .sector import (
    fetch_industry_ranking,
    fetch_concept_ranking,
    fetch_sector_stocks,
)

# ── 港股 ──
from .hk_share import (
    fetch_all_hk_codes,
    fetch_hk_daily_kline,
    fetch_hk_weekly_kline,
    fetch_hk_batch_klines,
)

# ── 美股 ──
from .us_share import (
    fetch_all_us_codes,
    fetch_us_daily_kline,
    fetch_us_batch_klines,
)

__all__ = [
    # A股
    "fetch_all_a_share_codes",
    "fetch_daily_kline",
    "fetch_batch_klines_parallel",
    "fetch_minute_kline",
    "fetch_weekly_kline",
    "fetch_monthly_kline",
    "get_realtime_quotes",
    # 基本面
    "fetch_financial_summary",
    "fetch_valuation",
    "fetch_fundamental_batch",
    # 资金流
    "fetch_stock_money_flow",
    "fetch_north_bound_flow",
    "fetch_continuous_inflow",
    # 板块
    "fetch_industry_ranking",
    "fetch_concept_ranking",
    "fetch_sector_stocks",
    # 港股
    "fetch_all_hk_codes",
    "fetch_hk_daily_kline",
    "fetch_hk_weekly_kline",
    "fetch_hk_batch_klines",
    # 美股
    "fetch_all_us_codes",
    "fetch_us_daily_kline",
    "fetch_us_batch_klines",
]
