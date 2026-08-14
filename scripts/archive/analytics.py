"""
stock-selecter-pro v1.0.1 策略表现聚合统计。

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
