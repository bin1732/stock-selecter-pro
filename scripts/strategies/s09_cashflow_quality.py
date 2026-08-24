"""S12 现金流质量策略

判定逻辑：
基于公开财务摘要数据 + 技术面代理，综合判断企业财务与股价质量：
- 核心通过条件：ROE >= 配置下限 + 价格在配置周期均线上方（财务质地 + 技术趋势确认）
- 辅助加分条件（仅影响评分与详情，不参与通过判定）：
  - 净利率 > 配置下限（基本面）
  - 资产负债率 < 配置上限（基本面）
  - 近5日阳线天数 >= 配置下限（技术面辅助）

注：股东户数与完整现金流数据（经营现金流/自由现金流）依赖付费接口，
本策略使用上述公开可获取指标作为代理，不虚构现金流字段。

数据源：日K线 + 东方财富公开财务API。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional
from .base import make_result, clean_klines
from indicators import calc_sma
import config  # noqa: F401

S12_ROE_MIN = getattr(config, "S12_ROE_MIN", 5.0)                    # ROE最低要求(%)
S12_NET_PROFIT_RATE_MIN = getattr(config, "S12_NET_PROFIT_RATE_MIN", 3.0)  # 净利率下限(%)
S12_DEBT_RATIO_MAX = getattr(config, "S12_DEBT_RATIO_MAX", 70.0)     # 资产负债率上限(%)
S12_MA_PERIOD = getattr(config, "S12_MA_PERIOD", 20)                 # 均线周期
S12_YANG_DAYS_MIN = getattr(config, "S12_YANG_DAYS_MIN", 3)          # 近5日阳线天数下限


def check_s12_cashflow_quality(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S12 现金流质量策略判定。

    Args:
        klines: 日K线列表
        fundamental: 基本面数据字典，含 roe/net_profit_rate/revenue_growth/debt_ratio
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
            code="S12", name="现金流质量",
            passed=False,
            score=0,
            reasons=[f"K线数据不足（{len(klines) if klines else 0}条，需≥30）"],
            details={},
        )

    closes = [k["close"] for k in klines]

    # ── 使用基本面数据 ──
    has_fundamental = bool(fundamental and (
        fundamental.get("roe") is not None or fundamental.get("net_profit_rate") is not None
    ))
    details["has_fundamental"] = has_fundamental

    roe = None
    net_profit_rate = None
    debt_ratio = None
    if fundamental:
        roe = fundamental.get("roe")
        net_profit_rate = fundamental.get("net_profit_rate")
        debt_ratio = fundamental.get("debt_ratio")

    # ── 条件一：ROE达标（基本面） ──
    roe_pass = False
    if roe is not None:
        details["roe"] = roe
        details["roe_threshold"] = S12_ROE_MIN
        if roe >= S12_ROE_MIN:
            roe_pass = True
            reasons.append(f"ROE {roe:.2f}% >= {S12_ROE_MIN}%")
        else:
            reasons.append(f"ROE {roe:.2f}% < {S12_ROE_MIN}% 盈利能力不足")
    else:
        details["roe"] = None

    # ── 条件二：净利率合理（基本面） ──
    npr_pass = False
    if net_profit_rate is not None:
        details["net_profit_rate"] = net_profit_rate
        if net_profit_rate > S12_NET_PROFIT_RATE_MIN:
            npr_pass = True
            reasons.append(f"净利率 {net_profit_rate:.2f}% 正常")
        else:
            reasons.append(f"净利率 {net_profit_rate:.2f}% 偏低")
    else:
        details["net_profit_rate"] = None

    # ── 条件三：资产负债率合理 ──
    debt_pass = False
    if debt_ratio is not None:
        details["debt_ratio"] = debt_ratio
        if debt_ratio < S12_DEBT_RATIO_MAX:
            debt_pass = True
            reasons.append(f"资产负债率 {debt_ratio:.2f}% 健康")
        else:
            reasons.append(f"资产负债率 {debt_ratio:.2f}% 偏高")
    else:
        details["debt_ratio"] = None

    # ── 条件四：技术面验证 ──
    # 价格在均线上方
    tech_pass = False
    ma_vals = calc_sma(closes, S12_MA_PERIOD)
    if ma_vals and len(ma_vals) > 0:
        ma20 = ma_vals[-1]
        latest_close = closes[-1]
        details["ma20"] = round(ma20, 2)
        details["close"] = round(latest_close, 2)
        if latest_close > ma20:
            tech_pass = True
            reasons.append(f"价格 {latest_close:.2f} > MA20 {ma20:.2f}")
        else:
            reasons.append(f"价格 {latest_close:.2f} <= MA20 {ma20:.2f}")
    else:
        details["ma20"] = None

    # ── 近5日阳线占比 ──
    yang_count = 0
    for k in klines[-5:]:
        if k["close"] >= k["open"]:
            yang_count += 1
    details["yang_ratio_5"] = yang_count / 5

    details["conditions"] = {
        "roe_pass": roe_pass,
        "npr_pass": npr_pass,
        "debt_pass": debt_pass,
        "tech_pass": tech_pass,
        "yang_pass": yang_count >= S12_YANG_DAYS_MIN,
    }

    if roe_pass:
        score += 0.35
    if npr_pass:
        score += 0.2
    if debt_pass:
        score += 0.15
    if tech_pass:
        score += 0.15
    if yang_count >= S12_YANG_DAYS_MIN:
        score += 0.15

    return make_result(
        code="S12", name="现金流质量",
        passed=roe_pass and tech_pass,  # 基本面+技术面同时满足
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s12_cashflow_quality"]
