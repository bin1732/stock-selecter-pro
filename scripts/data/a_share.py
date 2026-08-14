"""A股行情数据获取层。

数据来源：东方财富公开行情API（push2.eastmoney.com / 79.push2his.eastmoney.com）。
所有接口均为公开接口，不涉及认证，合规合法。

API说明：
- 实时行情：push2.eastmoney.com/api/qt/ulist.np?fltt=2&fields=...
- 日K线：79.push2his.eastmoney.com/api/qt/stock/kline/get?...
- 分钟K线：push2his.eastmoney.com/api/qt/stock/trends2/get?...&secid=...
"""

import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from ._http import push2_get, kline_get  # 东财实时/历史接口共享客户端（多节点故障切换）

# 全局requests会话，复用连接
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
})

# 市场代码映射
MARKET_SECID = {"sh": "1", "sz": "0", "bj": "0"}


def _market_code(code: str) -> str:
    """根据股票代码推断交易所前缀。"""
    if code.startswith("6"):
        return "1"
    elif code.startswith("0") or code.startswith("3"):
        return "0"
    elif code.startswith("4") or code.startswith("8"):
        return "0"  # 北交所
    else:
        return "0"


def _secid(code: str, market_code: Optional[str] = None) -> str:
    """构造东方财富 secid 参数，格式如 1.600519 或 0.000001。"""
    m = market_code if market_code else _market_code(code)
    return f"{m}.{code}"


def fetch_all_a_share_codes() -> list[dict]:
    """获取全部A股代码列表。

    Returns:
        list[dict]: 每项含 code(代码), name(名称), market(市场).

    来源：东方财富沪深京A股列表接口。
    """
    all_stocks = []
    # 沪深A股 + 北交所 分页获取
    for fs_code in ["m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23", "m:0+t:81+s:2048"]:
        page = 1
        while True:
            data = push2_get("/api/qt/clist/get", params={
                "pn": page, "pz": 500, "po": "1", "np": "1",
                "fltt": "2", "invt": "2", "fid": "f3",
                "fs": fs_code, "fields": "f12,f14",
            })
            if not data:
                break

            items = data.get("data", {}).get("diff", [])
            if not items:
                break

            for item in items:
                code = item.get("f12", "")
                name = item.get("f14", "")
                if code and name:
                    all_stocks.append({
                        "code": code,
                        "name": name,
                        "market": "sh" if code.startswith("6") else "sz",
                    })

            total = data.get("data", {}).get("total", 0)
            if len(all_stocks) >= total:
                break
            page += 1

    return all_stocks


def fetch_daily_kline(
    code: str,
    days: int = 120,
    market_code: Optional[str] = None,
) -> list[dict]:
    """获取单只股票日K线数据。

    Args:
        code: 股票代码，如 '600519'
        days: 获取天数
        market_code: 市场代码 '1'=沪 '0'=深/北

    Returns:
        list[dict]: K线数据，每项含 date/open/close/high/low/volume/amount/pct_chg/turnover
    """
    secid = _secid(code, market_code)
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
            "open": round(float(parts[1]), 2),
            "close": round(float(parts[2]), 2),
            "high": round(float(parts[3]), 2),
            "low": round(float(parts[4]), 2),
            "volume": int(float(parts[5])),
            "amount": round(float(parts[6]), 2),
            "pct_chg": round(float(parts[8]), 2) if parts[8] != "-" else 0.0,
            "turnover": round(float(parts[10]), 2) if parts[10] != "-" else 0.0,
        })
    return result


def fetch_batch_klines_parallel(
    codes: list[str],
    days: int = 120,
    max_workers: int = 10,
    delay: float = 0.15,
) -> dict[str, list[dict]]:
    """批量并发获取多只股票日K线。

    Args:
        codes: 股票代码列表
        days: 每只获取天数
        max_workers: 并发线程数
        delay: 请求间隔(秒)，控制频率避免被封

    Returns:
        dict[str, list[dict]]: code -> K线列表
    """
    results = {}

    def _fetch_one(code: str):
        nonlocal results
        time.sleep(random.uniform(0, delay))
        try:
            kl = fetch_daily_kline(code, days=days)
            return code, kl
        except Exception:
            return code, []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, c): c for c in codes}
        for future in as_completed(futures):
            code, kl = future.result()
            results[code] = kl

    return results


def fetch_minute_kline(code: str, period: str = "60") -> list[dict]:
    """获取分钟K线（60分钟/30分钟/15分钟/5分钟）。

    Args:
        code: 股票代码
        period: K线周期 '60','30','15','5'

    Returns:
        list[dict]: 分钟K线数据
    """
    secid = _secid(code)
    klt_map = {"60": 60, "30": 30, "15": 15, "5": 5}
    klt = klt_map.get(period, 60)

    data = kline_get("/api/qt/stock/kline/get", params={
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": klt, "fqt": "1", "end": "20500101", "lmt": 200,
    })
    if not data:
        return []

    klines = data.get("data", {}).get("klines", [])
    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 8:
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


def fetch_weekly_kline(code: str, weeks: int = 60) -> list[dict]:
    """获取周K线。"""
    secid = _secid(code)
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


def fetch_monthly_kline(code: str, months: int = 36) -> list[dict]:
    """获取月K线。"""
    secid = _secid(code)
    data = kline_get("/api/qt/stock/kline/get", params={
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "103", "fqt": "1", "end": "20500101", "lmt": months,
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


def get_realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """获取多只股票实时行情（快照）。

    Args:
        codes: 股票代码列表（一次最多约200只）

    Returns:
        dict[str, dict]: code -> {name, price, pct_chg, volume, amount, high, low, open, turnover}
    """
    if not codes:
        return {}

    secids = []
    for c in codes:
        m = _market_code(c)
        secids.append(f"{m}.{c}")

    data = push2_get("/api/qt/ulist.np", params={
        "fltt": "2", "invt": "2",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f12,f14,f15,f16,f17,f18,f20",
        "secids": ",".join(secids),
    })
    if not data:
        return {}

    items = data.get("data", {}).get("diff", [])
    result = {}
    for item in items:
        code = item.get("f12", "")
        if not code:
            continue
        result[code] = {
            "name": item.get("f14", ""),
            "price": item.get("f2", 0),
            "pct_chg": item.get("f3", 0),
            "change": item.get("f4", 0),
            "volume": item.get("f5", 0),
            "amount": item.get("f6", 0),
            "high": item.get("f15", 0),
            "low": item.get("f16", 0),
            "open": item.get("f17", 0),
            "turnover": item.get("f8", 0),
        }
    return result
