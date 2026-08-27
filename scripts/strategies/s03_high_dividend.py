"""S06 高股息策略

算法核心：
- 股息率 >= 配置阈值（核心条件）
- PE <= 配置阈值（防高股息低增长陷阱）
- PB <= 配置阈值（防低PB价值陷阱）
- 近60日价格振幅 < 配置阈值（持续派息股的股价特征）

数据源：股息率取自候选池 clist 接口 f133 字段（A股/港股/美股三市场真实返回）；
PE/PB 亦取自候选池 clist f9/f23。缺失标的回退 push2 单股估值接口。
不采用 f171 字段（该字段非股息率）。
"""

from typing import Optional
from .base import make_result
import config  # noqa: F401 — 配置参数统一管理

# 若不存在对应配置项，使用硬编码默认值
S06_DIVIDEND_YIELD_MIN = getattr(config, "S06_DIVIDEND_YIELD_MIN", 3.0)   # 股息率最低要求(%)
S06_PE_MAX = getattr(config, "S06_PE_MAX", 15.0)                       # PE上限
S06_PB_MAX = getattr(config, "S06_PB_MAX", 2.0)                       # PB上限
S06_AMPLITUDE_60_MAX = getattr(config, "S06_AMPLITUDE_60_MAX", 40.0)   # 近60日最大振幅(%)


def check_s06_high_dividend(
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
) -> dict:
    """S06 高股息策略判定。

    Args:
        klines: 日K线列表（用于计算股息率估算，优先使用 fundamental）
        fundamental: 基本面数据字典，含 pe_ttm/pb/dividend_yield/total_mv
        money_flow: 资金流数据字典（本策略不使用）

    Returns:
        {score: float, reasons: list[str], details: dict}
    """
    reasons = []
    details = {}
    score = 0.0

    # ── 提取基本面数据 ──
    div_yield = None
    pe_ttm = None
    pb = None

    if fundamental:
        div_yield = fundamental.get("dividend_yield")
        pe_ttm = fundamental.get("pe_ttm")
        pb = fundamental.get("pb")

    # ── 条件一：股息率达标 ──
    div_pass = False
    if div_yield is not None and div_yield > 0:
        details["dividend_yield"] = div_yield
        details["dividend_yield_threshold"] = S06_DIVIDEND_YIELD_MIN
        if div_yield >= S06_DIVIDEND_YIELD_MIN:
            div_pass = True
            reasons.append(f"股息率 {div_yield:.2f}% >= {S06_DIVIDEND_YIELD_MIN}%")
        else:
            reasons.append(f"股息率 {div_yield:.2f}% < {S06_DIVIDEND_YIELD_MIN}% 不达标")
    else:
        reasons.append("无股息率数据，跳过")
        details["dividend_yield"] = None

    # ── 条件二：PE合理（防价值陷阱） ──
    pe_pass = False
    if pe_ttm is not None and pe_ttm > 0:
        details["pe_ttm"] = pe_ttm
        details["pe_threshold"] = S06_PE_MAX
        if pe_ttm <= S06_PE_MAX:
            pe_pass = True
        else:
            reasons.append(f"PE_TTM {pe_ttm:.1f} > {S06_PE_MAX} 偏高")
    else:
        details["pe_ttm"] = None

    # ── 条件三：PB合理（防低PB价值陷阱） ──
    pb_pass = False
    if pb is not None and pb > 0:
        details["pb"] = pb
        details["pb_threshold"] = S06_PB_MAX
        if pb <= S06_PB_MAX:
            pb_pass = True
        else:
            reasons.append(f"PB {pb:.2f} > {S06_PB_MAX} 偏高")
    else:
        details["pb"] = None

    # ── 条件四：历史K线近端价格稳定（持续派息股的股价特征） ──
    price_stable_pass = False
    if klines and len(klines) >= 60:
        # 近60日振幅不超过40%
        closes = [k["close"] for k in klines[-60:]]
        max_close = max(closes)
        min_close = min(closes)
        if min_close > 0:
            amplitude_60 = (max_close - min_close) / min_close * 100
            details["price_amplitude_60"] = round(amplitude_60, 2)
            if amplitude_60 < S06_AMPLITUDE_60_MAX:
                price_stable_pass = True
            else:
                reasons.append(f"近60日振幅 {amplitude_60:.1f}% 过大，波动较高")
    else:
        details["price_amplitude_60"] = None

    # ── 综合评分 ──
    if div_pass:
        score += 0.5
    if pe_pass:
        score += 0.2
    if pb_pass:
        score += 0.15
    if price_stable_pass:
        score += 0.15

    details["conditions"] = {
        "dividend_yield_pass": div_pass,
        "pe_pass": pe_pass,
        "pb_pass": pb_pass,
        "price_stable_pass": price_stable_pass,
    }

    return make_result(
        code="S06", name="高股息策略",
        passed=div_pass,  # 核心条件是股息率，其余为辅助
        score=score,
        reasons=reasons,
        details=details,
    )


__all__ = ["check_s06_high_dividend"]
