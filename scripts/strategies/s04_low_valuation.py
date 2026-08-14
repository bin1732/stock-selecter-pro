"""S04 低估值策略 (S07)

算法核心（v1.0.1 实际实现）：
- PE_TTM <= 配置绝对上限（硬顶防范值陷阱）
- PB <= 配置上限
- ROE >= 配置下限（防价值陷阱）
- 净利率 > 配置下限（辅助判断）

数据源：东方财富公开估值API（push2.eastmoney.com）及财务摘要接口。
"""

from typing import Optional
from .base import make_result
import config  # noqa: F401

S07_PE_MAX = config.S07_PE_MAX                          # PE绝对上限
S07_PB_MAX = getattr(config, "S07_PB_MAX", 2.0)         # PB上限
S07_ROE_MIN = getattr(config, "S07_ROE_MIN", 8.0)       # ROE最低要求(%)
S07_NET_PROFIT_RATE_MIN = getattr(config, "S07_NET_PROFIT_RATE_MIN", 5.0)  # 净利率下限(%)


def check_s04_low_valuation(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S04 低估值策略判定。

    Args:
        klines: 日K线列表
        fundamental: 基本面数据字典，含 pe_ttm/pb/roe/profit_gross/net_profit_rate
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    pe_ttm = None
    pb = None
    roe = None
    net_profit_rate = None

    if fundamental:
        pe_ttm = fundamental.get("pe_ttm")
        pb = fundamental.get("pb")
        roe = fundamental.get("roe")
        net_profit_rate = fundamental.get("net_profit_rate")

    # ── 条件一：PE 低于预设阈值 ──
    pe_pass = False
    if pe_ttm is not None and pe_ttm > 0:
        details["pe_ttm"] = pe_ttm
        pe_threshold = S07_PE_MAX
        details["pe_threshold"] = pe_threshold
        if pe_ttm <= pe_threshold:
            pe_pass = True
            reasons.append(f"PE_TTM {pe_ttm:.1f} <= {pe_threshold}")
        else:
            reasons.append(f"PE_TTM {pe_ttm:.1f} > {pe_threshold} 不满足低估值")
    else:
        details["pe_ttm"] = None

    # ── 条件二：PB 低于上限 ──
    pb_pass = False
    if pb is not None and pb > 0:
        details["pb"] = pb
        details["pb_threshold"] = S07_PB_MAX
        if pb <= S07_PB_MAX:
            pb_pass = True
            reasons.append(f"PB {pb:.2f} <= {S07_PB_MAX}")
        else:
            reasons.append(f"PB {pb:.2f} > {S07_PB_MAX} 偏高")
    else:
        details["pb"] = None

    # ── 条件三：ROE 达标（防价值陷阱） ──
    roe_pass = False
    if roe is not None:
        details["roe"] = roe
        details["roe_threshold"] = S07_ROE_MIN
        if roe >= S07_ROE_MIN:
            roe_pass = True
            reasons.append(f"ROE {roe:.2f}% >= {S07_ROE_MIN}%")
        else:
            reasons.append(f"ROE {roe:.2f}% < {S07_ROE_MIN}% 盈利能力弱")
    else:
        details["roe"] = None

    # ── 条件四：净利率辅助判断 ──
    npr_pass = False
    if net_profit_rate is not None:
        details["net_profit_rate"] = net_profit_rate
        if net_profit_rate > S07_NET_PROFIT_RATE_MIN:
            npr_pass = True
    else:
        details["net_profit_rate"] = None

    # ── 综合评分 ──
    if pe_pass:
        score += 0.4
    if pb_pass:
        score += 0.25
    if roe_pass:
        score += 0.25
    if npr_pass:
        score += 0.1

    details["conditions"] = {
        "pe_pass": pe_pass,
        "pb_pass": pb_pass,
        "roe_pass": roe_pass,
        "npr_pass": npr_pass,
    }

    if not reasons:
        reasons.append("缺少估值数据（PE/PB/ROE 均无），无法完成低估值判定（如实不通过）")

    return make_result(
        code="s07", name="低估值策略",
        passed=pe_pass and pb_pass,  # PE+PB 同时满足才算核心通过
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s04_low_valuation"]
