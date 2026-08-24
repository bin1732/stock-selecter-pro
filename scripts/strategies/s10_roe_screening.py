"""S13 ROE杜邦筛选策略

算法核心：
基于公开财务摘要数据 + 技术面确认：
1. ROE >= 配置下限（核心条件）
2. 净利率 >= 配置下限（杜邦-盈利质量）
3. 资产负债率 <= 配置上限（杜邦-杠杆端）
4. 毛利率 >= 配置下限（盈利能力辅助）
5. 价格在配置周期均线上方（技术面趋势确认）

注：本策略使用公开可获取的财务摘要字段作杜邦拆解代理，
完整年报级周转率/权益乘数数据依赖付费接口，不虚构字段。

数据源：日K线 + 东方财富公开财务API（fundamental.py）。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result, clean_klines
from indicators import calc_sma
import config  # noqa: F401

S13_ROE_MIN = getattr(config, "S13_ROE_MIN", 15.0)                    # ROE最低要求(%)
S13_NET_PROFIT_RATE_MIN = getattr(config, "S13_NET_PROFIT_RATE_MIN", 8.0)  # 净利率最低(%)
S13_DEBT_RATIO_MAX = getattr(config, "S13_DEBT_RATIO_MAX", 60.0)      # 资产负债率上限(%)
S13_PROFIT_GROSS_MIN = getattr(config, "S13_PROFIT_GROSS_MIN", 20.0)  # 毛利率最低(%)
S13_TECH_MA_PERIOD = getattr(config, "S13_TECH_MA_PERIOD", 20)        # 技术面确认均线周期


def check_s13_roe_screening(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S13 ROE杜邦筛选策略判定。

    Args:
        klines: 日K线列表
        fundamental: 基本面数据字典，含 roe/net_profit_rate/debt_ratio/profit_gross
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    klines = clean_klines(klines)
    if not klines or len(klines) < 30:
        return make_result(
            code="S13", name="ROE杜邦筛选",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥30）"],
            details={},
        )

    closes = [k["close"] for k in klines]

    roe = None
    net_profit_rate = None
    debt_ratio = None
    profit_gross = None
    if fundamental:
        roe = fundamental.get("roe")
        net_profit_rate = fundamental.get("net_profit_rate")
        debt_ratio = fundamental.get("debt_ratio")
        profit_gross = fundamental.get("profit_gross")

    has_fundamental = bool(fundamental and roe is not None)
    details["has_fundamental"] = has_fundamental

    # ── 条件一：ROE 达标 ──
    roe_pass = False
    if roe is not None:
        details["roe"] = roe
        details["roe_threshold"] = S13_ROE_MIN
        if roe >= S13_ROE_MIN:
            roe_pass = True
            reasons.append(f"ROE {roe:.2f}% >= {S13_ROE_MIN}%")
        else:
            reasons.append(f"ROE {roe:.2f}% < {S13_ROE_MIN}% 不达标")
    else:
        details["roe"] = None
        reasons.append("无ROE数据，无法进行杜邦筛选")

    # ── 条件二：净利率（杜邦-盈利质量） ──
    npr_pass = False
    if net_profit_rate is not None:
        details["net_profit_rate"] = net_profit_rate
        details["net_profit_rate_threshold"] = S13_NET_PROFIT_RATE_MIN
        if net_profit_rate >= S13_NET_PROFIT_RATE_MIN:
            npr_pass = True
            reasons.append(f"净利率 {net_profit_rate:.2f}% 杜邦盈利端健康")
        else:
            reasons.append(f"净利率 {net_profit_rate:.2f}% < {S13_NET_PROFIT_RATE_MIN}% 偏低")
    else:
        details["net_profit_rate"] = None

    # ── 条件三：资产负债率（杜邦-杠杆端） ──
    debt_pass = False
    if debt_ratio is not None:
        details["debt_ratio"] = debt_ratio
        details["debt_ratio_threshold"] = S13_DEBT_RATIO_MAX
        if debt_ratio <= S13_DEBT_RATIO_MAX:
            debt_pass = True
            reasons.append(f"资产负债率 {debt_ratio:.2f}% 杜邦杠杆端健康")
        else:
            reasons.append(f"资产负债率 {debt_ratio:.2f}% > {S13_DEBT_RATIO_MAX}% 杠杆偏高")
    else:
        details["debt_ratio"] = None

    # ── 条件四：毛利率（盈利能力辅助） ──
    gross_pass = False
    if profit_gross is not None:
        details["profit_gross"] = profit_gross
        details["profit_gross_threshold"] = S13_PROFIT_GROSS_MIN
        if profit_gross >= S13_PROFIT_GROSS_MIN:
            gross_pass = True
            reasons.append(f"毛利率 {profit_gross:.2f}% >= {S13_PROFIT_GROSS_MIN}%")
        else:
            reasons.append(f"毛利率 {profit_gross:.2f}% < {S13_PROFIT_GROSS_MIN}% 偏低")
    else:
        details["profit_gross"] = None

    # ── 条件五：技术面趋势确认 ──
    tech_pass = False
    ma20 = calc_sma(closes, S13_TECH_MA_PERIOD)
    if ma20 and len(ma20) > 0:
        if closes[-1] > ma20[-1]:
            tech_pass = True

    details["conditions"] = {
        "roe_pass": roe_pass,
        "npr_pass": npr_pass,
        "debt_pass": debt_pass,
        "gross_pass": gross_pass,
        "tech_pass": tech_pass,
    }

    # 杜邦三分项评分
    if roe_pass:
        score += 0.4
    if npr_pass:
        score += 0.2     # 盈利质量
    if debt_pass:
        score += 0.15    # 杠杆健康
    if gross_pass:
        score += 0.15
    if tech_pass:
        score += 0.1

    return make_result(
        code="S13", name="ROE杜邦筛选",
        passed=roe_pass and npr_pass and debt_pass,  # 杜邦三核心
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s13_roe_screening"]
