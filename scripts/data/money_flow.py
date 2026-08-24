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
    return result
