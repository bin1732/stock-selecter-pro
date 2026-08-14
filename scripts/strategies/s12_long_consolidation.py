"""S12 长期低位蓄力策略 (S15)

算法核心：
- 60日跌幅 > 15%：处于长期低位
- 近20日横盘振幅 < 10%：蓄力
- 底部放量迹象：近5日量 > 60日均量 × 1.5
- 资金面辅助：价格不再创新低

数据源：日K线数据（东方财富 push2his.eastmoney.com）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result
import config  # noqa: F401

S15_DECLINE_60D_MIN = getattr(config, "S15_DECLINE_60D_MIN", 15.0)  # 60日最小跌幅(%)
S15_CONSO_20D_AMP_MAX = getattr(config, "S15_CONSO_20D_AMP_MAX", 10.0)  # 20日横盘振幅上限(%)
S15_BOTTOM_VOL_VS_MA60 = getattr(config, "S15_BOTTOM_VOL_VS_MA60", 1.5)  # 5日量/60日均量下限
S15_FLOW_DAYS_MIN = getattr(config, "S15_FLOW_DAYS_MIN", 3)          # 主力连续净流入天数下限
S15_LOW_STABILIZE_TOL = getattr(config, "S15_LOW_STABILIZE_TOL", 0.98)  # 近10日低点接近20日低点容差


def check_s12_long_consolidation(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S12 长期低位蓄力策略判定。

    Args:
        klines: 日K线列表（需≥60条）
        fundamental: 基本面数据字典（本策略不使用）
        money_flow: 资金流数据。可为 fetch_stock_money_flow 的 list[dict]（逐日主力净流入，
            自动统计连续流入天数），或含 continuous_inflow/is_continuous 键的 dict

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    if not klines or len(klines) < 60:
        return make_result(
            code="s15", name="长期蓄力",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥60）"],
            details={},
        )

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]

    n = len(closes)

    # ── 条件一：60日跌幅 > 15% ──
    price_60_ago = closes[-60]
    price_now = closes[-1]
    decline_60 = (price_60_ago - price_now) / price_60_ago * 100 if price_60_ago > 0 else 0
    details["decline_60"] = round(decline_60, 2)
    details["decline_threshold"] = S15_DECLINE_60D_MIN
    if decline_60 >= S15_DECLINE_60D_MIN:
        decline_pass = True
        reasons.append(f"60日跌幅 {decline_60:.1f}% >= {S15_DECLINE_60D_MIN}% 处于低位")
    else:
        decline_pass = False
        reasons.append(f"60日跌幅 {decline_60:.1f}% < {S15_DECLINE_60D_MIN}% 回调不够深")

    # ── 条件二：近20日横盘振幅 < 10% ──
    amp_pass = False
    if n >= 20:
        recent_20_high = max(highs[-20:])
        recent_20_low = min(lows[-20:])
        if recent_20_low > 0:
            amplitude_20 = (recent_20_high - recent_20_low) / recent_20_low * 100
            details["amplitude_20"] = round(amplitude_20, 2)
            details["amplitude_threshold"] = S15_CONSO_20D_AMP_MAX
            if amplitude_20 < S15_CONSO_20D_AMP_MAX:
                amp_pass = True
                reasons.append(f"近20日振幅 {amplitude_20:.1f}% < {S15_CONSO_20D_AMP_MAX}% 蓄力横盘")
            else:
                reasons.append(f"近20日振幅 {amplitude_20:.1f}% >= {S15_CONSO_20D_AMP_MAX}% 波动偏大")
        else:
            details["amplitude_20"] = None
    else:
        details["amplitude_20"] = None

    # ── 条件三：底部放量迹象 ──
    vol_pass = False
    if n >= 60:
        avg_vol_60 = sum(volumes[-60:]) / 60
        avg_vol_5 = sum(volumes[-5:]) / 5
        if avg_vol_60 > 0:
            vol_ratio = avg_vol_5 / avg_vol_60
            details["vol_ratio_5_vs_60"] = round(vol_ratio, 2)
            details["vol_ratio_threshold"] = S15_BOTTOM_VOL_VS_MA60
            if vol_ratio >= S15_BOTTOM_VOL_VS_MA60:
                vol_pass = True
                reasons.append(f"近5日均量 {avg_vol_5:.0f} / 60日均量 {avg_vol_60:.0f} = {vol_ratio:.1f}x 底部放量")
            else:
                reasons.append(f"量比 {vol_ratio:.1f}x < {S15_BOTTOM_VOL_VS_MA60}x 未放量")
        else:
            details["vol_ratio_5_vs_60"] = None
    else:
        details["vol_ratio_5_vs_60"] = None

    # ── 条件四：不再创新低 ──
    low_pass = False
    if n >= 10:
        low_10_min = min(lows[-10:])
        low_20_min = min(lows[-20:]) if n >= 20 else low_10_min
        details["low_10_min"] = low_10_min
        details["low_20_min"] = low_20_min
        # 近10日最低价 >= 20日最低价 x 容差
        if low_10_min >= low_20_min * S15_LOW_STABILIZE_TOL:
            low_pass = True
            reasons.append(f"近10日低点 {low_10_min:.2f} 接近20日低点 {low_20_min:.2f} 止跌企稳")
        else:
            reasons.append(f"仍在创新低: {low_10_min:.2f} < {low_20_min:.2f}")
    else:
        details["low_10_min"] = None

    # ── 条件五：资金面辅助 ──
    # money_flow 兼容两种真实数据形态：
    # 1. list[dict]：主流程 fetch_stock_money_flow 的逐日资金流（含 main_net_inflow），
    #    在此自行统计从最新日起连续主力净流入的天数；
    # 2. dict：含 continuous_inflow 子字典（days 字段）或 is_continuous/consecutive_days 字段。
    flow_pass = False
    consecutive_days = 0
    if isinstance(money_flow, list):
        for flow in money_flow:
            if flow.get("main_net_inflow", 0) > 0:
                consecutive_days += 1
            else:
                break
    elif isinstance(money_flow, dict):
        ci = money_flow.get("continuous_inflow")
        if isinstance(ci, dict):
            consecutive_days = ci.get("days", 0) or 0
        elif money_flow.get("is_continuous") is True:
            consecutive_days = money_flow.get("consecutive_days", 0) or 0
    details["consecutive_inflow_days"] = consecutive_days
    details["flow_days_threshold"] = S15_FLOW_DAYS_MIN
    if consecutive_days >= S15_FLOW_DAYS_MIN:
        flow_pass = True
        reasons.append(f"连续{consecutive_days}日主力净流入")
    details["fund_flow_confirm"] = flow_pass

    details["conditions"] = {
        "decline_pass": decline_pass,
        "amp_pass": amp_pass,
        "vol_pass": vol_pass,
        "low_pass": low_pass,
        "flow_pass": flow_pass,
    }

    if decline_pass:
        score += 0.3
    if amp_pass:
        score += 0.25
    if vol_pass:
        score += 0.2
    if low_pass:
        score += 0.15
    if flow_pass:
        score += 0.1

    return make_result(
        code="s15", name="长期蓄力",
        passed=decline_pass and amp_pass,  # 低位+横盘为核心
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s12_long_consolidation"]
