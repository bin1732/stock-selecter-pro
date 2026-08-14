"""板块数据获取层：行业板块 + 概念板块排行及成分股。

数据来源：东方财富公开板块行情API（push2.eastmoney.com）。
全部为公开数据接口，不涉及认证，合规合法。

覆盖范围：
- 申万一级行业板块（约31个）
- 概念板块（约400+个）
- 板块成分股列表

行业板块字段说明（f12/f14/f2/f3/f4/f104/f105/f128等）：
- f12: 板块代码
- f14: 板块名称
- f2: 最新价
- f3: 涨跌幅(%)
- f4: 涨跌额
- f104: 上涨家数
- f105: 下跌家数
- f128: 领涨股名称
- f140: 领涨股代码

API说明：
- 行业板块：push2.eastmoney.com/api/qt/clist/get?fs=m:90+t:2&...
- 概念板块：push2.eastmoney.com/api/qt/clist/get?fs=m:90+t:3&...
- 成分股：push2.eastmoney.com/api/qt/clist/get?fs=b:BKxxxx&...
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


def fetch_industry_ranking(sort_by: str = "f3") -> list[dict]:
    """获取申万一级行业板块实时涨跌幅排行。

    请求URL: https://push2.eastmoney.com/api/qt/clist/get
    参数:
        fs=m:90+t:2  (行业板块)
        fid=f3       (按涨跌幅排序)

    返回字段说明:
        - code: 板块代码 (如 BK0427)
        - name: 板块名称 (如 半导体)
        - price: 板块指数
        - pct_chg: 涨跌幅(%)
        - change: 涨跌额
        - up_count: 上涨家数
        - down_count: 下跌家数
        - lead_stock_name: 领涨股名称
        - lead_stock_code: 领涨股代码

    Returns:
        list[dict]: 行业板块排行列表
    """
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": sort_by,
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f14,f104,f105,f128,f140",
    }
    data = push2_get("/api/qt/clist/get", params=params)
    if not data:
        return []

    items = data.get("data", {}).get("diff", [])
    result = []
    for item in items:
        result.append({
            "code": item.get("f12", ""),
            "name": item.get("f14", ""),
            "price": safe_float(item.get("f2")),
            "pct_chg": safe_float(item.get("f3")),
            "change": safe_float(item.get("f4")),
            "up_count": safe_float(item.get("f104")),
            "down_count": safe_float(item.get("f105")),
            "lead_stock_name": item.get("f128", ""),
            "lead_stock_code": item.get("f140", ""),
        })
    return result


def fetch_concept_ranking(sort_by: str = "f3") -> list[dict]:
    """获取概念板块实时涨跌幅排行。

    请求URL: https://push2.eastmoney.com/api/qt/clist/get
    参数:
        fs=m:90+t:3  (概念板块)
        fid=f3       (按涨跌幅排序)

    返回字段说明:
        - code: 板块代码 (如 BK0715)
        - name: 板块名称 (如 AI芯片)
        - price: 板块指数
        - pct_chg: 涨跌幅(%)
        - change: 涨跌额
        - up_count: 上涨家数
        - down_count: 下跌家数
        - lead_stock_name: 领涨股名称
        - lead_stock_code: 领涨股代码

    Returns:
        list[dict]: 概念板块排行列表（top 200）
    """
    params = {
        "pn": "1",
        "pz": "200",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": sort_by,
        "fs": "m:90+t:3",
        "fields": "f2,f3,f4,f12,f14,f104,f105,f128,f140",
    }
    data = push2_get("/api/qt/clist/get", params=params)
    if not data:
        return []

    items = data.get("data", {}).get("diff", [])
    result = []
    for item in items:
        result.append({
            "code": item.get("f12", ""),
            "name": item.get("f14", ""),
            "price": safe_float(item.get("f2")),
            "pct_chg": safe_float(item.get("f3")),
            "change": safe_float(item.get("f4")),
            "up_count": safe_float(item.get("f104")),
            "down_count": safe_float(item.get("f105")),
            "lead_stock_name": item.get("f128", ""),
            "lead_stock_code": item.get("f140", ""),
        })
    return result


def fetch_sector_stocks(sector_code: str) -> list[dict]:
    """获取某板块下的成分股列表。

    请求URL: https://push2.eastmoney.com/api/qt/clist/get
    参数:
        fs=b:{sector_code}  (指定板块代码，BK开头)

    返回字段说明:
        - code: 股票代码
        - name: 股票名称
        - price: 最新价
        - pct_chg: 涨跌幅(%)

    Returns:
        list[dict]: 成分股列表
    """
    params = {
        "pn": "1",
        "pz": "500",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": f"b:{sector_code}",
        "fields": "f2,f3,f4,f12,f14",
    }
    data = push2_get("/api/qt/clist/get", params=params)
    if not data:
        return []

    items = data.get("data", {}).get("diff", [])
    result = []
    for item in items:
        result.append({
            "code": item.get("f12", ""),
            "name": item.get("f14", ""),
            "price": safe_float(item.get("f2")),
            "pct_chg": safe_float(item.get("f3")),
        })
    return result
