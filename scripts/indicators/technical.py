"""技术指标计算模块。

全部基于公开日K线数据，纯数学运算，不依赖外部库。
所有计算均可审计复现，无随机性或猜测。

指标清单：
- MA: 简单移动平均线
- EMA: 指数移动平均线
- MACD: 异同移动平均线 (DIF/DEA/MACD柱)
- KDJ: 随机指标 (K/D/J值)
- RSI: 相对强弱指标
- BOLL: 布林带 (上轨/中轨/下轨)
- ADX: 平均趋向指数
- ATR: 平均真实波幅
- OBV: 能量潮
"""


# ============================================================
# 基础工具函数
# ============================================================

def _get_closes(klines: list[dict], period: int = -1) -> list[float]:
    """提取收盘价序列。period<=0时取全部，否则取最近period条。"""
    if period > 0:
        subset = klines[-period:]
    else:
        subset = klines
    return [k["close"] for k in subset]


def _get_highs(klines: list[dict]) -> list[float]:
    return [k["high"] for k in klines]


def _get_lows(klines: list[dict]) -> list[float]:
    return [k["low"] for k in klines]


def _get_volumes(klines: list[dict]) -> list[float]:
    return [k["volume"] for k in klines]


# ============================================================
# 移动平均线
# ============================================================

def calc_ma(klines: list[dict], period: int) -> list[float]:
    """计算简单移动平均线 (SMA/MA)。

    Args:
        klines: K线数据列表
        period: 周期，如5/10/20/60

    Returns:
        list[float]: 与输入等长的MA序列，前period-1个为0

    公式: MA = SUM(close, period) / period
    """
    closes = _get_closes(klines)
    ma = [0.0] * len(closes)
    if len(closes) < period:
        return ma
    for i in range(period - 1, len(closes)):
        ma[i] = round(sum(closes[i - period + 1:i + 1]) / period, 2)
    return ma


def calc_ema(klines: list[dict], period: int) -> list[float]:
    """计算指数移动平均线 (EMA)。

    Args:
        klines: K线数据列表
        period: 周期

    Returns:
        list[float]: 与输入等长的EMA序列

    公式: EMA_t = α * close_t + (1-α) * EMA_{t-1}, α = 2/(period+1)
    """
    closes = _get_closes(klines)
    ema = [0.0] * len(closes)
    if len(closes) < period:
        return ema
    alpha = 2.0 / (period + 1)
    # 初始EMA用SMA近似
    ema[period - 1] = sum(closes[:period]) / period
    for i in range(period, len(closes)):
        ema[i] = round(alpha * closes[i] + (1 - alpha) * ema[i - 1], 2)
    return ema


# ============================================================
# MACD
# ============================================================

