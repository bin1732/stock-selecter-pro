"""
stock-selecter-pro v1.0.4 档案报告生成器。

提供两个函数：
- text_archive_report: 生成纯文本档案报告
- json_archive_report: 生成 JSON 格式档案报告
"""

import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

try:
    from strategies import STRATEGY_REGISTRY
except ImportError:
    STRATEGY_REGISTRY = {}

_RISK_DISCLAIMER = (
    "以上为策略历史表现统计，不构成投资建议。过往表现不代表未来收益。"
)


def text_archive_report(db_path: str) -> str:
    """生成纯文本档案报告。

    包含：策略表现排名表、近10次筛选摘要、最佳/最差策略、数据覆盖统计。
    """
    db_abs = os.path.abspath(db_path)
    lines = []

    lines.append("=" * 70)
    lines.append(f"  stock-selecter-pro {config.VERSION}  策略表现档案报告")
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)

    if not os.path.exists(db_abs):
        lines.append("")
        lines.append("  [无数据] 档案数据库尚未创建。请先执行至少一次 --track 筛选。")
        lines.append("")
        lines.append("-" * 70)
        lines.append(_RISK_DISCLAIMER)
        return "\n".join(lines)

    conn = sqlite3.connect(db_abs)
    conn.row_factory = sqlite3.Row

    # ── 策略表现排名 ──
    stats_rows = conn.execute(
        "SELECT * FROM strategy_stats ORDER BY win_rate_1m DESC"
    ).fetchall()

    lines.append("")
    lines.append("  【策略表现排名】")
    lines.append("  " + "-" * 78)
    if stats_rows:
        header = (
            f"  {'策略ID':8s} {'策略名':14s} {'执行次数':>6s} "
            f"{'入选数':>6s} {'1周胜率':>8s} {'1月胜率':>8s} "
            f"{'均分':>6s} {'最佳标的':>12s}"
        )
        lines.append(header)
        lines.append("  " + "-" * 78)
        for r in stats_rows:
            sid = r["strategy_id"]
            reg = STRATEGY_REGISTRY.get(sid, {})
            sname = reg.get("name", sid)[:14]
            wr1w = f"{r['win_rate_1w']*100:.1f}%" if r["win_rate_1w"] is not None else "N/A"
            wr1m = f"{r['win_rate_1m']*100:.1f}%" if r["win_rate_1m"] is not None else "N/A"
            avg_s = f"{r['avg_score']:.1f}" if r["avg_score"] is not None else "N/A"
            best = (r["best_pick_code"] or "")[:12]
            lines.append(
                f"  {sid:8s} {sname:14s} {r['total_runs']:>6d} "
                f"{r['total_picks']:>6d} {wr1w:>8s} {wr1m:>8s} "
                f"{avg_s:>6s} {best:>12s}"
            )
    else:
        lines.append("  (暂无统计数据)")
    lines.append("  " + "-" * 78)

    # ── 近10次筛选摘要 ──
    recent_runs = conn.execute(
        "SELECT run_id, timestamp, market, mode, candidate_count, "
        "passed_count, top5_codes "
        "FROM screening_log ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()

    lines.append("")
    lines.append("  【近10次筛选摘要】")
    lines.append("  " + "-" * 65)
    if recent_runs:
        for r in recent_runs:
            ts = r["timestamp"][:16]
            lines.append(
                f"  {ts} | {r['market']} | {r['mode']} | "
                f"候选{r['candidate_count']} -> 通过{r['passed_count']}"
            )
            if r["top5_codes"]:
                lines.append(f"    TOP5: {r['top5_codes']}")
    else:
        lines.append("  (暂无筛选记录)")
    lines.append("  " + "-" * 65)

    # ── 最佳/最差策略 ──
    lines.append("")
    lines.append("  【最佳/最差策略（按1月胜率）】")
    if stats_rows:
        best = stats_rows[0]
        worst = stats_rows[-1]
        best_name = STRATEGY_REGISTRY.get(
            best["strategy_id"], {}
        ).get("name", best["strategy_id"])
        worst_name = STRATEGY_REGISTRY.get(
            worst["strategy_id"], {}
        ).get("name", worst["strategy_id"])
        wr_best = f"{best['win_rate_1m']*100:.1f}%" if best["win_rate_1m"] is not None else "N/A"
        wr_worst = f"{worst['win_rate_1m']*100:.1f}%" if worst["win_rate_1m"] is not None else "N/A"
        lines.append(
            f"  最佳: {best['strategy_id']} {best_name}  "
            f"1月胜率: {wr_best} (运行 {best['total_runs']} 次)"
        )
        lines.append(
            f"  最差: {worst['strategy_id']} {worst_name}  "
            f"1月胜率: {wr_worst} (运行 {worst['total_runs']} 次)"
        )
    else:
        lines.append("  (暂无统计数据)")

    # ── 数据覆盖统计 ──
    lines.append("")
    lines.append("  【数据覆盖统计】")
    total_runs = conn.execute(
        "SELECT COUNT(*) FROM screening_log"
    ).fetchone()[0]
    total_picks = conn.execute(
        "SELECT COUNT(*) FROM pick_performance"
    ).fetchone()[0]
    with_1w = conn.execute(
        "SELECT COUNT(*) FROM pick_performance WHERE return_1w IS NOT NULL"
    ).fetchone()[0]
    with_1m = conn.execute(
        "SELECT COUNT(*) FROM pick_performance WHERE return_1m IS NOT NULL"
    ).fetchone()[0]
    lines.append(f"  历史筛选总次数: {total_runs}")
    lines.append(f"  累计入选标的数: {total_picks}")
    lines.append(f"  已有1周收益数据: {with_1w}")
    lines.append(f"  已有1月收益数据: {with_1m}")

    conn.close()

    lines.append("")
    lines.append("-" * 70)
    lines.append(_RISK_DISCLAIMER)

    return "\n".join(lines)


def json_archive_report(db_path: str) -> dict:
    """生成 JSON 格式档案报告。

    包含 screening_summary、strategy_ranking、recent_runs。
    """
    db_abs = os.path.abspath(db_path)
    report = {
        "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": config.VERSION,
        "disclaimer": _RISK_DISCLAIMER,
        "screening_summary": {},
        "strategy_ranking": [],
        "recent_runs": [],
    }

    if not os.path.exists(db_abs):
        report["screening_summary"] = {"status": "no_data", "total_runs": 0}
        return report

    conn = sqlite3.connect(db_abs)
    conn.row_factory = sqlite3.Row

    total_runs = conn.execute(
        "SELECT COUNT(*) FROM screening_log"
    ).fetchone()[0]
    total_picks = conn.execute(
        "SELECT COUNT(*) FROM pick_performance"
    ).fetchone()[0]
    with_1w = conn.execute(
        "SELECT COUNT(*) FROM pick_performance WHERE return_1w IS NOT NULL"
    ).fetchone()[0]
    with_1m = conn.execute(
        "SELECT COUNT(*) FROM pick_performance WHERE return_1m IS NOT NULL"
    ).fetchone()[0]
    report["screening_summary"] = {
        "total_runs": total_runs,
        "total_picks": total_picks,
        "with_1w_return": with_1w,
        "with_1m_return": with_1m,
    }

    stat_rows = conn.execute(
        "SELECT strategy_id, total_runs, total_picks, avg_score, "
        "avg_1w_return, avg_1m_return, win_rate_1w, win_rate_1m, "
        "best_pick_code, best_pick_return, last_updated "
        "FROM strategy_stats ORDER BY win_rate_1m DESC"
    ).fetchall()
    for r in stat_rows:
        report["strategy_ranking"].append({
            "strategy_id": r["strategy_id"],
            "total_runs": r["total_runs"],
            "total_picks": r["total_picks"],
            "avg_score": r["avg_score"],
            "avg_1w_return": r["avg_1w_return"],
            "avg_1m_return": r["avg_1m_return"],
            "win_rate_1w": r["win_rate_1w"],
            "win_rate_1m": r["win_rate_1m"],
            "best_pick_code": r["best_pick_code"],
            "best_pick_return": r["best_pick_return"],
            "last_updated": r["last_updated"],
        })

    run_rows = conn.execute(
        "SELECT run_id, timestamp, market, strategy_ids, mode, "
        "candidate_count, passed_count, top5_codes "
        "FROM screening_log ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()
    for r in run_rows:
        report["recent_runs"].append({
            "run_id": r["run_id"],
            "timestamp": r["timestamp"],
            "market": r["market"],
            "strategy_ids": r["strategy_ids"],
            "mode": r["mode"],
            "candidate_count": r["candidate_count"],
            "passed_count": r["passed_count"],
            "top5_codes": r["top5_codes"],
        })

    conn.close()
    return report
