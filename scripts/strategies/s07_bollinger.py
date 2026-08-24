"""S10 布林带下轨反弹策略

判定逻辑：
- 核心通过条件：收盘价触及布林下轨 + RSI < 30 超卖 + 当日/次日阳线确认（防假突破）
- 辅助加分条件（仅影响评分与详情，不参与通过判定）：成交量缩至近5日最低（缩量企稳）

数据源：日K线数据（东方财富 push2his.eastmoney.com）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result, clean_klines
from indicators.technical import calc_bollinger, calc_rsi
import config  # noqa: F401

S10_BOLL_PERIOD = getattr(config, "S10_BOLL_PERIOD", 20)              # 布林带计算周期
S10_BOLL_STD = getattr(config, "S10_BOLL_STD", 2.0)                  # 标准差倍数
S10_RSI_MAX = getattr(config, "S10_RSI_MAX", 30.0)                   # RSI超卖上限
S10_RSI_PERIOD = getattr(config, "S10_RSI_PERIOD", 14)               # RSI周期
S10_VOL_LOW_DAYS = getattr(config, "S10_VOL_LOW_DAYS", 5)            # 缩量对比天数
S10_VOL_MIN_TOLERANCE = getattr(config, "S10_VOL_MIN_TOLERANCE", 1.05)  # 缩量容差
S10_TOUCH_TOLERANCE = getattr(config, "S10_TOUCH_TOLERANCE", 1.02)   # 触及下轨容差


def check_s10_bollinger(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S10 布林带下轨反弹策略判定。

    Args:
        klines: 日K线列表（需≥30条）
        fundamental: 基本面数据字典（本策略不使用）
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    klines = clean_klines(klines)
    reasons = []
    details = {}
    score = 0.0

    min_len = max(S10_BOLL_PERIOD, S10_RSI_PERIOD) + 10
    if not klines or len(klines) < min_len:
        return make_result(
            code="S10", name="布林带下轨",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥{min_len}）"],
            details={},
        )

    closes = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]

    # ── 布林带计算 ──
    boll = calc_bollinger(klines, period=S10_BOLL_PERIOD, std_mult=S10_BOLL_STD)
    if not boll or len(boll["lower"]) == 0:
        return make_result(
            code="S10", name="布林带下轨",
            passed=False,
            score=0,
            reasons=["布林带计算失败"],
            details={},
        )

    lower_band = boll["lower"][-1]
    middle_band = boll["mid"][-1]
    upper_band = boll["upper"][-1]
    latest_close = closes[-1]

    details["boll_lower"] = round(lower_band, 2)
    details["boll_middle"] = round(middle_band, 2)
    details["boll_upper"] = round(upper_band, 2)
    details["close"] = round(latest_close, 2)

    # ── 条件一：收盘价触及或跌破布林下轨 ──
    # 允许容差（防临界波动误判）
    if latest_close <= lower_band * S10_TOUCH_TOLERANCE:
        touch_pass = True
        if latest_close <= lower_band:
            reasons.append(f"收盘 {latest_close:.2f} 跌破布林下轨 {lower_band:.2f}")
        else:
            reasons.append(f"收盘 {latest_close:.2f} 触及布林下轨 {lower_band:.2f}")
    else:
        touch_pass = False
        reasons.append(f"收盘 {latest_close:.2f} 远离布林下轨 {lower_band:.2f}")

    # ── 条件二：成交量缩至近5日最低 ──
    vol_shrink_pass = False
    if len(volumes) >= S10_VOL_LOW_DAYS + 1:
        # 对比窗口不含当日（近5日的前5日），避免"当日 vs 当日"导致条件恒真
        recent_vols = volumes[-(S10_VOL_LOW_DAYS + 1):-1]
        min_recent_vol = min(recent_vols)
        details["min_prev_volume"] = int(min_recent_vol)
        details["current_volume"] = int(volumes[-1])
        if volumes[-1] <= min_recent_vol * S10_VOL_MIN_TOLERANCE:  # 低于前N日最低（含容差）
            vol_shrink_pass = True
            reasons.append(f"成交量 {volumes[-1]:.0f} 缩至前{S10_VOL_LOW_DAYS}日最低 {min_recent_vol:.0f} 附近")
        else:
            reasons.append("成交量未明显萎缩")
    else:
        details["current_volume"] = volumes[-1] if volumes else None

    # ── 条件三：RSI超卖 ──
    rsi_pass = False
    rsi_vals = calc_rsi(klines, period=S10_RSI_PERIOD)
    if rsi_vals and len(rsi_vals) > 0:
        latest_rsi = rsi_vals[-1]
        details["rsi"] = round(latest_rsi, 2)
        details["rsi_threshold"] = S10_RSI_MAX
        if latest_rsi < S10_RSI_MAX:
            rsi_pass = True
            reasons.append(f"RSI {latest_rsi:.1f} < {S10_RSI_MAX} 超卖")
        else:
            reasons.append(f"RSI {latest_rsi:.1f} >= {S10_RSI_MAX} 未超卖")
    else:
        details["rsi"] = None

    # ── 条件四：近1-2日阳线确认 ──
    yang_pass = False
    prev_day = klines[-2] if len(klines) >= 2 else None
    today = klines[-1]
    if today["close"] >= today["open"]:
        yang_pass = True
        reasons.append("当日收阳线")
    elif prev_day and prev_day["close"] >= prev_day["open"]:
        yang_pass = True
        reasons.append("前日收阳线，等待今日确认")
    else:
        reasons.append("近2日未见阳线确认信号")

    details["conditions"] = {
        "touch_pass": touch_pass,
        "vol_shrink_pass": vol_shrink_pass,
        "rsi_pass": rsi_pass,
        "yang_pass": yang_pass,
    }

    if touch_pass:
        score += 0.4
    if vol_shrink_pass:
        score += 0.2
    if rsi_pass:
        score += 0.2
    if yang_pass:
        score += 0.2

    return make_result(
        code="S10", name="布林带下轨",
        passed=touch_pass and rsi_pass and yang_pass,
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s10_bollinger"]
