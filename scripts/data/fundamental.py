"""A股基本面数据层。

数据来源：东方财富公开财务API（datacenter.eastmoney.com / emweb.securities.eastmoney.com）。
全部为公开数据接口，不涉及认证。

覆盖指标：
- 财务摘要：每股收益、净资产收益率(ROE)、毛利率、净利率
- 估值指标：市盈率(PE)、市净率(PB)、市销率(PS)
- 分红数据：股息率
- 成长性指标：营收增长率、净利润增长率
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
    "Referer": "https://emweb.securities.eastmoney.com/",
})

# 估值接口 secid 前缀（push2 stock/get 对三市场均返回 PE/PB/股息率等估值字段）
# - A股: 1.沪 / 0.深（按代码首位动态）
# - 港股: 116.主板 / 115.创业板（主板失败时 fallback）
# - 美股: 105.（NYSE/NASDAQ 统一）
_MARKET_SECID_PREFIX = {
    "A股": None,   # 按代码首位动态判断
    "港股": "116",
    "美股": "105",
}


def _secid_for_valuation(code: str, market: str = "A股") -> str:
    """生成指定市场标的在 push2 stock/get 接口的 secid。"""
    prefix = _MARKET_SECID_PREFIX.get(market)
    if prefix is None:
        return f"1.{code}" if code.startswith("6") else f"0.{code}"
    if market == "港股":
        return f"116.{code.strip().zfill(5)}"
    return f"{prefix}.{code}"


def fetch_financial_summary(code: str) -> dict:
    """获取个股财务摘要。

    来源：东方财富数据中心公开API。

    Returns:
        dict: 含 roe/per_eps/profit_gross/net_profit_rate/debt_ratio 等字段
    """
    result = {
        "code": code,
        "roe": None,               # 净资产收益率(%)
        "per_eps": None,            # 每股收益
        "profit_gross": None,       # 毛利率(%)
        "net_profit_rate": None,    # 净利率(%)
        "debt_ratio": None,         # 资产负债率(%)
        "revenue_growth": None,     # 营收同比(%)
        "net_profit_growth": None,  # 净利润同比(%)
        "operating_cfps": None,     # 每股经营现金流
    }

    try:
        # 获取主要财务指标（按代码前缀区分沪市/深市）
        prefix = "SH" if code.startswith("6") else "SZ"
        url = (
            "https://emweb.securities.eastmoney.com/PC_HSF10/FinanceSummary/FinanceSummary"
            f"?code={prefix}{code}&type=web"
        )
        resp = _session.get(url, timeout=20)
        data = resp.json()

        if data and isinstance(data, list) and len(data) > 0:
            latest = data[0]
            result["roe"] = safe_float(latest.get("ROEJQ", latest.get("ROE", "")))
            result["per_eps"] = safe_float(latest.get("BASICEPS", latest.get("EPS", "")))
            result["profit_gross"] = safe_float(latest.get("XSMLL", ""))
            result["net_profit_rate"] = safe_float(latest.get("JLRTTM", ""))
            result["debt_ratio"] = safe_float(latest.get("ZCFZL", ""))
            result["revenue_growth"] = safe_float(latest.get("YYSZGR", latest.get("TOTALYOYGROW", "")))
            result["net_profit_growth"] = safe_float(latest.get("JLRGR", ""))
    except Exception:
        pass

    return result


def fetch_valuation(code: str, market: str = "A股") -> dict:
    """获取个股估值指标（支持 A股/港股/美股）。

    港股/美股基于 push2 stock/get 接口的估值字段（PE/PB/股息率/总市值），
    与 A股同一字段语义；港股创业板（115）在主板块无数据时自动 fallback。

    Returns:
        dict: 含 pe/pb/ps/dividend_yield/total_mv 等字段
    """
    result = {
        "code": code,
        "pe_ttm": None,        # 市盈率(TTM)
        "pb": None,            # 市净率
        "ps_ttm": None,        # 市销率(TTM)
        "dividend_yield": None, # 股息率(%)
        "total_mv": None,      # 总市值(亿)
    }

    def _try_fetch(secid: str) -> dict:
        # fltt=2 返回格式化小数（未加 fltt 时 PE/PB 为放大100倍整数，已核实）
        data = push2_get("/api/qt/stock/get", params={
            "secid": secid,
            "fltt": "2",
            "fields": "f57,f58,f116,f162,f163,f167,f168,f171",
        })
        return data.get("data", {}) if data else {}

    try:
        data = _try_fetch(_secid_for_valuation(code, market))
        if not data and market == "港股":
            # 港股创业板 fallback
            data = _try_fetch(f"115.{code.strip().zfill(5)}")

        if data:
            # 市盈率(TTM)：港股/美股该字段为0，回退静态市盈率(f163)（三市场口径一致）
            pe_ttm = safe_float(data.get("f162"))
            if not pe_ttm:
                pe_ttm = safe_float(data.get("f163"))
            result["pe_ttm"] = pe_ttm
            result["pb"] = safe_float(data.get("f167"))
            result["ps_ttm"] = safe_float(data.get("f168"))
            # f171 = 股息率(%)（注意：f163 为静态PE，并非股息率，勿混淆）
            result["dividend_yield"] = safe_float(data.get("f171"))
            # f116 = 总市值(元) → 亿元（港股/美股口径一致）
            mv = safe_float(data.get("f116"))
            if mv:
                result["total_mv"] = round(mv / 1e8, 2)
    except Exception:
        pass

    return result


def fetch_fundamental_batch(
    codes: list[str],
    max_workers: int = 10,
) -> dict[str, dict]:
    """批量获取多只股票基本面+估值数据。

    Returns:
        dict[str, dict]: code -> {**financial_summary, **valuation}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}

    def _fetch_one(code: str):
        fin = fetch_financial_summary(code)
        val = fetch_valuation(code)
        merged = {**fin, **val}
        merged["code"] = code
        return code, merged

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, c): c for c in codes}
        for future in as_completed(futures):
            code, data = future.result()
            results[code] = data

    return results
