"""S09 趋势分析策略

算法核心：
- 多周期均线多头排列（5/10/20/60日）
- ADX > 25 趋势确认
- 价格在60日均线上方

数据源：日K线数据（东方财富 push2his.eastmoney.com）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result
from indicators.technical import calc_adx, check_ma_alignment
import config  # noqa: F401

S09_MA_PERIODS = getattr(config, "S09_MA_PERIODS", [5, 10, 20, 60])  # 均线周期
S09_ADX_MIN = getattr(config, "S09_ADX_MIN", 25.0)                    # ADX最低值
S09_ADX_PERIOD = getattr(config, "S09_ADX_PERIOD", 14)                # ADX计算周期
S09_CENTER_DAYS = getattr(config, "S09_CENTER_DAYS", 5)               # 价格重心对比天数


def check_s09_trend_analysis(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S09 趋势分析策略判定。

    Args:
        klines: 日K线列表（需≥60条）
        fundamental: 基本面数据字典（本策略不使用）
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    min_len = max(S09_MA_PERIODS) + S09_ADX_PERIOD + 10
    if not klines or len(klines) < min_len:
        return make_result(
            code="S09", name="趋势分析",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥{min_len}）"],
            details={},
        )

    closes = [k["close"] for k in klines]

    # ── 条件一：均线多头排列 ──
    alignment = check_ma_alignment(klines, periods=tuple(S09_MA_PERIODS))
    ma_values = alignment["ma_values"]
    details["ma_values"] = ma_values
    details["ma_alignment"] = alignment

    if alignment and alignment.get("is_bullish", False):
        alignment_pass = True
        reasons.append("均线多头排列")
    else:
        alignment_pass = False
        # 给出哪些不对齐
        failed = []
        for i in range(len(S09_MA_PERIODS) - 1):
            ma_a_key = f"MA{S09_MA_PERIODS[i]}"
            ma_b_key = f"MA{S09_MA_PERIODS[i+1]}"
            va = ma_values.get(ma_a_key)
            vb = ma_values.get(ma_b_key)
            if va is not None and vb is not None and va <= vb:
                failed.append(f"{ma_a_key}({va}) <= {ma_b_key}({vb})")
        if failed:
            reasons.append(f"均线非多头排列: {', '.join(failed[:2])}")

    # ── 条件二：ADX趋势强度 ──
    adx = calc_adx(klines, period=S09_ADX_PERIOD)
    if adx and len(adx) > 0:
        latest_adx = adx[-1]
        details["adx"] = round(latest_adx, 2)
        details["adx_threshold"] = S09_ADX_MIN
        if latest_adx >= S09_ADX_MIN:
            adx_pass = True
            reasons.append(f"ADX {latest_adx:.1f} >= {S09_ADX_MIN} 趋势明确")
        else:
            adx_pass = False
            reasons.append(f"ADX {latest_adx:.1f} < {S09_ADX_MIN} 趋势不强")
    else:
        adx_pass = False
        details["adx"] = None

    # ── 条件三：价格在60日均线上方 ──
    ma60_pass = False
    ma60_val = ma_values.get("MA60")
    if ma60_val is not None and ma60_val > 0:
        latest_close = closes[-1]
        details["close_vs_ma60"] = round(latest_close / ma60_val, 3)
        if latest_close > ma60_val:
            ma60_pass = True
            reasons.append(f"收盘 {latest_close:.2f} > MA60 {ma60_val:.2f}")
        else:
            reasons.append(f"收盘 {latest_close:.2f} <= MA60 {ma60_val:.2f}")
    else:
        details["close_vs_ma60"] = None

    # ── 条件四：近5日价格重心上移 ──
    center_pass = False
    if len(closes) >= S09_CENTER_DAYS * 2:
        avg_5_recent = sum(closes[-S09_CENTER_DAYS:]) / S09_CENTER_DAYS
        avg_5_prev = sum(closes[-S09_CENTER_DAYS * 2:-S09_CENTER_DAYS]) / S09_CENTER_DAYS
        details["avg_5_recent"] = round(avg_5_recent, 2)
        details["avg_5_prev"] = round(avg_5_prev, 2)
        if avg_5_recent > avg_5_prev:
            center_pass = True
    else:
        details["avg_5_recent"] = None

    # ── 综合评分 ──
    if alignment_pass:
        score += 0.35
    if adx_pass:
        score += 0.3
    if ma60_pass:
        score += 0.2
    if center_pass:
        score += 0.15

    details["conditions"] = {
        "alignment_pass": alignment_pass,
        "adx_pass": adx_pass,
        "ma60_pass": ma60_pass,
        "center_pass": center_pass,
    }

    return make_result(
        code="S09", name="趋势分析",
        passed=alignment_pass and adx_pass and ma60_pass,
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s09_trend_analysis"]