def calc_macd(
    klines: list[dict],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """计算 MACD 指标。

    Args:
        klines: K线数据列表
        fast: 快线EMA周期，默认12
        slow: 慢线EMA周期，默认26
        signal: 信号线EMA周期，默认9

    Returns:
        dict: {
            dif: list[float],    # DIF快线 (EMA12 - EMA26)
            dea: list[float],    # DEA信号线 (DIF的EMA9)
            macd: list[float],   # MACD柱 (2 * (DIF - DEA))
        }

    算法：MACD = 2 * (DIF - DEA)，其中 DIF = EMA12 - EMA26, DEA = EMA(DIF, 9)
    """
    closes = _get_closes(klines)
    n = len(closes)

    # 计算EMA12和EMA26
    ema12 = calc_ema(klines, fast)
    ema26 = calc_ema(klines, slow)

    # DIF = EMA12 - EMA26
    dif = [0.0] * n
    for i in range(n):
        if ema12[i] and ema26[i]:
            dif[i] = round(ema12[i] - ema26[i], 2)

    # DEA = EMA(DIF, signal)
    dea = [0.0] * n
    if n >= slow + signal - 1:
        alpha = 2.0 / (signal + 1)
        start_idx = slow - 1
        dea[start_idx] = sum(dif[start_idx:start_idx + signal]) / signal
        for i in range(start_idx + signal, n):
            dea[i] = round(alpha * dif[i] + (1 - alpha) * dea[i - 1], 2)

    # MACD柱 = 2 * (DIF - DEA)，保留正负方向：正为红柱，负为绿柱
    macd_bar = [0.0] * n
    for i in range(n):
        if dea[i] != 0 or i >= slow:
            macd_bar[i] = round(2 * (dif[i] - dea[i]), 2)

    return {"dif": dif, "dea": dea, "macd": macd_bar}


def check_macd_golden_cross(klines: list[dict], recent: int = 5) -> dict:
    """检测 MACD 金叉（DIF上穿DEA）。

    Returns:
        dict: {
            has_cross: bool,
            cross_index: int (最近一次金叉位置，-1表示无),
            strength: str ('weak'/'normal'/'strong'),
        }
    """
    macd_data = calc_macd(klines)
    dif = macd_data["dif"]
    dea = macd_data["dea"]
    n = len(dif)

    # 从后往前找最近金叉
    for i in range(n - 2, max(n - recent - 1, 0), -1):
        if dif[i] <= dea[i] and dif[i + 1] > dea[i + 1]:
            # 判断强度
            diff = abs(dif[i + 1] - dea[i + 1])
            if diff > 0.3:
                strength = "strong"
            elif diff > 0.1:
                strength = "normal"
            else:
                strength = "weak"
            return {"has_cross": True, "cross_index": i + 1, "strength": strength}

    return {"has_cross": False, "cross_index": -1, "strength": "none"}


def check_macd_divergence(klines: list[dict]) -> dict:
    """检测 MACD 底背离（股价新低但DIF未新低）。

    底背离定义：股价创近20日新低，但DIF的低点高于前一个低点。

    Returns:
        dict: {
            has_divergence: bool,
            signal_strength: str ('weak'/'medium'/'strong'),
            detail: str,
        }
    """
    if len(klines) < 40:
        return {"has_divergence": False, "signal_strength": "none",
                "detail": "K线数据不足（需≥40条）"}

    macd_data = calc_macd(klines)
    dif = macd_data["dif"]
    closes = _get_closes(klines)

    # 扫描最近40日，找两段低点
    window = min(40, len(closes))
    start = len(closes) - window

    # 找最近20日内的最低收盘价位置
    recent_start = max(start, len(closes) - 20)
    price_low_2 = closes[recent_start]
    price_low_2_idx = recent_start
    for i in range(recent_start, len(closes)):
        if closes[i] < price_low_2:
            price_low_2 = closes[i]
            price_low_2_idx = i

    # 在20-40日之前找另一个阶段性低点
    prev_start = start
    prev_end = recent_start
    if prev_end - prev_start < 5:
        return {"has_divergence": False, "signal_strength": "none",
                "detail": "历史区间不足，无法判断背离"}

    price_low_1 = closes[prev_start]
    price_low_1_idx = prev_start
    for i in range(prev_start, prev_end):
        if closes[i] < price_low_1:
            price_low_1 = closes[i]
            price_low_1_idx = i

    # 判定背离：股价更低但DIF更高
    if price_low_2 < price_low_1 and dif[price_low_2_idx] > dif[price_low_1_idx]:
        gap = round((dif[price_low_2_idx] - dif[price_low_1_idx]) /
                    abs(dif[price_low_1_idx]) * 100, 1) if dif[price_low_1_idx] != 0 else 100
        if gap > 20:
            strength = "strong"
        elif gap > 10:
            strength = "medium"
        else:
            strength = "weak"
        return {
            "has_divergence": True,
            "signal_strength": strength,
            "detail": (f"底背离：股价{price_low_2:.2f}(新低) vs "
                       f"{price_low_1:.2f}(前低)，DIF {dif[price_low_2_idx]:.2f} > "
                       f"{dif[price_low_1_idx]:.2f}，背离幅度{gap}%"),
        }

    return {"has_divergence": False, "signal_strength": "none",
            "detail": "未检测到底背离信号"}


# ============================================================
# KDJ
# ============================================================

def calc_kdj(
    klines: list[dict],
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> dict:
    """计算 KDJ 随机指标。

    Args:
        klines: K线数据列表
        n: RSV计算周期，默认9
        m1: K值平滑周期，默认3
        m2: D值平滑周期，默认3

    Returns:
        dict: {k: list[float], d: list[float], j: list[float]}

    公式：
        RSV = (C - L_n) / (H_n - L_n) * 100
        K = SMA(RSV, m1)
        D = SMA(K, m2)
        J = 3K - 2D
    """
    closes = _get_closes(klines)
    highs = _get_highs(klines)
    lows = _get_lows(klines)
    length = len(closes)

    k_vals = [50.0] * length   # 初始值50
    d_vals = [50.0] * length
    j_vals = [50.0] * length

    if length < n:
        return {"k": k_vals, "d": d_vals, "j": j_vals}

    alpha_k = 1.0 / m1
    alpha_d = 1.0 / m2

    for i in range(n - 1, length):
        h_max = max(highs[i - n + 1:i + 1])
        l_min = min(lows[i - n + 1:i + 1])
        if h_max == l_min:
            rsv = 50.0
        else:
            rsv = (closes[i] - l_min) / (h_max - l_min) * 100

        if i == n - 1:
            k_vals[i] = 50.0
            d_vals[i] = 50.0
        else:
            k_vals[i] = round(alpha_k * rsv + (1 - alpha_k) * k_vals[i - 1], 2)
            d_vals[i] = round(alpha_d * k_vals[i] + (1 - alpha_d) * d_vals[i - 1], 2)

        j_vals[i] = round(3 * k_vals[i] - 2 * d_vals[i], 2)

    return {"k": k_vals, "d": d_vals, "j": j_vals}


# ============================================================
# RSI
# ============================================================

def calc_rsi(klines: list[dict], period: int = 14) -> list[float]:
    """计算 RSI 相对强弱指标。

    Args:
        klines: K线数据列表
        period: 计算周期，默认14

    Returns:
        list[float]: 与输入等长的RSI序列

    公式: RSI = 100 - 100 / (1 + RS), RS = 平均涨幅 / 平均跌幅
    """
    closes = _get_closes(klines)
    n = len(closes)
    rsi = [50.0] * n

    if n < period + 1:
        return rsi

    gains = []
    losses = []
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = round(100 - 100 / (1 + rs), 2)

    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = round(100 - 100 / (1 + rs), 2)

    return rsi


# ============================================================
# 布林带 BOLL
# ============================================================

def calc_bollinger(
    klines: list[dict],
    period: int = 20,
    std_mult: float = 2.0,
) -> dict:
    """计算布林带 (Bollinger Bands)。

    Args:
        klines: K线数据列表
        period: 移动平均周期，默认20
        std_mult: 标准差倍数，默认2.0

    Returns:
        dict: {
            upper: list[float],   # 上轨 (MID + std_mult * σ)
            mid: list[float],     # 中轨 (MA20)
            lower: list[float],   # 下轨 (MID - std_mult * σ)
            width: list[float],   # 带宽 (upper - lower)
            pct_b: list[float],   # %b = (close - lower) / (upper - lower)
        }

    算法：基于收盘价的移动平均和标准差。带宽收窄到低位时，可能预示方向性突破。
    """
    closes = _get_closes(klines)
    n = len(closes)

    upper = [0.0] * n
    mid = [0.0] * n
    lower = [0.0] * n
    width = [0.0] * n
    pct_b = [0.0] * n

    if n < period:
        return {"upper": upper, "mid": mid, "lower": lower, "width": width, "pct_b": pct_b}

    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        ma = sum(window) / period
        variance = sum((x - ma) ** 2 for x in window) / period
        std = variance ** 0.5

        mid[i] = round(ma, 2)
        upper[i] = round(ma + std_mult * std, 2)
        lower[i] = round(ma - std_mult * std, 2)
        width[i] = round(upper[i] - lower[i], 2)

        if upper[i] != lower[i]:
            pct_b[i] = round((closes[i] - lower[i]) / (upper[i] - lower[i]), 2)
        else:
            pct_b[i] = 0.5

    return {"upper": upper, "mid": mid, "lower": lower, "width": width, "pct_b": pct_b}


# ============================================================
# ADX (平均趋向指数)
# ============================================================

def calc_adx(klines: list[dict], period: int = 14) -> list[float]:
    """计算 ADX 平均趋向指数。

    Args:
        klines: K线数据列表
        period: 计算周期，默认14

    Returns:
        list[float]: 与输入等长的ADX序列

    ADX > 25 表示强趋势，ADX < 20 表示盘整/无趋势。
    不区分方向，仅衡量趋势强度。
    """
    highs = _get_highs(klines)
    lows = _get_lows(klines)
    closes = _get_closes(klines)
    n = len(klines)

    adx = [0.0] * n
    if n < period * 2:
        return adx

    # True Range
    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    # +DM / -DM
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        if up > down and up > 0:
            plus_dm[i] = up
        if down > up and down > 0:
            minus_dm[i] = down

    # 平滑TR, +DM, -DM (Wilder's smoothing)
    atr = [0.0] * n
    atr[period] = sum(tr[1:period + 1])
    smoothed_plus_dm = [0.0] * n
    smoothed_plus_dm[period] = sum(plus_dm[1:period + 1])
    smoothed_minus_dm = [0.0] * n
    smoothed_minus_dm[period] = sum(minus_dm[1:period + 1])

    for i in range(period + 1, n):
        atr[i] = atr[i - 1] - atr[i - 1] / period + tr[i]
        smoothed_plus_dm[i] = smoothed_plus_dm[i - 1] - smoothed_plus_dm[i - 1] / period + plus_dm[i]
        smoothed_minus_dm[i] = smoothed_minus_dm[i - 1] - smoothed_minus_dm[i - 1] / period + minus_dm[i]

    # +DI / -DI / DX / ADX
    plus_di = [0.0] * n
    minus_di = [0.0] * n
    dx = [0.0] * n

    for i in range(period, n):
        if atr[i] > 0:
            plus_di[i] = round(smoothed_plus_dm[i] / atr[i] * 100, 2)
            minus_di[i] = round(smoothed_minus_dm[i] / atr[i] * 100, 2)
        if plus_di[i] + minus_di[i] > 0:
            dx[i] = round(abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i]) * 100, 2)

    # ADX = EMA of DX
    adx[period * 2 - 1] = sum(dx[period:period * 2]) / period
    for i in range(period * 2, n):
        adx[i] = round((adx[i - 1] * (period - 1) + dx[i]) / period, 2)

    return adx


