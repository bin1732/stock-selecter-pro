"""历史回放回测模块（真实K线信号回放，非虚构）。

核心思路（无前视偏差、复用真实策略判定函数）：
- 对给定K线，从 `BACKTEST_WINDOW` 处开始，每一根K线作为"信号日"
- 信号日窗口 = 该日及之前 `BACKTEST_WINDOW` 根K线（只使用历史数据，无前视偏差）
- 调用 `STRATEGY_REGISTRY` 中的真实策略判定函数判断该日是否触发信号
- 持有期收益 = 信号日后第 `hold_days` 个交易日收盘 / 信号日收盘 - 1
- 统计：信号次数、胜率（收益>0占比）、平均收益、最好/最差单次收益

合规声明（强制执行）：
- 仅基于当前仍在交易标的的历史K线回放，存在幸存者偏差
- 样本有限，胜率/收益为历史统计，不代表未来收益
- 不构成投资建议，不构成收益承诺
"""

from typing import Optional

import config
from strategies import STRATEGY_REGISTRY


def _scan_signal_days(
    func,
    klines: list[dict],
    fundamental: Optional[dict],
    money_flow: Optional[dict],
    window: int,
) -> list[int]:
    """逐日滑动窗口扫描信号日索引（信号日窗口只用历史数据，无前视偏差）。"""
    signal_days = []
    for i in range(window - 1, len(klines)):
        window_klines = klines[i - window + 1: i + 1]
        try:
            res = func(klines=window_klines, fundamental=fundamental, money_flow=money_flow)
        except Exception:
            continue
        if res and res.get("passed"):
            signal_days.append(i)
    return signal_days


def _hold_returns(klines: list[dict], signal_days: list[int], hold: int) -> list[float]:
    """计算每个信号日持有 hold 个交易日后的收益列表（%）。"""
    returns = []
    for i in signal_days:
        exit_idx = i + hold
        if exit_idx >= len(klines):
            continue
        entry_close = klines[i]["close"]
        if not entry_close:
            continue
        exit_close = klines[exit_idx]["close"]
        if not exit_close:
            continue
        returns.append(round(exit_close / entry_close - 1, 4))
    return returns


def collect_signal_returns(
    strategy_id: str,
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
    window: Optional[int] = None,
    hold_days: tuple = (5, 20),
) -> dict:
    """收集单只标的所有信号日的持有期收益列表（供市场级合并统计真实胜率）。

    Returns:
        dict: {"samples": int, hold: [收益...], "note": str}
    """
    entry = STRATEGY_REGISTRY.get(strategy_id)
    result = {"samples": 0, "note": ""}
    if entry is None or not klines:
        result["note"] = "策略不存在或K线为空"
        return result

    window = window or config.BACKTEST_WINDOW
    signal_days = _scan_signal_days(entry["func"], klines, fundamental, money_flow, window)
    result["samples"] = len(signal_days)
    for hold in hold_days:
        rets = _hold_returns(klines, signal_days, hold)
        if rets:
            result[hold] = rets
    return result
