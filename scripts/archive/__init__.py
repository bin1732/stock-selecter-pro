"""
stock-selecter-pro v1.0.1 策略表现档案库 (archive) 子模块。

功能：
- tracker:   筛选快照记录 + 收益回填
- analytics: 策略表现聚合统计
- reporter:  档案报告生成
"""

from .tracker import log_screening, refresh_performance
from .analytics import refresh_strategy_stats, get_strategy_ranking
from .reporter import text_archive_report, json_archive_report

__all__ = [
    "log_screening",
    "refresh_performance",
    "refresh_strategy_stats",
    "get_strategy_ranking",
    "text_archive_report",
    "json_archive_report",
]
