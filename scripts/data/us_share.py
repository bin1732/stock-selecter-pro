"""美股行情数据获取层。

数据来源：东方财富公开行情API（push2.eastmoney.com / push2his.eastmoney.com）。
全部为公开数据接口，不涉及认证，合规合法。

覆盖范围：
- 美股全市场列表（NYSE + NASDAQ + AMEX）
- 道琼斯/纳斯达克/标普500指数实时行情
- 美股日K线
- 批量K线获取

API说明：
- 美股列表：push2.eastmoney.com/api/qt/clist/get?fs=m:105+t:3,m:105+t:4,m:105+t:5
- 美股K线：79.push2his.eastmoney.com/api/qt/stock/kline/get?secid=105.{code}
- secid格式：105.{字母代码} 美股统一前缀

代码标准化规则：
- 美股代码保持原样（字母代码），东方财富直接使用（如 AAPL、TSLA）
- 部分含点的代码（如 BRK.A）需先尝试，失败返回空列表
"""

import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from ._http import push2_get, kline_get, safe_float  # 东财共享客户端（故障切换+数值清洗）


def fetch_all_us_codes() -> list[dict]:
    """获取美股全市场股票列表（NYSE + NASDAQ + AMEX）。

    请求URL: https://push2.eastmoney.com/api/qt/clist/get
    参数:
        fs=m:105+t:3,m:105+t:4,m:105+t:5  (纽交所 + 纳斯达克 + 美国证券交易所)
        fields=f12,f14,f20    (代码/名称/总市值)

    返回字段说明:
        - code: 美股代码（字母标识）
        - name: 股票名称
        - price: 最新价
        - pct_chg: 涨跌幅(%)
        - total_mv: 总市值（美元）

    Returns:
        list[dict]: 美股列表
    """
    all_stocks = []
    page = 1
    while True:
        params = {
            "pn": str(page),
            "pz": "500",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f20",
            "fs": "m:105+t:3,m:105+t:4,m:105+t:5",
            # f9 PE(动)/f23 PB/f133 股息率(%)：估值字段（美股 clist 真实返回；
            # push2 stock/get 对美股返回空、f171 不可靠，统一走列表字段）
            "fields": "f2,f3,f12,f14,f20,f9,f23,f133",
        }
        data = push2_get("/api/qt/clist/get", params=params)
        if not data:
            break

        items = data.get("data", {}).get("diff", [])
        if not items:
            break

        for item in items:
            code = item.get("f12", "")
            if code:
                all_stocks.append({
                    "code": code,
                    "name": item.get("f14", ""),
                    "price": safe_float(item.get("f2")),
                    "pct_chg": safe_float(item.get("f3")),
                    "total_mv": safe_float(item.get("f20")),
                    "pe": safe_float(item.get("f9")),
                    "pb": safe_float(item.get("f23")),
                    "dividend_yield": safe_float(item.get("f133")),
                })

        # 分页终止：以当页返回条数判断（不足一页即最后一页），
        # 避免用累计数与 total 比较导致提前终止
        if len(items) < 500:
            break
        page += 1

    return all_stocks


def fetch_us_daily_kline(code: str, days: int = 120) -> list[dict]:
    """获取美股日K线数据。

    请求URL: https://79.push2his.eastmoney.com/api/qt/stock/kline/get
    参数:
        secid=105.{代码}  (美股统一前缀)
        klt=101           (日线)
        fqt=1             (前复权)

    返回字段说明:
        - date: 日期
        - open/close/high/low: 开收盘高低（美元）
        - volume: 成交量
        - amount: 成交额
        - pct_chg: 涨跌幅(%)

    Returns:
        list[dict]: 日K线数据
    """
    secid = f"105.{code}"
    data = kline_get("/api/qt/stock/kline/get", params={
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1", "end": "20500101", "lmt": days,
    })
    if not data:
        return []

    klines = data.get("data", {}).get("klines", [])
    if not klines:
        return []

    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        result.append({
            "date": parts[0],
            "open": round(safe_float(parts[1]), 2),
            "close": round(safe_float(parts[2]), 2),
            "high": round(safe_float(parts[3]), 2),
            "low": round(safe_float(parts[4]), 2),
            "volume": int(safe_float(parts[5])),
            "amount": round(safe_float(parts[6]), 2),
            "pct_chg": safe_float(parts[8]),
        })
    return result


def fetch_us_batch_klines(
    codes: list[str],
    days: int = 120,
    max_workers: int = 10,
    delay: float = 0.15,
) -> dict[str, list[dict]]:
    """批量并发获取多只美股日K线。

    Args:
        codes: 美股代码列表（如 ['AAPL', 'TSLA', 'MSFT']）
        days: 获取天数
        max_workers: 并发线程数
        delay: 请求间隔(秒)

    Returns:
        dict[str, list[dict]]: code -> K线列表
    """
    results = {}

    def _fetch_one(code: str):
        time.sleep(random.uniform(0, delay))
        try:
            kl = fetch_us_daily_kline(code, days=days)
            return code, kl
        except Exception:
            return code, []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, c): c for c in codes}
        for future in as_completed(futures):
            code, kl = future.result()
            results[code] = kl

    return results
