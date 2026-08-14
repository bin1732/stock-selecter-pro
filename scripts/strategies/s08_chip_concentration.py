"""S08 筹码集中度策略 (S11)

算法核心：
- 基于 K 线数据估算筹码集中度（换手率连续低位 + 振幅收窄）
- 实际场景中需补充股东户数数据（东方财富股东户数API为付费，此处用技术面代理）

代理算法：
- 近20日换手率均值 < 1.5%（筹码锁定）
- 近20日振幅 < 15%（筹码稳定）
- 收盘价在20日、60日均线上方（主力护盘迹象）

数据源：日K线数据（东方财富 push2his.eastmoney.com）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result
from indicators import calc_sma
import config  # noqa: F401

S11_TURNOVER_MAX = getattr(config, "S11_TURNOVER_MAX", 1.5)          # 日均换手率上限(%)
S11_AMPLITUDE_MAX = getattr(config, "S11_AMPLITUDE_MAX", 15.0)       # 近20日振幅上限(%)
S11_MA_PERIODS = getattr(config, "S11_MA_PERIODS", [20, 60])         # 均线判断周期
S11_TREND_BAND = getattr(config, "S11_TREND_BAND", 0.15)             # 近10日均价偏离60日均价幅度上限


def check_s08_chip_concentration(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S08 筹码集中度策略判定（技术面代理）。

    Args:
        klines: 日K线列表（需≥60条，含turnover字段）
        fundamental: 基本面数据字典（本策略不使用）
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    if not klines or len(klines) < 60:
        return make_result(
            code="s11", name="筹码集中",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥60）"],
            details={},
        )

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]

    # ── 条件一：近20日换手率均值低 ──
    turnover_pass = False
    turnovers = [k.get("turnover", 0) for k in klines[-20:] if k.get("turnover")]
    if turnovers:
        avg_turnover = sum(turnovers) / len(turnovers)
        details["avg_turnover_20"] = round(avg_turnover, 2)
        details["turnover_threshold"] = S11_TURNOVER_MAX
        if avg_turnover < S11_TURNOVER_MAX:
            turnover_pass = True
            reasons.append(f"近20日均换手率 {avg_turnover:.2f}% < {S11_TURNOVER_MAX}% 筹码锁定")
        else:
            reasons.append(f"近20日均换手率 {avg_turnover:.2f}% >= {S11_TURNOVER_MAX}% 换手偏高")
    else:
        details["avg_turnover_20"] = None

    # ── 条件二：近20日振幅收窄 ──
    amp_pass = False
    recent_20_highs = highs[-20:]
    recent_20_lows = lows[-20:]
    if recent_20_highs and recent_20_lows:
        max_h = max(recent_20_highs)
        min_l = min(recent_20_lows)
        if min_l > 0:
            amplitude = (max_h - min_l) / min_l * 100
            details["amplitude_20"] = round(amplitude, 2)
            details["amplitude_threshold"] = S11_AMPLITUDE_MAX
            if amplitude < S11_AMPLITUDE_MAX:
                amp_pass = True
                reasons.append(f"近20日振幅 {amplitude:.1f}% < {S11_AMPLITUDE_MAX}% 筹码稳定")
            else:
                reasons.append(f"近20日振幅 {amplitude:.1f}% >= {S11_AMPLITUDE_MAX}% 波动偏大")
    else:
        details["amplitude_20"] = None

    # ── 条件三：价格在均线上方 ──
    ma_pass = True
    ma_values = {}
    latest_close = closes[-1]
    for period in S11_MA_PERIODS:
        ma = calc_sma(closes, period)
        if ma and len(ma) > 0:
            ma_val = ma[-1]
            ma_values[f"MA{period}"] = round(ma_val, 2)
            if latest_close <= ma_val:
                ma_pass = False
                reasons.append(f"收盘 {latest_close:.2f} <= MA{period} {ma_val:.2f}")
        else:
            ma_values[f"MA{period}"] = None
    details["ma_values"] = ma_values
    if ma_pass and ma_values:
        reasons.append("价格在关键均线上方，主力护盘")

    # ── 条件四：近60日整体趋势收窄 ──
    trend_pass = False
    if len(closes) >= 60:
        avg_60_recent = sum(closes[-10:]) / 10
        avg_60_full = sum(closes[-60:]) / 60
        details["avg_10_vs_avg_60"] = round(avg_60_recent / avg_60_full, 3) if avg_60_full > 0 else None
        if avg_60_full > 0 and abs(avg_60_recent / avg_60_full - 1) < S11_TREND_BAND:
            trend_pass = True

    details["conditions"] = {
        "turnover_pass": turnover_pass,
        "amp_pass": amp_pass,
        "ma_pass": ma_pass,
        "trend_pass": trend_pass,
    }

    if turnover_pass:
        score += 0.3
    if amp_pass:
        score += 0.3
    if ma_pass:
        score += 0.25
    if trend_pass:
        score += 0.15

    return make_result(
        code="s11", name="筹码集中",
        passed=turnover_pass and amp_pass,  # 换手+振幅为核心
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s08_chip_concentration"]
