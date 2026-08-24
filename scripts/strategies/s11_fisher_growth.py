"""S14 费雪成长股策略

算法核心：
- 营收增速 >= 配置下限（基于基本面字段 revenue_growth）
- 净利润增速 >= 配置下限（基于基本面字段 net_profit_growth）
- PEG < 配置上限（PE / 净利润增速）
- 毛利率 > 配置下限（基本面）
- 价格在配置周期均线上方 + MACD零轴上方（技术面加分）

注：本策略通过条件为营收增速与净利润增速同时达标（双增长）。缺少基本面数据时
passed 恒为 False，技术面仅作为评分加分项，不替代基本面通过判定。

数据源：日K线 + 东方财富公开财务API（fundamental.py）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result
from indicators.technical import calc_macd, calc_ma
import config  # noqa: F401

S14_REVENUE_GROWTH_MIN = getattr(config, "S14_REVENUE_GROWTH_MIN", 15.0)  # 营收增速最低(%)
S14_PROFIT_GROWTH_MIN = getattr(config, "S14_PROFIT_GROWTH_MIN", 15.0)    # 净利润增速最低(%)
S14_PEG_MAX = getattr(config, "S14_PEG_MAX", 1.5)                         # PEG上限
S14_PROFIT_GROSS_MIN = getattr(config, "S14_PROFIT_GROSS_MIN", 25.0)      # 毛利率下限(%)
S14_TECH_MA_PERIODS = getattr(config, "S14_TECH_MA_PERIODS", [20, 60])    # 技术面确认均线周期


def check_s14_fisher_growth(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S14 费雪成长股策略判定。

    Args:
        klines: 日K线列表（需≥60条）
        fundamental: 基本面数据字典，含 revenue_growth/net_profit_growth/pe_ttm/roe/profit_gross
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    if not klines or len(klines) < 60:
        return make_result(
            code="S14", name="费雪成长股",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥60）"],
            details={},
        )

    closes = [k["close"] for k in klines]

    revenue_growth = None
    profit_growth = None
    pe_ttm = None
    profit_gross = None
    if fundamental:
        revenue_growth = fundamental.get("revenue_growth")
        profit_growth = fundamental.get("net_profit_growth")
        pe_ttm = fundamental.get("pe_ttm")
        profit_gross = fundamental.get("profit_gross")

    has_fundamental = bool(fundamental and revenue_growth is not None)
    details["has_fundamental"] = has_fundamental

    # ── 条件一：营收增速 ──
    rev_pass = False
    if revenue_growth is not None:
        details["revenue_growth"] = revenue_growth
        details["revenue_growth_threshold"] = S14_REVENUE_GROWTH_MIN
        if revenue_growth >= S14_REVENUE_GROWTH_MIN:
            rev_pass = True
            reasons.append(f"营收增速 {revenue_growth:.2f}% >= {S14_REVENUE_GROWTH_MIN}%")
        else:
            reasons.append(f"营收增速 {revenue_growth:.2f}% < {S14_REVENUE_GROWTH_MIN}% 成长性不足")
    else:
        details["revenue_growth"] = None

    # ── 条件二：净利润增速 ──
    prof_pass = False
    if profit_growth is not None:
        details["net_profit_growth"] = profit_growth
        details["profit_growth_threshold"] = S14_PROFIT_GROWTH_MIN
        if profit_growth >= S14_PROFIT_GROWTH_MIN:
            prof_pass = True
            reasons.append(f"净利润增速 {profit_growth:.2f}% >= {S14_PROFIT_GROWTH_MIN}%")
        else:
            reasons.append(f"净利润增速 {profit_growth:.2f}% < {S14_PROFIT_GROWTH_MIN}% 成长性不足")
    else:
        details["net_profit_growth"] = None

    # ── 条件三：PEG合理 ──
    peg_pass = False
    if pe_ttm is not None and pe_ttm > 0 and profit_growth is not None and profit_growth > 0:
        peg = pe_ttm / profit_growth
        details["peg"] = round(peg, 2)
        details["peg_threshold"] = S14_PEG_MAX
        if peg < S14_PEG_MAX:
            peg_pass = True
            reasons.append(f"PEG {peg:.1f} < {S14_PEG_MAX} 估值合理")
        else:
            reasons.append(f"PEG {peg:.1f} >= {S14_PEG_MAX} 估值偏高")
    else:
        details["peg"] = None

    # ── 条件四：毛利率下限 ──
    gross_pass = False
    if profit_gross is not None:
        details["profit_gross"] = profit_gross
        if profit_gross > S14_PROFIT_GROSS_MIN:
            gross_pass = True
            reasons.append(f"毛利率 {profit_gross:.2f}% 护城河宽")
    else:
        details["profit_gross"] = None

    # ── 条件五：技术面上升趋势 ──
    tech_pass = False
    ma20 = calc_ma(klines, S14_TECH_MA_PERIODS[0])
    ma60 = calc_ma(klines, S14_TECH_MA_PERIODS[1])
    if ma20 and ma60 and len(ma20) > 0 and len(ma60) > 0:
        details["close_vs_ma20"] = round(closes[-1] / ma20[-1], 3) if ma20[-1] > 0 else None
        if closes[-1] > ma20[-1] and closes[-1] > ma60[-1]:
            tech_pass = True

    # MACD在零轴上方为加分项
    macd_result = calc_macd(klines)
    macd_above_zero = False
    if macd_result and len(macd_result["dif"]) > 0:
        macd_above_zero = macd_result["dif"][-1] > 0
        details["macd_above_zero"] = macd_above_zero

    details["conditions"] = {
        "rev_pass": rev_pass,
        "prof_pass": prof_pass,
        "peg_pass": peg_pass,
        "gross_pass": gross_pass,
        "tech_pass": tech_pass,
    }

    if rev_pass:
        score += 0.25
    if prof_pass:
        score += 0.25
    if peg_pass:
        score += 0.2
    if gross_pass:
        score += 0.15
    if tech_pass:
        score += 0.1
    if macd_above_zero:
        score += 0.05

    if not reasons:
        reasons.append("缺少财务数据（营收/净利/PEG/毛利率均无），无法完成费雪成长判定（如实不通过）")

    return make_result(
        code="S14", name="费雪成长股",
        passed=rev_pass and prof_pass,  # 营收与净利润双增长才通过
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s14_fisher_growth"]
