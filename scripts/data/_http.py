"""东财公开API 共享 HTTP 客户端（域名级故障切换 + 备选数据通道）。

- 部分网络环境下 push2.eastmoney.com（实时快照主节点）连接不可达，
  但东财官方备用延迟节点 push2delay.eastmoney.com 可达（约3分钟延迟）。
- 两节点返回同一套公开字段（列表/行情/估值/资金流），语义一致，
  备用节点仅数据延迟更高，不改变数据真实性。
- 历史K线接口（push2his 多编号节点）在部分网络环境整体不可达时，
  自动切换到腾讯公开K线通道（web.ifzq.gtimg.cn，A股/港股/美股均支持），
  输出与东财同构的K线字段，确保回测与技术面策略真实可用。

为确保工具在用户网络环境中真实可用，所有 push2 实时请求
在主节点失败时自动切换到备用节点重试；K线请求在 push2his
全部节点失败时自动切换到腾讯公开通道。
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

# TLS 证书健壮性：若系统环境变量 SSL_CERT_FILE / REQUESTS_CA_BUNDLE 指向不存在的路径
# （如已卸载软件的残留配置），从环境中清除，避免标准库 SSL 上下文加载失败。
for _env_key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
    _p = os.environ.get(_env_key, "")
    if _p and not os.path.exists(_p):
        os.environ.pop(_env_key, None)


class _HttpResponse:
    """极简响应对象：兼容调用点使用的 status_code / text / json() / raise_for_status()。"""

    __slots__ = ("status_code", "text", "_data")

    def __init__(self, status_code: int, data: bytes):
        self.status_code = status_code
        self.text = data.decode("utf-8", errors="replace")
        self._data = data

    def json(self):
        return json.loads(self._data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise urllib.error.HTTPError(
                None, self.status_code, f"HTTP {self.status_code}", None, None
            )


class _HttpClient:
    """基于 Python 标准库 urllib 的轻量 HTTP GET 客户端（全项目唯一共享客户端）。

    仅提供 get()，返回 _HttpResponse；自动处理查询串编码与重定向，
    读取系统代理环境变量，SSL 使用系统证书库。零第三方依赖、无需任何 API Key。
    """

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/",
        }
        self._opener = urllib.request.build_opener()

    def get(self, url: str, params: dict = None, timeout: int = 8) -> _HttpResponse:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=self.headers)
        with self._opener.open(req, timeout=timeout) as resp:
            return _HttpResponse(resp.status, resp.read())


# 全局共享客户端（全项目唯一 HTTP 客户端，fundamental/guide 复用，避免重复实现）
http_get = _HttpClient().get

# 主节点 + 备用延迟节点（东财官方，延迟约3分钟，字段一致）
PUSH2_HOSTS = ("push2.eastmoney.com", "push2delay.eastmoney.com")

# 历史K线节点（push2his）：东财按线路部署多个编号节点，不同网络环境可达性不同，
# 按序尝试，首个返回有效 data 的节点即用（单一节点可能被限流/断开）
PUSH2HIS_HOSTS = (
    "https://79.push2his.eastmoney.com",
    "https://92.push2his.eastmoney.com",
    "https://91.push2his.eastmoney.com",
    "https://push2his.eastmoney.com",
)

# 腾讯公开K线通道：push2his 全部节点不可达时的备选（A股/港股三市场真实可用）。
# 多入口轮询：proxy.finance.qq.com 为独立入口（对高频请求更稳健），
# web.ifzq.gtimg.cn 高频请求会触发 501 风控，作为轮询后备。
TENCENT_KLINE_HOSTS = (
    "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get",
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
    "https://ifzq.gtimg.cn/appstock/app/fqkline/get",
)
TENCENT_HOST_LABEL = "腾讯公开K线通道"

# 美股K线备选：腾讯接口对美股仅返回首末两条，历史不可用；
# 新浪美股公开接口返回全历史日K（1984 年至今），作为美股专用备选。
SINA_US_KLINE_URL = "https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20_=/US_MinKService.getDailyK"
SINA_US_HOST_LABEL = "新浪美股K线通道"

# 最近一次成功请求实际使用的节点（供报告如实展示当前数据通道）
LAST_HOST = [None]
LAST_HIS_HOST = [None]


def push2_get(path: str, params: dict = None, timeout: int = 8) -> dict:
    """请求 push2 实时接口，主节点失败自动切换备用节点。

    Args:
        path: API 路径，如 /api/qt/clist/get
        params: 查询参数
        timeout: 单次请求超时（秒）
            （正常请求 0.5s 内返回，8s 仅约束挂死节点，避免慢网络下双节点超时链拖慢整批）

    Returns:
        dict: 接口 JSON 字典；全部节点失败返回 {}（调用方自行判空降级）
    """
    for host in PUSH2_HOSTS:
        try:
            resp = http_get(f"https://{host}{path}", params=params, timeout=timeout)
            data = resp.json()
            # 强校验：JSON 解析成功且 rc==0 且 data 非空。
            # 东财错误包形态为 {"rc": 非0, "data": null}，若仅判 data 为真会被放行，
            # 导致下游 AttributeError；此处统一拦截。
            if data and data.get("rc", 0) == 0 and data.get("data") is not None:
                LAST_HOST[0] = host
                return data
        except Exception:  # 网络异常/解析失败 → 切换下一节点
            continue
    return {}


def kline_get(path: str, params: dict = None, timeout: int = 5) -> dict:
    """请求历史K线接口：优先 push2his 多编号节点，全部失败时切换腾讯公开K线通道。

    push2his 节点返回空 data 时继续尝试下一节点（避免选中了不支持该标的的线路）；
    全部节点失败后调用腾讯公开通道（web.ifzq.gtimg.cn），并如实记录实际通道供报告展示。
    超时策略：
    - 首个节点 5s 超时（正常请求 0.5s 内返回；5s 约束挂死节点）
    - 后续节点 3s 超时：慢网络下避免 4 节点 × 8s = 32s 的串行超时链拖慢整批

    Returns:
        dict: 与东财同构的 {"data": {"klines": [csv行, ...]}}；双通道均失败返回 {}
    """
    secid = (params or {}).get("secid", "")
    lmt = int((params or {}).get("lmt", 120))
    klt = str((params or {}).get("klt", "101"))

    for idx, host in enumerate(PUSH2HIS_HOSTS):
        try:
            # 首节点用完整超时；后续节点 3s 快速超时（慢网络下避免串行超时链过长）
            node_timeout = timeout if idx == 0 else max(3, timeout // 2)
            resp = http_get(f"{host}{path}", params=params, timeout=node_timeout)
            data = resp.json()
            if data and data.get("data"):
                LAST_HIS_HOST[0] = host
                return data
        except Exception:  # 网络异常/解析失败 → 切换下一节点
            continue

    # push2his 全部节点失败 → 按市场切换备选公开通道（三市场真实可用）
    if str(secid).startswith("105."):
        # 美股：腾讯接口仅返回首末两条，走新浪美股全历史日K
        lines = _sina_us_kline_fallback(secid, lmt)
    else:
        # A股/港股：腾讯公开K线通道（多入口轮询）
        lines = _tencent_kline_fallback(secid, lmt, klt)
    if lines:
        LAST_HIS_HOST[0] = (
            SINA_US_HOST_LABEL if str(secid).startswith("105.") else TENCENT_HOST_LABEL
        )
        return {"data": {"klines": lines}}
    return {}


def _tencent_symbol(secid: str) -> str:
    """东财 secid → 腾讯行情代码。

    东财 secid 前缀映射：
    - 1.   → A股沪市 → sh
    - 0.   → A股深市/北交所 → sz
    - 116./115. → 港股主板/创业板 → hk
    - 105. → 美股 → us
    """
    if "." not in secid:
        return ""
    prefix, code = secid.split(".", 1)
    if prefix == "1":
        return f"sh{code}"
    if prefix == "0":
        return f"sz{code}"
    if prefix in ("116", "115"):
        return f"hk{code}"
    if prefix == "105":
        return f"us{code}"
    if prefix == "100":
        # 指数：东财 100.HSI/100.HSCEI/100.DJI/100.IXIC → 腾讯公开指数代码
        idx_map = {
            "HSI": "hkHSI",
            "HSCEI": "hkHSCEI",
            "DJI": "usDJI",
            "IXIC": "usIXIC",
        }
        return idx_map.get(code, "")
    return ""


def _tencent_kline_fallback(secid: str, lmt: int, klt: str = "101") -> list[str]:
    """腾讯公开K线通道（A股/港股）：多入口轮询，返回与东财 fields2=f51..f61 同构的 CSV 行。

    腾讯 fqkline 每行返回 [date, open, close, high, low, volume]；
    东财同构行缺省字段（成交额/振幅/换手率）如实置 0，
    涨跌幅/涨跌额由收盘价序列真实计算（无该字段的通道不伪造）。

    proxy.finance.qq.com 为独立入口（对高频请求更稳健），
    web.ifzq.gtimg.cn 高频触发 501 风控，作为轮询后备。

    Args:
        secid: 东财 secid（如 "1.600519" / "116.00700"）
        lmt: 获取K线条数
        klt: 周期，101=日线 102=周线

    Returns:
        list[str]: 东财同构 CSV 行；全部入口失败或数据为空返回 []
    """
    sym = _tencent_symbol(secid)
    if not sym:
        return []
    freq = "week" if klt == "102" else "day"
    for url in TENCENT_KLINE_HOSTS:
        try:
            resp = http_get(url, params={
                "param": f"{sym},{freq},,,{lmt},qfq",
            }, timeout=5)
            if resp.status_code != 200:
                continue
            data = resp.json().get("data", {}).get(sym, {})
            rows = data.get("qfqday") or data.get("qfqweek") or data.get(freq) or []
            if not rows:
                continue
            lines = []
            prev_close = None
            for row in rows:
                if len(row) < 6:
                    continue
                date, o, c, h, l, v = row[0], row[1], row[2], row[3], row[4], row[5]
                pct, chg = "-", "-"
                try:
                    if prev_close is not None:
                        prev_f = float(prev_close)
                        if prev_f:
                            c_f = float(c)
                            pct = round((c_f / prev_f - 1) * 100, 4)
                            chg = round(c_f - prev_f, 4)
                except (ValueError, TypeError):
                    pass
                lines.append(f"{date},{o},{c},{h},{l},{v},0,0,{pct},{chg},0")
                prev_close = c
            if lines:
                return lines
        except Exception:
            continue
    return []


def _sina_us_kline_fallback(secid: str, lmt: int) -> list[str]:
    """新浪美股K线通道：返回与东财 fields2=f51..f61 同构的 CSV 行。

    新浪 US_MinKService.getDailyK 返回全历史日K（1984 年至今），
    JSONP 包裹（var _=([...]);），每行 {d,o,h,l,c,v}；
    取最近 lmt 条，缺省字段（成交额/振幅/换手率）如实置 0，
    涨跌幅/涨跌额由收盘价序列真实计算。

    Args:
        secid: 东财美股 secid（如 "105.AAPL"）
        lmt: 获取K线条数

    Returns:
        list[str]: 东财同构 CSV 行；失败或数据为空返回 []
    """
    code = str(secid).split(".", 1)[-1].lower()
    try:
        resp = http_get(SINA_US_KLINE_URL, params={"symbol": code}, timeout=6)
        if resp.status_code != 200:
            return []
        text = resp.text
        start = text.find("[")
        end = text.rfind("])")
        if start == -1 or end == -1:
            return []
        import json
        arr = json.loads(text[start:end + 1])
        if not arr:
            return []
        lines = []
        prev_close = None
        for row in arr[-lmt:]:
            date = row.get("d", "")
            o = row.get("o", "")
            c = row.get("c", "")
            h = row.get("h", "")
            l = row.get("l", "")
            v = row.get("v", "")
            if not date:
                continue
            pct, chg = "-", "-"
            try:
                if prev_close is not None:
                    prev_f = float(prev_close)
                    if prev_f:
                        c_f = float(c)
                        pct = round((c_f / prev_f - 1) * 100, 4)
                        chg = round(c_f - prev_f, 4)
            except (ValueError, TypeError):
                pass
            lines.append(f"{date},{o},{c},{h},{l},{v},0,0,{pct},{chg},0")
            prev_close = c
        return lines
    except Exception:
        return []


def current_host_label() -> str:
    """返回当前实际数据通道的说明文字（供报告展示，如实声明）。

    - push2.eastmoney.com       → 实时主节点
    - push2delay.eastmoney.com  → 官方延迟节点（约3分钟延迟）
    - None                      → 最近请求全部失败
    """
    host = LAST_HOST[0]
    if not host:
        return "数据通道异常（最近请求全部失败）"
    if "delay" in host:
        return f"官方延迟节点（{host}，行情延迟约3分钟）"
    return f"实时主节点（{host}）"


def current_kline_host_label() -> str:
    """返回最近一次K线请求实际使用的数据通道（供报告如实展示）。

    - push2his.*.eastmoney.com → 东财历史K线节点
    - 腾讯公开K线通道（web.ifzq.gtimg.cn）→ push2his 不可达时自动切换
    - None → 最近K线请求全部失败
    """
    host = LAST_HIS_HOST[0]
    if not host:
        return "K线通道异常（最近请求全部失败）"
    return f"{host}"


def safe_float(val, default: float = 0.0) -> float:
    """安全转换为 float。

    东财公开接口的空值形态多样（"-"、""、None、含千分位逗号、百分号），
    统一清洗后转换；无效值返回 default，避免下游排序/运算抛错。
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace("%", "").replace(",", "").strip()
        if s == "-" or s == "":
            return default
        return float(s)
    except (ValueError, TypeError):
        return default


def parse_kline_csv(klines, include_turnover: bool = False) -> list[dict]:
    """解析东财 K线 CSV 行（date/open/close/high/low/volume/amount/pct_chg[+turnover]）。

    三市场（A股/港股/美股）K线接口返回同构 CSV 行（逗号分隔，至少 11 列，
    列位：0日期/1开/2收/3高/4低/5量/6额/7振幅/8涨跌幅/9涨跌额/10换手率），
    统一在此解析，避免三市场各自实现重复逻辑。
    """
    result = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        row = {
            "date": parts[0],
            "open": round(safe_float(parts[1]), 2),
            "close": round(safe_float(parts[2]), 2),
            "high": round(safe_float(parts[3]), 2),
            "low": round(safe_float(parts[4]), 2),
            "volume": int(safe_float(parts[5])),
            "amount": round(safe_float(parts[6]), 2),
            "pct_chg": safe_float(parts[8]),
        }
        if include_turnover:
            row["turnover"] = safe_float(parts[10])
        result.append(row)
    return result
