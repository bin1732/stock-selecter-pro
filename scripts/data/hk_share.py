"""港股行情数据获取层。

数据来源：东方财富公开行情API（push2.eastmoney.com / push2his.eastmoney.com）。
全部为公开数据接口，不涉及认证，合规合法。

覆盖范围：
- 港股全市场列表（主板 + 创业板）
- 恒生指数/国企指数/科技指数实时行情
- 港股日K线/周K线
- 批量K线获取

API说明：
- 港股列表：push2.eastmoney.com/api/qt/clist/get?fs=m:128+t:3,m:128+t:4
- 港股K线：79.push2his.eastmoney.com/api/qt/stock/kline/get?secid=116.{code}
- secid格式：116.{5位代码} 港股主板，115.{5位代码} 港股创业板

代码标准化规则：
- 港股代码统一补0到5位数字，如 700 -> 00700，1 -> 00001
"""

import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from ._http import push2_get, kline_get, safe_float  # 东财共享客户端（故障切换+数值清洗）

_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
})


def _pad_hk_code(code: str) -> str:
    """港股代码标准化：补0到5位数字。"""
    code = code.strip().zfill(5)
    return code


def fetch_all_hk_codes() -> list[dict]:
    """获取港股全市场股票列表（主板 + 创业板）。

    请求URL: https://push2.eastmoney.com/api/qt/clist/get
    参数:
        fs=m:128+t:3,m:128+t:4  (港股主板 + 创业板)
        fields=f12,f14,f20    (代码/名称/总市值)

    返回字段说明:
        - code: 港股代码（标准化为5位）
        - name: 股票名称
        - total_mv: 总市值（元）

    Returns:
        list[dict]: 港股列表
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
            "fs": "m:128+t:3,m:128+t:4",
            "fields": "f2,f3,f12,f14,f20",
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
                    "code": _pad_hk_code(code),
                    "name": item.get("f14", ""),
                    "price": safe_float(item.get("f2")),
                    "pct_chg": safe_float(item.get("f3")),
                    "total_mv": safe_float(item.get("f20")),
                })

        total = data.get("data", {}).get("total", 0)
        if len(all_stocks) >= total:
            break
        page += 1

    return all_stocks


def fetch_hk_daily_kline(code: str, days: int = 120) -> list[dict]:
    """获取港股日K线数据。

    请求URL: https://79.push2his.eastmoney.com/api/qt/stock/kline/get
    参数:
        secid=116.{5位代码}  (港股主板)
        klt=101              (日线)
        fqt=1                (前复权)

    返回字段说明:
        - date: 日期
        - open/close/high/low: 开收盘高低
        - volume: 成交量
        - amount: 成交额
        - pct_chg: 涨跌幅(%)

    Returns:
        list[dict]: 日K线数据
    """
    padded = _pad_hk_code(code)
    secid = f"116.{padded}"
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
        # 尝试创业板 secid
        data = kline_get("/api/qt/stock/kline/get", params={
            "secid": f"115.{padded}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101", "fqt": "1", "end": "20500101", "lmt": days,
        })
        if not data:
            return []
        klines = data.get("data", {}).get("klines", [])

    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        result.append({
            "date": parts[0],
            "open": round(float(parts[1]), 2),
            "close": round(float(parts[2]), 2),
            "high": round(float(parts[3]), 2),
            "low": round(float(parts[4]), 2),
            "volume": int(float(parts[5])),
            "amount": round(float(parts[6]), 2),
            "pct_chg": round(float(parts[8]), 2) if parts[8] != "-" else 0.0,
        })
    return result


def fetch_hk_weekly_kline(code: str, weeks: int = 60) -> list[dict]:
    """获取港股周K线数据。

    请求URL: https://79.push2his.eastmoney.com/api/qt/stock/kline/get
    参数:
        klt=102 (周线)

    Returns:
        list[dict]: 周K线数据
    """
    padded = _pad_hk_code(code)
    secid = f"116.{padded}"
    data = kline_get("/api/qt/stock/kline/get", params={
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "102", "fqt": "1", "end": "20500101", "lmt": weeks,
    })
    if not data:
        return []

    klines = data.get("data", {}).get("klines", [])
    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        result.append({
            "date": parts[0],
            "open": round(float(parts[1]), 2),
            "close": round(float(parts[2]), 2),
            "high": round(float(parts[3]), 2),
            "low": round(float(parts[4]), 2),
            "volume": int(float(parts[5])),
            "amount": round(float(parts[6]), 2),
        })
    return result


def fetch_hk_batch_klines(
    codes: list[str],
    days: int = 120,
    max_workers: int = 10,
    delay: float = 0.15,
) -> dict[str, list[dict]]:
    """批量并发获取多只港股日K线。

    Args:
        codes: 港股代码列表
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
            kl = fetch_hk_daily_kline(code, days=days)
            return code, kl
        except Exception:
            return code, []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, c): c for c in codes}
        for future in as_completed(futures):
            code, kl = future.result()
            results[code] = kl

    return results
