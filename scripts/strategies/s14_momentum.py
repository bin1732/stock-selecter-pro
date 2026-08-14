"""S14 动量策略 (S17)

算法核心（基于价格动量的确定性量化）：
- 中期动量：近60日收益率 >= 8%（核心动量条件，经典动量窗口）
- 短期延续：近20日收益率为正（动量未衰竭）
- 趋势背景：收盘价在60日均线上方（动量有效的前提，避免下跌反抽伪动量）
- 过热过滤：RSI < 75 且价格乖离MA60 < 25%（防止追高）

数据源：日K线数据（东方财富 push2his / 腾讯·新浪备选通道）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result
from indicators.technical import calc_rsi, calc_ma
import config  # noqa: F401

S17_MOM_MID = getattr(config, "S17_MOM_MID", 60)          # 中期动量窗口（交易日）
S17_MOM_SHORT = getattr(config, "S17_MOM_SHORT", 20)      # 短期延续窗口
S17_MOM_MID_MIN = getattr(config, "S17_MOM_MID_MIN", 0.08)  # 中期动量最低收益（8%）
S17_RSI_PERIOD = getattr(config, "S17_RSI_PERIOD", 14)    # RSI周期
S17_RSI_MAX = getattr(config, "S17_RSI_MAX", 75.0)        # RSI过热上限
S17_MA_PERIOD = getattr(config, "S17_MA_PERIOD", 60)      # 趋势背景均线周期
S17_MA_BIAS_MAX = getattr(config, "S17_MA_BIAS_MAX", 0.25)  # 乖离MA上限（25%，防追高）


def check_s14_momentum(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S14 动量策略判定。

    Args:
        klines: 日K线列表（需≥65条）
        fundamental: 基本面数据字典（本策略不使用）
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    min_len = S17_MOM_MID + S17_RSI_PERIOD + 5
    if not klines or len(klines) < min_len:
        return make_result(
            code="s17", name="动量策略",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥{min_len}）"],
            details={},
        )

    closes = [k["close"] for k in klines]
    latest_close = closes[-1]
    details["close"] = round(latest_close, 2)

    # ── 条件一：中期动量（近60日收益率） ──
    mid_pass = False
    mid_mom = None
    if len(closes) > S17_MOM_MID:
        base = closes[-S17_MOM_MID - 1]
        if base > 0:
            mid_mom = latest_close / base - 1
            details["mom_mid"] = round(mid_mom, 4)
            details["mom_mid_threshold"] = S17_MOM_MID_MIN
            if mid_mom >= S17_MOM_MID_MIN:
                mid_pass = True
                reasons.append(f"近{S17_MOM_MID}日动量 {mid_mom * 100:.1f}% >= "
                               f"{S17_MOM_MID_MIN * 100:.0f}% 中期动量成立")
            else:
                reasons.append(f"近{S17_MOM_MID}日动量 {mid_mom * 100:.1f}% < "
                               f"{S17_MOM_MID_MIN * 100:.0f}% 中期动量不足")

    # ── 条件二：短期延续（近20日收益率为正） ──
    short_pass = False
    short_mom = None
    if len(closes) > S17_MOM_SHORT:
        base = closes[-S17_MOM_SHORT - 1]
        if base > 0:
            short_mom = latest_close / base - 1
            details["mom_short"] = round(short_mom, 4)
            if short_mom > 0:
                short_pass = True
                reasons.append(f"近{S17_MOM_SHORT}日动量 {short_mom * 100:.1f}% 为正（动能延续）")
            else:
                reasons.append(f"近{S17_MOM_SHORT}日动量 {short_mom * 100:.1f}% 未延续为正")

    # ── 条件三：趋势背景（价格在MA60上方） ──
    ma_pass = False
    ma60 = calc_ma(klines, S17_MA_PERIOD)
    ma60_val = ma60[-1] if ma60 and len(ma60) > 0 else 0.0
    if ma60_val > 0:
        details["ma60"] = round(ma60_val, 2)
        if latest_close > ma60_val:
            ma_pass = True
            reasons.append(f"收盘 {latest_close:.2f} > MA{S17_MA_PERIOD} {ma60_val:.2f} 趋势背景成立")
        else:
            reasons.append(f"收盘 {latest_close:.2f} <= MA{S17_MA_PERIOD} {ma60_val:.2f} 趋势背景不足")

    # ── 条件四：过热过滤（RSI 与乖离率） ──
    cool_pass = False
    rsi_vals = calc_rsi(klines, period=S17_RSI_PERIOD)
    rsi = rsi_vals[-1] if rsi_vals and len(rsi_vals) > 0 else 50.0
    bias = latest_close / ma60_val - 1 if ma60_val > 0 else 0.0
    details["rsi"] = round(rsi, 2)
    details["rsi_threshold"] = S17_RSI_MAX
    details["bias_ma60"] = round(bias, 4)
    details["bias_threshold"] = S17_MA_BIAS_MAX
    if rsi < S17_RSI_MAX and bias < S17_MA_BIAS_MAX:
        cool_pass = True
        reasons.append(f"RSI {rsi:.1f} < {S17_RSI_MAX} 且乖离MA60 {bias * 100:.1f}% < "
                       f"{S17_MA_BIAS_MAX * 100:.0f}% 未过热")
    else:
        reasons.append(f"RSI {rsi:.1f} / 乖离MA60 {bias * 100:.1f}% 存在追高风险")

    # ── 综合评分 ──
    if mid_pass:
        score += 0.4
    if short_pass:
        score += 0.2
    if ma_pass:
        score += 0.2
    if cool_pass:
        score += 0.2

    details["conditions"] = {
        "mid_pass": mid_pass,
        "short_pass": short_pass,
        "ma_pass": ma_pass,
        "cool_pass": cool_pass,
    }

    return make_result(
        code="s17", name="动量策略",
        passed=mid_pass,
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s14_momentum"]