# ============================================================
# ATR
# ============================================================

def calc_atr(klines: list[dict], period: int = 14) -> list[float]:
    """计算 ATR 平均真实波幅。

    Args:
        klines: K线数据列表
        period: 计算周期，默认14

    Returns:
        list[float]: 与输入等长的ATR序列
    """
    highs = _get_highs(klines)
    lows = _get_lows(klines)
    closes = _get_closes(klines)
    n = len(klines)

    atr = [0.0] * n
    if n < period + 1:
        return atr

    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    atr[period] = sum(tr[1:period + 1]) / period
    for i in range(period + 1, n):
        atr[i] = round((atr[i - 1] * (period - 1) + tr[i]) / period, 2)

    return atr


# ============================================================
# OBV (能量潮)
# ============================================================

def calc_obv(klines: list[dict]) -> list[float]:
    """计算 OBV 能量潮指标。

    Returns:
        list[float]: 与输入等长的OBV序列
    """
    closes = _get_closes(klines)
    volumes = _get_volumes(klines)
    n = len(closes)

    obv = [0.0] * n
    if n == 0:
        return obv
    obv[0] = volumes[0]

    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            obv[i] = round(obv[i - 1] + volumes[i], 2)
        elif closes[i] < closes[i - 1]:
            obv[i] = round(obv[i - 1] - volumes[i], 2)
        else:
            obv[i] = obv[i - 1]

    return obv


