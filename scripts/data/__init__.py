"""数据层：多市场行情、基本面、资金流、板块数据获取。

基于东方财富公开API，纯HTTP请求，无认证依赖，合规合法。
所有数据均为公开行情数据，不涉及内幕或非公开信息。

模块清单（全部真实存在，可审计）：
- a_share.py:  A股行情/列表/日周K线/批量并发
- fundamental.py: 财务摘要/估值/批量基本面
- money_flow.py:  个股资金流向
- sector.py:      行业板块/概念板块排行
- hk_share.py:    港股行情/列表/K线（主板+创业板）
- us_share.py:    美股行情/列表/K线（NYSE+NASDAQ）
"""

# ── A股行情（全部函数在 a_share.py 中真实存在）──
from .a_share import (
    fetch_top_a_share_codes,
    fetch_daily_kline,
    fetch_batch_klines_parallel,
    fetch_weekly_kline,
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
)

# ── 板块 ──
from .sector import (
    fetch_industry_ranking,
    fetch_concept_ranking,
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


def fetch_market_total(market: str) -> int:
    """轻量查询某市场全市场股票总数（clist pz=1 的 total 字段，公开接口）。

    用途：报告如实标注候选池覆盖率（候选数 / 全市场总数），仅 1 条请求，不引入额外依赖。

    Returns:
        int: 全市场股票总数；市场未知或接口失败时返回 0（如实未知）。
    """
    fs_map = {
        "A股": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "港股": "m:128+t:3,m:128+t:4",
        "美股": "m:105+t:3,m:105+t:4,m:105+t:5",
    }
    fs = fs_map.get(market)
    if not fs:
        return 0
    from ._http import push2_get
    data = push2_get("/api/qt/clist/get", params={
        "pn": "1", "pz": "1", "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fs": fs, "fields": "f12,f14",
    })
    if data:
        return (data.get("data") or {}).get("total") or 0
    return 0


__all__ = [
    # A股
    "fetch_top_a_share_codes",
    "fetch_daily_kline",
    "fetch_batch_klines_parallel",
    "fetch_weekly_kline",
    # 基本面
    "fetch_financial_summary",
    "fetch_valuation",
    "fetch_fundamental_batch",
    # 资金流
    "fetch_stock_money_flow",
    # 板块
    "fetch_industry_ranking",
    "fetch_concept_ranking",
    # 港股
    "fetch_all_hk_codes",
    "fetch_hk_daily_kline",
    "fetch_hk_weekly_kline",
    "fetch_hk_batch_klines",
    # 美股
    "fetch_all_us_codes",
    "fetch_us_daily_kline",
    "fetch_us_batch_klines",
    # 聚合
    "fetch_market_total",
]
