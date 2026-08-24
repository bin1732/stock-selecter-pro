"""板块数据获取层：行业板块 + 概念板块排行。

数据来源：东方财富公开板块行情API（push2.eastmoney.com）。
全部为公开数据接口，不涉及认证，合规合法。

覆盖范围：
- 行业板块（东方财富板块分类，BK代码）
- 概念板块

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
"""

from ._http import push2_get, safe_float  # 东财共享客户端（主/备节点故障切换+数值清洗）


def _fetch_board_ranking(fs: str, pz: int, sort_by: str = "f3") -> list[dict]:
    """公共板块排行实现（行业/概念板块共用）。

    Args:
        fs: 东财板块过滤条件（m:90+t:2 行业 / m:90+t:3 概念）
        pz: 单页条数
        sort_by: 排序字段，默认 f3 涨跌幅

    Returns:
        list[dict]: 板块排行列表
    """
    params = {
        "pn": "1",
        "pz": str(pz),
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": sort_by,
        "fs": fs,
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


def fetch_industry_ranking(sort_by: str = "f3") -> list[dict]:
    """获取东方财富行业板块实时涨跌幅排行。

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
    return _fetch_board_ranking("m:90+t:2", 100, sort_by)


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
    return _fetch_board_ranking("m:90+t:3", 200, sort_by)
