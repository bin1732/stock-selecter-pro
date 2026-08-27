"""港股行情数据获取层。

数据来源：东方财富公开行情API（push2.eastmoney.com / push2his.eastmoney.com）。
全部为公开数据接口，不涉及认证，合规合法。

覆盖范围：
- 港股全市场列表（主板 + 创业板）
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
from concurrent.futures import ThreadPoolExecutor, as_completed

from ._http import push2_get, kline_get, safe_float, parse_kline_csv  # 东财共享客户端（故障切换+数值清洗）


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
    max_pages = 10  # 页数上限保护（防接口异常导致无限翻页）
    empty_retries = 3  # 列表接口瞬时限流时整列表重试（连续空返回达到阈值才放弃）
    while page <= max_pages:
        params = {
            "pn": str(page),
            "pz": "500",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f20",
            "fs": "m:128+t:3,m:128+t:4",
            # f9 PE(动)/f23 PB/f133 股息率(%)：估值字段（港股 clist 真实返回，
            # 替代逐只 push2 请求；push2 f171 对港股不可靠，股息率失真）
            "fields": "f2,f3,f12,f14,f20,f9,f23,f133",
        }
        data = push2_get("/api/qt/clist/get", params=params)
        if not data:
            break

        payload = data.get("data") or {}
        items = payload.get("diff") or []
        if not items:
            # 接口偶发限流（延迟节点对高频请求返回空）：等待后重试本页
            # （clist 接口偶发数量波动，需重试兜底）
            if page == 1:
                for attempt in range(empty_retries):
                    time.sleep(0.8 * (attempt + 1))
                    data = push2_get("/api/qt/clist/get", params=params)
                    if not data:
                        continue
                    payload = data.get("data") or {}
                    items = payload.get("diff") or []
                    if items:
                        break
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
                    "pe": safe_float(item.get("f9")),
                    "pb": safe_float(item.get("f23")),
                    "dividend_yield": safe_float(item.get("f133")),
                })

        # 分页终止：优先按接口返回的 total 判断（延迟节点每页可能仅返回 100 条，
        # 若按"当页不足整页"判断会提前截断候选池，漏掉市值靠后的标的）；
        # 接口未返回 total 时才按"当页不足整页"兜底判末页
        total = payload.get("total") or 0
        if total and len(all_stocks) >= total:
            break
        if not total and len(items) < 500:
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
    return parse_kline_csv(klines)


def fetch_hk_weekly_kline(code: str, weeks: int = 60) -> list[dict]:
    """获取港股周K线数据。

    请求URL: https://79.push2his.eastmoney.com/api/qt/stock/kline/get
    参数:
        klt=102 (周线)

    Returns:
        list[dict]: 周K线数据
    """
    padded = _pad_hk_code(code)
    data = kline_get("/api/qt/stock/kline/get", params={
        "secid": f"116.{padded}",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "102", "fqt": "1", "end": "20500101", "lmt": weeks,
    })
    klines = data.get("data", {}).get("klines", []) if data else []
    if not klines:
        # 主板无数据时尝试创业板 secid（与日线同策略）
        data = kline_get("/api/qt/stock/kline/get", params={
            "secid": f"115.{padded}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "102", "fqt": "1", "end": "20500101", "lmt": weeks,
        })
        klines = data.get("data", {}).get("klines", []) if data else []

    return parse_kline_csv(klines)


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
