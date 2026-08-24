"""A股行情数据获取层。

数据来源：东方财富公开行情API（push2.eastmoney.com / 79.push2his.eastmoney.com）。
所有接口均为公开接口，不涉及认证，合规合法。

API说明：
- 列表（候选池）：push2.eastmoney.com/api/qt/clist/get（总市值降序，含行业字段 f100）
- 日K线：79.push2his.eastmoney.com/api/qt/stock/kline/get?...&klt=101
- 周K线：79.push2his.eastmoney.com/api/qt/stock/kline/get?...&klt=102
"""

import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from ._http import push2_get, kline_get, safe_float  # 东财实时/历史接口共享客户端（多节点故障切换）


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


def fetch_top_a_share_codes(cap: int = 1000) -> list[dict]:
    """按总市值降序获取A股候选池（过滤 ST/退市/新股后取前 cap 只）。

    与港股/美股列表口径一致：fid=f20（总市值）降序分页取前N近似，
    替代此前 fid=f3（当日涨跌幅）排序取前N造成的候选池偏倚——
    原实现候选池只覆盖当日涨幅最大的股票，会系统性漏掉回调/横盘等
    大量符合技术形态的标的，导致筛选结果失真。

    Returns:
        list[dict]: [{code, name, market, industry}, ...]（market 为 sh/sz/bj 标签；
            industry 为东方财富行业名称，部分标的可能为空）
    """
    stocks = []
    page = 1
    # 市值降序 + ST/退市/新股过滤损耗：多拉 30% 余量后截断
    target = int(cap * 1.3) + 50
    while len(stocks) < target and page <= 8:
        data = push2_get("/api/qt/clist/get", params={
            "pn": page, "pz": 500, "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f20",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            # f12/f14 代码名称；f20 总市值；f100 行业；
            # f9 PE(动)/f23 PB/f133 股息率(%)：估值字段（clist 与 push2 stock/get
            # 数值一致；f133 三市场真实可用，替代不可靠的 push2 f171，见 fundamental.py）
            "fields": "f12,f14,f20,f100,f9,f23,f133",
        })
        if not data:
            break
        payload = data.get("data", {}) or {}
        items = payload.get("diff", []) or []
        if not items:
            break
        total = payload.get("total") or 0
        for item in items:
            code = item.get("f12", "")
            name = item.get("f14", "")
            if not code or not name:
                continue
            # ST / 退市 / 新股（N/C 仅当名称以该字母开头时视为新股，避免误杀）
            if "ST" in name or "退" in name or name.startswith(("N", "C")):
                continue
            if code.startswith("6"):
                market_tag = "sh"
            elif code.startswith(("4", "8")):
                market_tag = "bj"
            else:
                market_tag = "sz"
            stocks.append({
                "code": code,
                "name": name,
                "market": market_tag,
                "industry": item.get("f100", "") or "",
                "total_mv": safe_float(item.get("f20")),  # 总市值(元)，与港股/美股列表口径一致
                # 估值字段（clist 批量真实返回，替代逐只 push2 请求，口径与 fundamental.fetch_valuation 一致）
                "pe": safe_float(item.get("f9")),
                "pb": safe_float(item.get("f23")),
                "dividend_yield": safe_float(item.get("f133")),
            })
        # 分页终止：按接口返回的 total 判断，累计已拉满 total 才停（0 条页兜底）。
        # 延迟节点下 clist 每页可能仅返回 100 条，若按页大小判末页会把候选池
        # 提前截断为市值 top 100，漏掉其余约 90% 标的。
        if total and len(stocks) >= total:
            break
        page += 1
    return stocks[:cap]


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
            "open": round(safe_float(parts[1]), 2),
            "close": round(safe_float(parts[2]), 2),
            "high": round(safe_float(parts[3]), 2),
            "low": round(safe_float(parts[4]), 2),
            "volume": int(safe_float(parts[5])),
            "amount": round(safe_float(parts[6]), 2),
            "pct_chg": safe_float(parts[8]),
            "turnover": safe_float(parts[10]),
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
            "open": round(safe_float(parts[1]), 2),
            "close": round(safe_float(parts[2]), 2),
            "high": round(safe_float(parts[3]), 2),
            "low": round(safe_float(parts[4]), 2),
            "volume": int(safe_float(parts[5])),
            "amount": round(safe_float(parts[6]), 2),
        })
    return result
