"""
stock-selecter-pro v1.0.4 策略表现聚合统计。

提供两个核心函数：
- refresh_strategy_stats: 从 pick_performance 聚合计算 strategy_stats
- get_strategy_ranking:   按指定指标降序返回策略排名
"""

import os
import sqlite3
from datetime import datetime


def refresh_strategy_stats(db_path: str):
    """从 pick_performance 聚合计算并更新 strategy_stats。

    使用 SQL 子查询在单次查询中完成所有聚合。
    """
    db_abs = os.path.abspath(db_path)
    if not os.path.exists(db_abs):
        return

    conn = sqlite3.connect(db_abs)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 先清空旧统计，避免策略下线后残留历史行（INSERT OR REPLACE 只覆盖不删除）
    conn.execute("DELETE FROM strategy_stats")

    conn.execute("""
        INSERT OR REPLACE INTO strategy_stats (
            strategy_id, total_runs, total_picks, avg_score,
            avg_1w_return, avg_1m_return, win_rate_1w, win_rate_1m,
            best_pick_code, best_pick_return, last_updated
        )
        SELECT
            pp.strategy_id,
            (SELECT COUNT(DISTINCT sl.run_id)
             FROM pick_performance pp2
             JOIN screening_log sl ON pp2.run_id = sl.run_id
             WHERE pp2.strategy_id = pp.strategy_id),
            COUNT(*) AS total_picks,
            ROUND(AVG(pp.score), 2) AS avg_score,
            ROUND(AVG(pp.return_1w), 2) AS avg_1w_return,
            ROUND(AVG(pp.return_1m), 2) AS avg_1m_return,
            ROUND(
                CAST(SUM(CASE WHEN pp.return_1w > 0 THEN 1 ELSE 0 END) AS REAL)
                / NULLIF(COUNT(pp.return_1w), 0), 4
            ) AS win_rate_1w,
            ROUND(
                CAST(SUM(CASE WHEN pp.return_1m > 0 THEN 1 ELSE 0 END) AS REAL)
                / NULLIF(COUNT(pp.return_1m), 0), 4
            ) AS win_rate_1m,
            (
                SELECT ppb.stock_code || ' ' || ppb.stock_name
                FROM pick_performance ppb
                WHERE ppb.strategy_id = pp.strategy_id
                  AND ppb.return_1m IS NOT NULL
                ORDER BY ppb.return_1m DESC
                LIMIT 1
            ),
            (
                SELECT MAX(ppc.return_1m)
                FROM pick_performance ppc
                WHERE ppc.strategy_id = pp.strategy_id
                  AND ppc.return_1m IS NOT NULL
            ),
            ?
        FROM pick_performance pp
        GROUP BY pp.strategy_id;
    """, (now_str,))

    conn.commit()
    conn.close()


def get_strategy_ranking(db_path: str, metric: str = "win_rate_1m") -> list:
    """按指定指标降序返回策略排名列表。

    Args:
        db_path: 数据库文件路径
        metric:  排名指标（win_rate_1m / win_rate_1w / avg_1m_return /
                 avg_1w_return / avg_score / total_picks）

    Returns:
        list[dict]: 每项含 strategy_id, metric_value, total_runs, total_picks
    """
    valid_metrics = {
        "win_rate_1m", "win_rate_1w", "avg_1m_return",
        "avg_1w_return", "avg_score", "total_picks",
    }
    if metric not in valid_metrics:
        metric = "win_rate_1m"

    db_abs = os.path.abspath(db_path)
    if not os.path.exists(db_abs):
        return []

    conn = sqlite3.connect(db_abs)
    conn.row_factory = sqlite3.Row

    sql = f"""
        SELECT strategy_id, {metric} AS metric_value, total_runs, total_picks
        FROM strategy_stats
        ORDER BY {metric} DESC
    """
    rows = conn.execute(sql).fetchall()
    conn.close()

    return [
        {
            "strategy_id": r["strategy_id"],
            "metric_value": r["metric_value"],
            "total_runs": r["total_runs"],
            "total_picks": r["total_picks"],
        }
        for r in rows
    ]


