"""S13 海龟交易策略 (S16)

算法核心（经典海龟趋势跟踪规则，适配单股筛选场景）：
- 唐奇安通道突破：收盘价突破近20日最高价（入场通道，不含当日）触发突破信号
- 顺势过滤：收盘价在60日均线上方，只参与上升趋势（海龟为顺势策略）
- 趋势强度：ADX >= 20 排除震荡市的假突破
- 风险如实提示：输出基于 2*ATR 的止损参考价与止损幅度（仅供参考，不构成投资建议）

数据源：日K线数据（东方财富 push2his / 腾讯·新浪备选通道）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result
from indicators.technical import calc_atr, calc_adx, calc_ma
import config  # noqa: F401

S16_ENTRY_PERIOD = getattr(config, "S16_ENTRY_PERIOD", 20)      # 入场通道：近N日最高价（不含当日）
S16_EXIT_PERIOD = getattr(config, "S16_EXIT_PERIOD", 10)        # 退出通道：近N日最低价
S16_ADX_MIN = getattr(config, "S16_ADX_MIN", 20.0)              # 趋势强度门槛
S16_ADX_PERIOD = getattr(config, "S16_ADX_PERIOD", 14)          # ADX计算周期
S16_ATR_PERIOD = getattr(config, "S16_ATR_PERIOD", 14)          # ATR计算周期
S16_ATR_STOP_MULT = getattr(config, "S16_ATR_STOP_MULT", 2.0)   # 止损倍数：入场价 - N*ATR
S16_MA_PERIOD = getattr(config, "S16_MA_PERIOD", 60)            # 长期趋势过滤均线周期


def check_s13_turtle(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S13 海龟交易策略判定（唐奇安通道突破 + 趋势过滤）。

    Args:
        klines: 日K线列表（需≥84条）
        fundamental: 基本面数据字典（本策略不使用）
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    min_len = S16_MA_PERIOD + S16_ADX_PERIOD + 10
    if not klines or len(klines) < min_len:
        return make_result(
            code="s16", name="海龟交易",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥{min_len}）"],
            details={},
        )

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    latest_close = closes[-1]

    # ── 条件一：唐奇安通道突破（收盘突破近20日最高价，不含当日） ──
    break_pass = False
    if len(highs) > S16_ENTRY_PERIOD:
        entry_high = max(highs[-S16_ENTRY_PERIOD - 1:-1])  # 不含当日的近20日最高
        exit_low = min(lows[-S16_EXIT_PERIOD:])
        details["entry_channel_high"] = round(entry_high, 2)
        details["exit_channel_low"] = round(exit_low, 2)
        details["close"] = round(latest_close, 2)
        if latest_close > entry_high:
            break_pass = True
            reasons.append(f"收盘 {latest_close:.2f} 突破近{S16_ENTRY_PERIOD}日最高价 {entry_high:.2f}")
        else:
            reasons.append(f"收盘 {latest_close:.2f} 未突破近{S16_ENTRY_PERIOD}日最高价 {entry_high:.2f}")

    # ── 条件二：趋势强度 ADX（排除震荡假突破） ──
    adx_pass = False
    adx = calc_adx(klines, period=S16_ADX_PERIOD)
    if adx and len(adx) > 0:
        latest_adx = adx[-1]
        details["adx"] = round(latest_adx, 2)
        details["adx_threshold"] = S16_ADX_MIN
        if latest_adx >= S16_ADX_MIN:
            adx_pass = True
            reasons.append(f"ADX {latest_adx:.1f} >= {S16_ADX_MIN} 趋势明确")
        else:
            reasons.append(f"ADX {latest_adx:.1f} < {S16_ADX_MIN} 趋势强度不足")

    # ── 条件三：价格在60日均线上方（顺势过滤） ──
    ma60_pass = False
    ma60 = calc_ma(klines, S16_MA_PERIOD)
    ma60_val = ma60[-1] if ma60 and len(ma60) > 0 else 0.0
    if ma60_val > 0:
        details["ma60"] = round(ma60_val, 2)
        if latest_close > ma60_val:
            ma60_pass = True
            reasons.append(f"收盘 {latest_close:.2f} > MA{S16_MA_PERIOD} {ma60_val:.2f} 顺势")
        else:
            reasons.append(f"收盘 {latest_close:.2f} <= MA{S16_MA_PERIOD} {ma60_val:.2f} 逆势")

    # ── 风险如实提示：基于 ATR 的止损参考 ──
    atr_vals = calc_atr(klines, period=S16_ATR_PERIOD)
    atr = atr_vals[-1] if atr_vals and len(atr_vals) > 0 else 0.0
    stop_price = round(latest_close - S16_ATR_STOP_MULT * atr, 2)
    risk_pct = round(S16_ATR_STOP_MULT * atr / latest_close * 100, 2) if latest_close > 0 else 0.0
    details["atr"] = round(atr, 2)
    details["stop_price"] = stop_price
    details["risk_pct"] = risk_pct
    if atr > 0:
        reasons.append(f"止损参考 {stop_price:.2f}（2*ATR，风险约{risk_pct:.1f}%，仅供风控参考）")

    # ── 综合评分 ──
    if break_pass:
        score += 0.5
    if adx_pass:
        score += 0.3
    if ma60_pass:
        score += 0.2

    details["conditions"] = {
        "break_pass": break_pass,
        "adx_pass": adx_pass,
        "ma60_pass": ma60_pass,
    }

    return make_result(
        code="s16", name="海龟交易",
        passed=break_pass,
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s13_turtle"]
