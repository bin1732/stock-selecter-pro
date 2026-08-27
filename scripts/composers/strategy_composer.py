"""策略组合引擎。

支持三种组合模式：
- union:        并集 — 任一策略通过即纳入
- intersection: 交集 — 所有指定策略均通过才纳入
- weighted:     加权 — 按策略权重计算加权总分

数据源：所有策略均基于东方财富公开行情API，纯数学运算，可审计复现。
"""

from typing import Optional
from strategies import get_strategy


def compose(
    strategy_ids: list[str],
    klines: list[dict],
    fundamental: Optional[dict] = None,
    money_flow: Optional[dict] = None,
    weekly_klines: Optional[list[dict]] = None,
    mode: str = "weighted",
    weights: Optional[dict[str, float]] = None,
):
    """策略组合判定入口。

    Args:
        strategy_ids: 策略编号列表，如 ['S01', 'S05', 'S07']
        klines: 日K线数据
        fundamental: 基本面数据字典（可选）
        money_flow: 资金流数据字典（可选）
        weekly_klines: 周K线数据（可选，用于多周期验证）
        mode: 组合模式 'union' / 'intersection' / 'weighted'
        weights: 自定义权重 dict，如 {'S01': 0.3, 'S05': 0.5, 'S07': 0.2}

    Returns:
        dict: {
            passed: bool,           # 组合结果是否通过
            score: float,           # 综合得分 0-10
            strategy_results: list, # 各策略独立结果列表
            hit_count: int,         # 命中策略数
            consensus_level: str,   # 共识度 '高共识'/'中共识'/'低共识'
            details: list[str],     # 综合判定详情
            weekly_confirm: dict,   # 周线确认结果（启用多周期且数据充足时存在）
        }
    """
    fundamental = fundamental or {}
    money_flow = money_flow or {}
    weights = weights or {}

    strategy_results = []
    for sid in strategy_ids:
        entry = get_strategy(sid)
        if entry is None:
            continue
        result = _call_with_compatible_args(
            entry["func"],
            klines=klines,
            fundamental=fundamental,
            money_flow=money_flow,
        )
        strategy_results.append({
            "id": sid,
            "name": entry["name"],
            "result": result,
        })

    evaluated = _evaluate(strategy_results, mode, weights)

    # 多周期验证：仅当调用方显式传入周K线且数据足够时执行周线趋势确认，
    # 未启用多周期（weekly_klines 为空）时保持纯日线判定，结果不受影响。
    weekly_confirm = None
    if weekly_klines:
        weekly_confirm = _weekly_confirm(weekly_klines)
        if weekly_confirm:
            if not weekly_confirm["confirmed"]:
                # 周线趋势未确认：综合得分乘以 0.85 的谨慎系数；
                # 仅在加权模式下按得分阈值收紧通过判定，
                # union/intersection 的通过语义（任一/全部通过）不受得分否决
                evaluated["score"] = round(evaluated["score"] * 0.85, 2)
                if mode == "weighted":
                    evaluated["passed"] = evaluated["score"] >= 3.0 and evaluated["passed"]
            evaluated["details"].append(
                f"周线确认: {weekly_confirm['reason']}"
            )
            evaluated["weekly_confirm"] = weekly_confirm

    return evaluated


def _weekly_confirm(weekly_klines: list[dict]) -> Optional[dict]:
    """周线趋势确认：最新周线收盘站上近10周均线视为多周期确认。

    Args:
        weekly_klines: 周K线数据（需≥15条以保证均线计算有效）

    Returns:
        dict: {confirmed, latest_close, ma10, bars, reason}；
              数据不足时返回 None（不确认也不否定）。
    """
    if not weekly_klines or len(weekly_klines) < 15:
        return None
    closes = [k["close"] for k in weekly_klines]
    ma10 = sum(closes[-10:]) / 10.0
    confirmed = closes[-1] > ma10
    return {
        "confirmed": confirmed,
        "latest_close": round(closes[-1], 2),
        "ma10": round(ma10, 2),
        "bars": len(weekly_klines),
        "reason": (
            f"周线收盘{closes[-1]:.2f} > 周线MA10({ma10:.2f})"
            if confirmed else
            f"周线收盘{closes[-1]:.2f} <= 周线MA10({ma10:.2f})"
        ),
    }


def _call_with_compatible_args(func, **kwargs):
    """以兼容方式调用策略函数，适配不同参数签名。"""
    import inspect

    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return func(**kwargs)

    filtered = {}
    for name, param in sig.parameters.items():
        if name in kwargs:
            filtered[name] = kwargs[name]
    return func(**filtered)


def _evaluate(
    strategy_results: list[dict],
    mode: str,
    weights: dict[str, float],
) -> dict:
    """根据模式评估组合结果。"""
    if not strategy_results:
        return {
            "passed": False,
            "score": 0.0,
            "strategy_results": [],
            "hit_count": 0,
            "consensus_level": "低共识",
            "details": ["无有效策略结果"],
        }

    passed_results = [
        r for r in strategy_results if r["result"].get("passed", False)
    ]
    hit_count = len(passed_results)
    total = len(strategy_results)

    # 共识度
    if hit_count >= 3:
        consensus = "高共识"
    elif hit_count >= 2:
        consensus = "中共识"
    else:
        consensus = "低共识"

    details = [f"总策略数: {total}, 通过: {hit_count}"]

    if mode == "intersection":
        passed = hit_count == total
        score = hit_count / total * 10.0 if total > 0 else 0
        details.append(f"交集模式: {'通过' if passed else '未通过'} ({hit_count}/{total})")

    elif mode == "union":
        passed = hit_count > 0
        score = hit_count / total * 10.0 if total > 0 else 0
        details.append(f"并集模式: {'通过' if passed else '未通过'} (命中{hit_count}个)")

    else:  # weighted
        total_weight = 0.0
        weighted_score = 0.0
        for r in strategy_results:
            sid = r["id"]
            # 显式判断键是否存在：权重传 0 也如实按 0 处理（不参与加权），
            # 未配置的权重按等权兜底
            w = weights[sid] if sid in weights else 1.0 / total
            s = r["result"].get("score", 0)
            if isinstance(s, (int, float)):
                weighted_score += s * w
            total_weight += w

        if total_weight > 0:
            score = weighted_score / total_weight * 10.0
        else:
            score = 0.0

        # 加权通过口径：需"综合得分达标"且"至少一个策略真实通过核心条件"，
        # 避免仅靠辅助加分（如 PE/PB/振幅等非核心条件）的标的入选。
        passed = score >= 3.0 and hit_count >= 1
        details.append(
            f"加权模式: 综合得分 {score:.1f}/10.0, 命中策略 {hit_count} 个, "
            f"{'通过' if passed else '未通过（无策略真实通过或得分不足）'}"
        )

        if weights:
            details.append(f"自定义权重: {weights}")

    details.append(f"共识度: {consensus}")

    return {
        "passed": passed,
        "score": round(score, 2),
        "strategy_results": strategy_results,
        "hit_count": hit_count,
        "consensus_level": consensus,
        "details": details,
    }


__all__ = ["compose"]