# ============================================================
# 均线多头/空头排列检测
# ============================================================

def calc_sma(data: list[float], period: int) -> list[float]:
    """计算基于 float 列表的简单移动平均（供策略层直接使用）。

    Args:
        data: float 值列表
        period: 移动平均周期

    Returns:
        list[float]: 与输入等长的 SMA 序列
    """
    n = len(data)
    sma = [0.0] * n
    if n < period:
        return sma
    window_sum = sum(data[:period])
    sma[period - 1] = round(window_sum / period, 2)
    for i in range(period, n):
        window_sum += data[i] - data[i - period]
        sma[i] = round(window_sum / period, 2)
    return sma


def check_ma_alignment(klines: list[dict]) -> dict:
    """检测均线多头排列（MA5 > MA10 > MA20 > MA60）。

    Returns:
        dict: {
            is_bullish: bool,    # 是否多头排列
            alignment: str,      # 'bullish'/'bearish'/'mixed'
            ma_values: dict,     # {ma5, ma10, ma20, ma60} 最新值
        }
    """
    ma5 = calc_ma(klines, 5)
    ma10 = calc_ma(klines, 10)
    ma20 = calc_ma(klines, 20)
    ma60 = calc_ma(klines, 60)

    last = len(klines) - 1
    vals = {
        "ma5": ma5[last],
        "ma10": ma10[last],
        "ma20": ma20[last],
        "ma60": ma60[last],
    }

    is_bullish = (vals["ma5"] > vals["ma10"] > vals["ma20"] > vals["ma60"])
    is_bearish = (vals["ma5"] < vals["ma10"] < vals["ma20"] < vals["ma60"])

    if is_bullish:
        alignment = "bullish"
    elif is_bearish:
        alignment = "bearish"
    else:
        alignment = "mixed"

    return {
        "is_bullish": is_bullish,
        "is_bearish": is_bearish,
        "alignment": alignment,
        "ma_values": vals,
    }
