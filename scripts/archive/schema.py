"""
stock-selecter-pro v1.0.4 归档数据库 Schema 定义。

定义3张表：
- screening_log:   每次筛选执行的快照
- pick_performance: 每只入选标的的逐次表现追踪
- strategy_stats:   策略聚合统计

所有数据库文件纯本地存储，不上传。
"""

import os
import sqlite3


CREATE_SCREENING_LOG = """
CREATE TABLE IF NOT EXISTS screening_log (
    run_id       TEXT PRIMARY KEY,
    timestamp    TEXT NOT NULL,
    market       TEXT NOT NULL,
    strategy_ids TEXT NOT NULL,
    mode         TEXT NOT NULL,
    candidate_count INTEGER NOT NULL,
    passed_count    INTEGER NOT NULL,
    top5_codes      TEXT NOT NULL
);
"""

CREATE_PICK_PERFORMANCE = """
CREATE TABLE IF NOT EXISTS pick_performance (
    pick_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT NOT NULL,
    stock_code     TEXT NOT NULL,
    stock_name     TEXT NOT NULL,
    strategy_id    TEXT NOT NULL,
    score          REAL NOT NULL,
    snapshot_price REAL NOT NULL,
    snapshot_date  TEXT NOT NULL,
    check_date_1w  TEXT,
    price_1w       REAL,
    return_1w      REAL,
    check_date_1m  TEXT,
    price_1m       REAL,
    return_1m      REAL,
    FOREIGN KEY (run_id) REFERENCES screening_log(run_id)
);
"""

CREATE_STRATEGY_STATS = """
CREATE TABLE IF NOT EXISTS strategy_stats (
    strategy_id     TEXT PRIMARY KEY,
    total_runs      INTEGER NOT NULL DEFAULT 0,
    total_picks     INTEGER NOT NULL DEFAULT 0,
    avg_score       REAL NOT NULL DEFAULT 0.0,
    avg_1w_return   REAL,
    avg_1m_return   REAL,
    win_rate_1w     REAL,
    win_rate_1m     REAL,
    best_pick_code  TEXT,
    best_pick_return REAL,
    last_updated    TEXT
);
"""

CREATE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_pp_run_id ON pick_performance(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_pp_snapshot_date ON pick_performance(snapshot_date);",
    "CREATE INDEX IF NOT EXISTS idx_pp_return_1w ON pick_performance(return_1w);",
    "CREATE INDEX IF NOT EXISTS idx_pp_strategy_id ON pick_performance(strategy_id);",
]


def init_db(db_path: str):
    """初始化 SQLite 数据库，自动创建表和索引，启用 WAL 模式。

    Args:
        db_path: 数据库文件路径，如 "archive/stock_selecter.db"

    Returns:
        str: 已初始化的数据库文件绝对路径
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.execute(CREATE_SCREENING_LOG)
    conn.execute(CREATE_PICK_PERFORMANCE)
    conn.execute(CREATE_STRATEGY_STATS)

    for idx_sql in CREATE_INDICES:
        conn.execute(idx_sql)

    conn.commit()
    conn.close()

    return os.path.abspath(db_path)