def suggest_weights(
    db_path: str,
    default_weights: dict,
    min_picks: int = 5,
) -> tuple:
    """基于档案库真实历史表现生成策略权重建议（自进化闭环，不造假）。

    数据来源：strategy_stats 表（由 pick_performance 真实聚合，见 refresh_strategy_stats）。
    真实约束（如实，不虚构）：
    - 仅 total_picks >= min_picks 的策略参与权重调整（样本充足才可信）；
      样本不足的策略**保持默认权重**，不被夸大也不被压低。
    - 指标：1月胜率 win_rate_1m（主，0.7）+ 1月平均收益 avg_1m_return（辅，0.3，
      最小-最大归一化到 0~1 以统一量纲）。指标为 NULL（无1月收益数据）时该策略
      保持默认权重（不参与调整）。
    - 参与调整的策略权重按表现分归一化，总和保持 1.0。
    - 该建议仅为**历史统计**（基于 N 次真实筛选后的表现），不代表未来收益。

    Args:
        db_path: 档案库文件路径
        default_weights: 默认权重 dict（config.STRATEGY_DEFAULT_WEIGHTS）
        min_picks: 最小入选样本数（低于该值不参与自动调整）

    Returns:
        tuple[dict, str]: (调整后权重 dict, 说明文本)
    """
    db_abs = os.path.abspath(db_path)
    weights = dict(default_weights)
    if not os.path.exists(db_abs):
        return weights, f"档案库不存在（{db_path}），保持全部默认权重"

    conn = sqlite3.connect(db_abs)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT strategy_id, win_rate_1m, avg_1m_return, total_picks "
        "FROM strategy_stats"
    ).fetchall()
    conn.close()
    if not rows:
        return weights, "档案库无策略统计（尚无 --track 历史），保持全部默认权重"

    stats = {r["strategy_id"]: dict(r) for r in rows}
    # 参与调整的策略（样本充足且指标齐全）
    eligible = {
        sid: s for sid, s in stats.items()
        if s["total_picks"] >= min_picks
        and s["win_rate_1m"] is not None
        and s["avg_1m_return"] is not None
    }
    if not eligible:
        return weights, (
            f"档案库中无样本充足（≥{min_picks}次入选）且指标齐全的策略，保持全部默认权重"
        )

    # 表现分：0.7 * 1月胜率 + 0.3 * 1月均收益（最小-最大归一化）
    returns = [s["avg_1m_return"] for s in eligible.values()]
    r_min, r_max = min(returns), max(returns)
    r_span = (r_max - r_min) or 1.0
    scores = {}
    for sid, s in eligible.items():
        norm_ret = (s["avg_1m_return"] - r_min) / r_span
        scores[sid] = 0.7 * s["win_rate_1m"] + 0.3 * norm_ret

    # 参与调整的策略：保底 20% 默认权重 + 共享"可调总池"按表现分份额分配。
    # 可调总池 = 参与策略默认权重的 80% 之和（表现差者省出的份额流向表现好者），
    # 未参与调整的策略**绝对权重保持不变**，总和精确保持 1.0，
    # 且无极端化（表现最差仍保底 20%，不会被压到 0）。
    pool = sum(default_weights.get(sid, 0.05) * 0.8 for sid in scores) or 1.0
    total_score = sum(scores.values()) or 1.0
    for sid, sc in scores.items():
        share = sc / total_score
        base = default_weights.get(sid, 0.05) * 0.2
        weights[sid] = base + pool * share

    total_picks_sum = sum(s["total_picks"] for s in eligible.values())
    kept = sorted(set(default_weights) - set(eligible))
    note = (
        f"自适应权重基于档案库 {total_picks_sum} 条真实历史表现"
        f"（{len(eligible)} 个策略：1月胜率70% + 1月均收益30%，归一化）"
    )
    if kept:
        note += f"；样本不足保持默认权重: {', '.join(kept)}"
    note += "（历史统计，不代表未来收益）"
    return weights, note
