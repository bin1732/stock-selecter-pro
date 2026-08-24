"""S05 MACD底背离策略。

基于MACD指标识别股价与指标之间的底背离信号：
- 股价创新低，DIF未创新低 → 底背离
- 信号强度按背离幅度分级（弱/中/强）

数据源：基于日K线的MACD计算（东方财富公开行情数据）
"""

import config
from .base import make_result, clean_klines
from indicators.technical import calc_macd


def _find_local_minima(values: list, window: int = None) -> list[int]:
    """在值列表中查找局部极小值索引。"""
    window = window or config.S05_LOW_WINDOW
    idxs = []
    for i in range(window, len(values) - window):
        left = values[i - window:i]
        right = values[i + 1:i + window + 1]
        if values[i] <= min(left) and values[i] <= min(right):
            idxs.append(i)
    return idxs


def check_s05_macd_divergence(klines: list, fundamental: dict = None, money_flow: dict = None) -> dict:
    """S05 MACD底背离：检测日线MACD底背离信号。

    算法：
    1. 基于日K线计算EMA12、EMA26、DIF、DEA、MACD柱
    2. 在近60日数据中寻找最近两个低点
    3. 股价低点下降 + DIF低点上升 → 底背离

    Returns:
        {passed, score, reasons, details, signal}
    """
    klines = clean_klines(klines)
    if not klines or len(klines) < 30:
        return make_result("S05", "MACD底背离", False, 0, ["K线数据不足(需要≥30条)"])

    closes = [k["close"] for k in klines]

    # 统一使用库实现计算 MACD（DIF/DEA/MACD柱），与 indicators.technical 保持一致
    macd_data = calc_macd(
        klines,
        fast=config.S05_EMA_FAST,
        slow=config.S05_EMA_SLOW,
        signal=config.S05_EMA_SIGNAL,
    )
    dif = macd_data["dif"]

    # 在最近N个数据中找局部低点
    n = min(config.S05_LOOKBACK, len(klines))
    start = len(klines) - n
    end = len(klines)

    price_lows = _find_local_minima(closes[start:end])

    if len(price_lows) < 2:
        return make_result("S05", "MACD底背离", False, 0, [f"近{n}日未检测到足够的价格低点"], {})

    # 取最近两个价格低点
    pidx1 = price_lows[-2]  # 较早的低点
    pidx2 = price_lows[-1]  # 较近的低点

    # 查找对应时间范围的DIF低点
    abs_p1 = start + pidx1
    abs_p2 = start + pidx2

    # 判断是否底背离：股价新低但DIF未新低
    price_new_low = closes[abs_p2] <= closes[abs_p1]
    dif_not_new_low = dif[abs_p2] > dif[abs_p1]

    # DIF 拐头向上确认（仅依据当日及历史数据，无前视偏差）
    dif_turning_up = (
        abs_p2 > 1
        and dif[abs_p2] > dif[abs_p2 - 1]
    )

    divergence_strength = 0
    if price_new_low and dif_not_new_low:
        # 计算背离幅度
        price_decline = (closes[abs_p1] - closes[abs_p2]) / closes[abs_p1] if closes[abs_p1] else 0
        # 分母下限保护：DIF 接近零轴时 abs(dif) 极小，相对变化率会爆炸。
        # 下限取 0.5：零轴附近的微弱 DIF 抬升不再虚高评级，真实信号分级不受影响。
        dif_rise = (dif[abs_p2] - dif[abs_p1]) / max(abs(dif[abs_p1]), 0.5) if dif[abs_p1] else 0
        divergence_strength = price_decline + dif_rise  # 背离强度

    passed = price_new_low and dif_not_new_low and divergence_strength > config.S05_DIVERGENCE_MIN_GAP
    reasons = []

    if price_new_low and dif_not_new_low:
        reasons.append(f"股价{klines[abs_p1]['date']}→{klines[abs_p2]['date']}创新低，DIF同步抬升")
        reasons.append(f"背离强度: {divergence_strength:.3f}")
        if dif_turning_up:
            reasons.append("DIF处于拐头向上阶段")
    elif price_new_low:
        reasons.append("股价创新低但DIF同步新低，无背离")
    else:
        reasons.append(f"近{n}日未检测到MACD底背离信号")

    if divergence_strength >= config.S05_STRONG_GAP:
        signal = "强"; score = 0.9
    elif divergence_strength >= config.S05_MID_GAP:
        signal = "中"; score = 0.65
    elif passed:
        signal = "弱"; score = 0.4
    else:
        signal = None; score = 0

    return make_result("S05", "MACD底背离", passed, score, reasons,
                       {"divergence_strength": divergence_strength, "dif_turning_up": dif_turning_up,
                        "price_low_date1": klines[abs_p1]["date"], "price_low_date2": klines[abs_p2]["date"]},
                       signal)
