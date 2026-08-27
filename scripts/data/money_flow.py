"""个股资金流向数据获取层。

数据来源：东方财富公开资金流向API（push2.eastmoney.com）。
全部为公开数据接口，不涉及认证，合规合法。

资金流向定义：
- 主力净流入 = 超大单净流入 + 大单净流入
- 超大单：单笔 >= 100万元
- 大单：单笔 >= 20万元且 < 100万元
- 中单：单笔 >= 4万元且 < 20万元
- 小单：单笔 < 4万元

API说明：
- 个股资金流：push2.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=30&secid=...
- 连续流入：基于多日资金流数据累加计算
"""

from ._http import push2_get, safe_float  # 东财共享客户端（主/备节点故障切换+数值清洗）
from .fundamental import _RESULT_CACHE  # 共享结果级缓存（与财务/估值同实例，键带 flow: 前缀）


def _secid(code: str, market: str = "A股") -> str:
    """生成指定市场标的在 push2 fflow 接口的 secid。

    - A股：1.沪（6开头）/ 0.深
    - 港股：116.{5位代码}（主板/创业板统一走 116，真实返回）
    - 美股：105.{代码}（公开接口对美股不返回日级资金流数据，如实无）
    """
    code = str(code).strip()
    if market == "港股":
        return f"116.{code.zfill(5)}"
    if market == "美股":
        return f"105.{code}"
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def fetch_stock_money_flow(code: str, days: int = 30, market: str = "A股", use_cache: bool = True) -> list[dict]:
    """获取个股逐日资金流向数据。

    请求URL: https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get
    参数:
        lmt: 获取天数
        secid: 市场.代码 (如 1.600519 / 116.00700)

    返回字段说明:
        - date: 日期
        - main_net_inflow: 主力净流入(万元) = 超大单净流入 + 大单净流入
        - super_large_net: 超大单净流入(万元)
        - large_net: 大单净流入(万元)
        - medium_net: 中单净流入(万元)
        - small_net: 小单净流入(万元)

    数据可用性：
    - A股/港股：真实返回逐日资金流（116.00700 等港股 secid 真实返回数据）
    - 美股：公开接口对美股不返回该口径数据（105.AAPL 无数据），如实返回 []

    Returns:
        list[dict]: 逐日资金流向列表

    结果级缓存：同市场同代码当日有效（次日15:30过期，与K线缓存一致），
    仅缓存含真实数据的结果（网络失败返回空不缓存，下次重试）。
    """
    cached = _RESULT_CACHE.get(f"flow:{market}:{code}:{days}", 1) if use_cache else None
    if cached is not None:
        return cached

    secid = _secid(code, market)
    data = push2_get("/api/qt/stock/fflow/daykline/get", params={
        "lmt": days,
        "secid": secid,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
    })
    if not data:
        return []

    klines = data.get("data", {}).get("klines", [])
    if not klines:
        return []

    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 10:
            continue

        # 东财 fflow/daykline 行格式: 日期,主力净流入,小单,中单,大单,超大单 (单位:万元)
        # 主力净流入 = 超大单 + 大单（东财口径），接口直接返回主力值，直接采用
        main_net = safe_float(parts[1])
        small = safe_float(parts[2])
        medium = safe_float(parts[3])
        large = safe_float(parts[4])
        super_large = safe_float(parts[5]) if len(parts) > 5 else None

        result.append({
            "date": parts[0],
            "main_net_inflow": main_net,
            "super_large_net": super_large,
            "large_net": large,
            "medium_net": medium,
            "small_net": small,
        })

    # 仅缓存含真实数据的列表（网络失败返回空不缓存，下次重试；美股无口径如实空亦不缓存）
    if use_cache and result:
        _RESULT_CACHE.set(f"flow:{market}:{code}:{days}", 1, result)
    return result
