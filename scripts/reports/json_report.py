"""JSON结构化数据报告生成器。

输出符合标准Schema的结构化筛选结果，便于程序化处理与可视化。
"""

from datetime import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config  # noqa: E402


def generate_json_report(
    results: list[dict],
    output_dir: str,
    market_env: dict = None,
    strategy_stats: dict = None,
    total_passed: int = None,
) -> str:
    """生成JSON结构化选股报告。

    Args:
        results: 筛选结果列表（已按 --top 截断，仅含展示名单），每项含 code/name/score/strategy_hits/reasons/details 等。
        output_dir: 输出目录。
        market_env: 大盘环境数据。
        strategy_stats: 策略统计。
        total_passed: 实际通过总标的数（未截断），如实标注。

    Returns:
        str: JSON文件路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now()
    filename = f"选股结果_{now.strftime('%Y%m%d_%H%M%S')}.json"
    json_path = os.path.join(output_dir, filename)

    output = {
        "report_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "version": config.VERSION,
        "market": market_env or {},
        "strategies": strategy_stats or {},
        "total_passed": total_passed if total_passed is not None else len(results),
        "results": results,
        "data_quality": (market_env or {}).get("data_quality"),
        "risk_disclaimer": (
            "本报告基于东方财富公开行情接口生成（K线备选腾讯/新浪公开通道），数据可能存在3-5分钟延迟。"
            "技术形态筛选仅反映历史量价关系，不构成投资建议。"
            "股市有风险，投资需谨慎。"
        ),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return json_path
