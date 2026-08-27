"""报告生成模块。

生成格式：
- text_report.py:  纯文本报告
- json_report.py:  JSON结构化数据
- html_report.py:  HTML可视化报告（自包含单文件）
"""

from .text_report import generate_text_report
from .json_report import generate_json_report
from .html_report import generate_html_report

__all__ = [
    "generate_text_report",
    "generate_json_report",
    "generate_html_report",
]
