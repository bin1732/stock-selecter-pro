"""S05 放量突破策略 (S08)

算法核心：
- 当日量 > 20日均量 × 2
- 当日涨幅 > 3%
- 收盘价突破20日高点
- MACD金叉辅助确认

数据源：日K线数据（东方财富 push2his.eastmoney.com）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result
from indicators.technical import calc_macd, check_macd_golden_cross
import config  # noqa: F401

S08_VOL_VS_MA20 = getattr(config, "S08_VOL_VS_MA20", 2.0)       # 当日量/20日均量下限
S08_RISE_MIN = getattr(config, "S08_RISE_MIN", 3.0)              # 当日最低涨幅(%)
S08_HIGH_PERIOD = getattr(config, "S08_HIGH_PERIOD", 20)         # 突破周期(日)
S08_MACD_GOLDEN_CROSS = getattr(config, "S08_MACD_GOLDEN_CROSS", True)   # 是否需要MACD金叉辅助
S08_MACD_CROSS_DAYS = getattr(config, "S08_MACD_CROSS_DAYS", 3)  # 金叉距今日数上限


def check_s05_volume_breakout(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S05 放量突破策略判定。

    Args:
        klines: 日K线列表（需≥40条）
        fundamental: 基本面数据字典（本策略不使用）
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    if not klines or len(klines) < S08_HIGH_PERIOD + 5:
        return make_result(
            code="s08", name="放量突破",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥{S08_HIGH_PERIOD+5}）"],
            details={},
        )

    n = len(klines)
    today = klines[-1]
    prev_20 = klines[-21:-1]  # 前20日不含今日
    prev_all = klines[:-1]

    # ── 条件一：当日放量 ──
    if len(prev_20) >= 5:
        avg_vol_20 = sum(k["volume"] for k in prev_20) / len(prev_20)
        vol_ratio = today["volume"] / avg_vol_20 if avg_vol_20 > 0 else 0
        details["vol_ratio"] = round(vol_ratio, 2)
        details["vol_ratio_threshold"] = S08_VOL_VS_MA20
        vol_pass = vol_ratio >= S08_VOL_VS_MA20
        if vol_pass:
            reasons.append(f"放量 {vol_ratio:.1f}x >= {S08_VOL_VS_MA20}x")
        else:
            reasons.append(f"量比 {vol_ratio:.1f}x < {S08_VOL_VS_MA20}x 不达标")
    else:
        vol_pass = False
        details["vol_ratio"] = None

    # ── 条件二：当日涨幅达标 ──
    if today["close"] > 0 and today["open"] > 0:
        daily_change = (today["close"] - klines[-2]["close"]) / klines[-2]["close"] * 100 if n >= 2 else 0
        details["daily_change"] = round(daily_change, 2)
        details["change_threshold"] = S08_RISE_MIN
        change_pass = daily_change >= S08_RISE_MIN
        if change_pass:
            reasons.append(f"涨幅 {daily_change:.2f}% >= {S08_RISE_MIN}%")
        else:
            reasons.append(f"涨幅 {daily_change:.2f}% < {S08_RISE_MIN}% 不达标")
    else:
        change_pass = False
        details["daily_change"] = None

    # ── 条件三：收盘价突破20日高点 ──
    if len(prev_20) >= 5:
        high_20 = max(k["high"] for k in prev_20)
        details["high_20"] = round(high_20, 2)
        details["close"] = round(today["close"], 2)
        if today["close"] > high_20:
            breakout_pass = True
            reasons.append(f"收盘 {today['close']:.2f} 突破20日高点 {high_20:.2f}")
        else:
            breakout_pass = False
            reasons.append(f"收盘 {today['close']:.2f} 未突破20日高点 {high_20:.2f}")
    else:
        breakout_pass = False
        details["high_20"] = None

    # ── 条件四：MACD金叉辅助 ──
    macd_pass = False
    if S08_MACD_GOLDEN_CROSS and len(klines) >= 26:
        macd_result = calc_macd(klines)
        if macd_result:
            golden = check_macd_golden_cross(klines, recent=5)
            details["macd_golden_cross"] = golden
            # 金叉在近N日内
            if golden and golden.get("has_cross"):
                cross_days_ago = (n - 1) - golden.get("cross_index", -1)
                if 0 <= cross_days_ago <= S08_MACD_CROSS_DAYS:
                    macd_pass = True
                    reasons.append(f"MACD金叉确认 (DIF上穿DEA {cross_days_ago}日前)")
                else:
                    reasons.append(f"MACD金叉距今日数超过{S08_MACD_CROSS_DAYS}日")
            else:
                reasons.append("MACD未出现近3日金叉")
        else:
            details["macd_golden_cross"] = None
    else:
        details["macd_golden_cross"] = None

    # ── 综合评分 ──
    if vol_pass:
        score += 0.3
    if change_pass:
        score += 0.25
    if breakout_pass:
        score += 0.3
    if macd_pass:
        score += 0.15

    details["conditions"] = {
        "vol_pass": vol_pass,
        "change_pass": change_pass,
        "breakout_pass": breakout_pass,
        "macd_pass": macd_pass,
    }

    return make_result(
        code="s08", name="放量突破",
        passed=vol_pass and change_pass and breakout_pass,  # 核心三条件
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s05_volume_breakout"]
