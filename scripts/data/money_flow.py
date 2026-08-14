"""个股资金流向数据获取层。

数据来源：东方财富公开资金流向API（push2.eastmoney.com / datacenter.eastmoney.com）。
全部为公开数据接口，不涉及认证，合规合法。

资金流向定义：
- 主力净流入 = 超大单净流入 + 大单净流入
- 超大单：单笔 >= 100万元
- 大单：单笔 >= 20万元且 < 100万元
- 中单：单笔 >= 4万元且 < 20万元
- 小单：单笔 < 4万元

API说明：
- 个股资金流：push2.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=30&secid=...
- 北向资金：push2.eastmoney.com/api/qt/ulist.np/get?...&secids=...
- 连续流入：基于多日资金流数据累加计算
"""

import requests

from ._http import push2_get, safe_float  # 东财共享客户端（主/备节点故障切换+数值清洗）

_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
})


def _market_code(code: str) -> str:
    if code.startswith("6"):
        return "1"
    return "0"


def _secid(code: str) -> str:
    return f"{_market_code(code)}.{code}"


def fetch_stock_money_flow(code: str, days: int = 30) -> list[dict]:
    """获取个股逐日资金流向数据。

    请求URL: https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get
    参数:
        lmt: 获取天数
        secid: 市场.代码 (如 1.600519)

    返回字段说明:
        - date: 日期
        - main_net_inflow: 主力净流入(万元) = 超大单净流入 + 大单净流入
        - super_large_net: 超大单净流入(万元)
        - large_net: 大单净流入(万元)
        - medium_net: 中单净流入(万元)
        - small_net: 小单净流入(万元)

    Returns:
        list[dict]: 逐日资金流向列表
    """
    secid = _secid(code)
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

        # 主力净流入(万元) = 超大单 + 大单
        super_large = safe_float(parts[1])
        large = safe_float(parts[2])
        medium = safe_float(parts[3])
        small = safe_float(parts[4])

        main_net = (super_large or 0) + (large or 0)

        result.append({
            "date": parts[0],
            "main_net_inflow": main_net,
            "super_large_net": super_large,
            "large_net": large,
            "medium_net": medium,
            "small_net": small,
        })
    return result


def fetch_north_bound_flow(days: int = 30) -> list[dict]:
    """获取北向资金每日净流入。

    请求URL: https://push2.eastmoney.com/api/qt/ulist.np/get

    北向资金包含：
    - 沪股通（secid=1.000015）净流入
    - 深股通（secid=0.399015）净流入

    返回字段说明:
        - date: 日期
        - north_net_inflow: 北向合计净流入(万元)
        - hgt_net: 沪股通净流入(万元)
        - sgt_net: 深股通净流入(万元)

    Returns:
        list[dict]: 逐日北向资金净流入列表
    """
    # 北向资金通过东方财富数据中心公开接口获取
    url = (
        "https://datacenter.eastmoney.com/securities/api/data/v1/get"
        "?sortColumns=TRADE_DATE&sortTypes=-1&pageSize=30&pageNumber=1"
        "&reportName=RPT_MONEYFLOW_HSGTH"
        "&columns=ALL&source=WEB&client=WEB"
    )
    try:
        resp = _session.get(url, timeout=15)
        data = resp.json()
    except Exception:
        return []

    items = data.get("result", {}).get("data", [])
    if not items:
        return []

    result = []
    for item in items[:days]:
        result.append({
            "date": item.get("TRADE_DATE", ""),
            "north_net_inflow": safe_float(item.get("NET_DEAL_AMOUNT", "0")),
            "hgt_net": safe_float(item.get("NET_DEAL_AMOUNT_HK2SH", "0")),
            "sgt_net": safe_float(item.get("NET_DEAL_AMOUNT_HK2SZ", "0")),
        })
    return result


def fetch_continuous_inflow(code: str, check_days: int = 5) -> dict:
    """判断个股是否连续N日主力净流入。

    基于 fetch_stock_money_flow 的多日资金流累计计算。

    请求URL: (内部调用) https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get

    返回字段说明:
        - is_continuous: 是否连续流入 (bool)
        - consecutive_days: 连续流入天数
        - total_inflow: 期间累计主力净流入(万元)
        - daily_details: 逐日细节

    Returns:
        dict: 连续流入判定结果
    """
    flows = fetch_stock_money_flow(code, days=max(30, check_days + 10))
    if not flows:
        return {
            "is_continuous": False,
            "consecutive_days": 0,
            "total_inflow": 0,
            "daily_details": [],
        }

    # 从最新日期开始往前检查
    consecutive = 0
    total = 0.0
    details = []

    for flow in flows:
        if flow.get("main_net_inflow", 0) > 0:
            consecutive += 1
            total += flow["main_net_inflow"]
            details.append(flow)
        else:
            break
        if consecutive >= check_days:
            break

    return {
        "is_continuous": consecutive >= check_days,
        "consecutive_days": consecutive,
        "total_inflow": round(total, 2),
        "daily_details": details,
    }
