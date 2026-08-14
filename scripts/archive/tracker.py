"""
stock-selecter-pro v1.0.1 筛选结果追踪器。

提供两个核心函数：
- log_screening:      将每次筛选执行的快照写入数据库
- refresh_performance: 通过东方财富日K线API回填持仓收益
"""

import os
import sys
import time
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from .schema import init_db

# 东财历史K线共享客户端（多编号节点故障切换）
from data._http import kline_get

# 复用东方财富标准UA
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
})

# 东方财富日K线 API（多编号节点故障切换，见 data/_http.py）
_KLINE_URL = "/api/qt/stock/kline/get"


def _kline_url_params(stock_code: str) -> Optional[dict]:
    """根据股票代码生成东方财富日K线请求参数。"""
    code = stock_code.strip()
    if not code:
        return None
    if code.startswith("6") or code.startswith("9"):
        secid = f"1.{code}"
    elif code.startswith("0") or code.startswith("3") or code.startswith("2"):
        secid = f"0.{code}"
    else:
        secid = f"1.{code}"

    return {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "end": "20500101",
        "lmt": "30",
    }


def _fetch_latest_close(stock_code: str) -> Optional[float]:
    """通过东方财富日K线API获取最新收盘价。"""
    params = _kline_url_params(stock_code)
    if params is None:
        return None
    try:
        data = kline_get(_KLINE_URL, params=params)
        if data and data.get("data") and data["data"].get("klines"):
            klines = data["data"]["klines"]
            # 格式: "日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率"
            last_line = klines[-1]
            parts = last_line.split(",")
            if len(parts) >= 3:
                return float(parts[2])
    except Exception:
        pass
    return None


def log_screening(
    db_path: str,
    run_id: str,
    market: str,
    strategy_ids: list,
    mode: str,
    candidate_count: int,
    passed_count: int,
    results: list,
):
    """将一次筛选执行的快照写入 screening_log 和 pick_performance。

    Args:
        db_path:   数据库文件路径
        run_id:    本次运行的唯一ID
        market:    市场
        strategy_ids: 启用的策略ID列表
        mode:      筛选模式
        candidate_count: 候选池数量
        passed_count:    最终通过数量
        results:   compose() 返回的 final_results 列表
    """
    db_abs = init_db(db_path)

    conn = sqlite3.connect(db_abs)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_date = datetime.now().strftime("%Y-%m-%d")

    # 写入 screening_log
    top5_codes = ",".join([r.get("code", "") for r in results[:5]])
    conn.execute(
        "INSERT OR REPLACE INTO screening_log(run_id, timestamp, market, strategy_ids, "
        "mode, candidate_count, passed_count, top5_codes) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, timestamp, market,
            ",".join(strategy_ids), mode,
            candidate_count, passed_count, top5_codes,
        ),
    )

    # 写入 pick_performance
    for r in results:
        stock_code = r.get("code", "")
        stock_name = r.get("name", "")
        score = r.get("composite_score", 0)
        strategy_hits = r.get("strategy_hits", [])
        strategy_results = r.get("strategy_results", {})

        # 获取快照价格：优先策略详情中的收盘价，回退到主流程附带的当日收盘价
        snapshot_price = 0.0
        for sid, sresult in strategy_results.items():
            details = sresult.get("details", {})
            if isinstance(details, dict):
                if "latest_close" in details:
                    snapshot_price = float(details["latest_close"])
                    break
                elif "close" in details:
                    snapshot_price = float(details["close"])
                    break
        if snapshot_price <= 0:
            snapshot_price = float(r.get("latest_close") or 0)

        for sid in strategy_hits:
            sresult = strategy_results.get(sid, {})
            strategy_score = sresult.get("score", 0)
            conn.execute(
                "INSERT INTO pick_performance(run_id, stock_code, stock_name, "
                "strategy_id, score, snapshot_price, snapshot_date) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (run_id, stock_code, stock_name, sid, strategy_score,
                 snapshot_price, snapshot_date),
            )

    conn.commit()
    conn.close()


def refresh_performance(db_path: str) -> dict:
    """遍历 pick_performance 中 return_1w 为 NULL 的记录，
    通过东方财富日K线API获取最新收盘价并计算收益率回填。

    Returns:
        dict: {"checked": N, "updated_1w": N, "updated_1m": N, "failed": N}
    """
    db_abs = os.path.abspath(db_path)
    if not os.path.exists(db_abs):
        return {"checked": 0, "updated_1w": 0, "updated_1m": 0, "failed": 0}

    conn = sqlite3.connect(db_abs)
    conn.row_factory = sqlite3.Row

    cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT pick_id, stock_code, snapshot_price, snapshot_date "
        "FROM pick_performance "
        "WHERE return_1w IS NULL AND snapshot_date <= ?",
        (cutoff_date,),
    ).fetchall()

    interval = getattr(config, "ARCHIVE_REFRESH_INTERVAL", 0.3)
    checked = len(rows)
    updated_1w = 0
    updated_1m = 0
    failed = 0

    check_date = datetime.now().strftime("%Y-%m-%d")

    # 按股票去重，同一只股票只请求一次API
    stock_prices = {}
    for row in rows:
        code = row["stock_code"]
        if code not in stock_prices:
            price = _fetch_latest_close(code)
            stock_prices[code] = price
            time.sleep(interval)

    for row in rows:
        pick_id = row["pick_id"]
        code = row["stock_code"]
        snapshot_price = row["snapshot_price"]
        snapshot_date = row["snapshot_date"]

        latest_price = stock_prices.get(code)
        if latest_price is None or snapshot_price is None or snapshot_price <= 0:
            failed += 1
            continue

        return_1w = round((latest_price - snapshot_price) / snapshot_price * 100, 2)

        snapshot_dt = datetime.strptime(snapshot_date, "%Y-%m-%d")
        days_diff = (datetime.now() - snapshot_dt).days

        if days_diff >= 28:
            conn.execute(
                "UPDATE pick_performance SET check_date_1w=?, price_1w=?, return_1w=?, "
                "check_date_1m=?, price_1m=?, return_1m=? WHERE pick_id=?",
                (check_date, latest_price, return_1w,
                 check_date, latest_price, return_1w, pick_id),
            )
            updated_1w += 1
            updated_1m += 1
        else:
            conn.execute(
                "UPDATE pick_performance SET check_date_1w=?, price_1w=?, return_1w=? "
                "WHERE pick_id=?",
                (check_date, latest_price, return_1w, pick_id),
            )
            updated_1w += 1

    conn.commit()
    conn.close()

    return {
        "checked": checked,
        "updated_1w": updated_1w,
        "updated_1m": updated_1m,
        "failed": failed,
    }
