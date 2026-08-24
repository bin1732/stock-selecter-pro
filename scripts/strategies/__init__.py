"""策略层：统一导出17种选股策略与策略注册表。

全部策略均为真实实现，可独立调用或通过组合引擎联合判定。

策略清单：
  S01 红肥绿瘦    — s01_volume_price.py
  S02 上涨波段    — s01_volume_price.py
  S03 回调缩量    — s01_volume_price.py
  S04 横盘调整    — s01_volume_price.py
  S05 MACD底背离  — s02_macd_divergence.py
  S06 高股息策略  — s03_high_dividend.py
  S07 低估值策略  — s04_low_valuation.py
  S08 放量突破    — s05_volume_breakout.py
  S09 趋势分析    — s06_trend_analysis.py
  S10 布林带下轨  — s07_bollinger.py
  S11 筹码集中    — s08_chip_concentration.py
  S12 现金流质量  — s09_cashflow_quality.py
  S13 ROE杜邦筛选 — s10_roe_screening.py
  S14 费雪成长股  — s11_fisher_growth.py
  S15 长期蓄力    — s12_long_consolidation.py
  S16 海龟交易    — s13_turtle.py
  S17 动量策略    — s14_momentum.py
"""

from .s01_volume_price import (
    check_s01_red_fat_green_thin,
    check_s02_rising_wave,
    check_s03_pullback_shrink,
    check_s04_sideways_consolidation,
)
from .s02_macd_divergence import check_s05_macd_divergence
from .s03_high_dividend import check_s06_high_dividend
from .s04_low_valuation import check_s07_low_valuation
from .s05_volume_breakout import check_s08_volume_breakout
from .s06_trend_analysis import check_s09_trend_analysis
from .s07_bollinger import check_s10_bollinger
from .s08_chip_concentration import check_s11_chip_concentration
from .s09_cashflow_quality import check_s12_cashflow_quality
from .s10_roe_screening import check_s13_roe_screening
from .s11_fisher_growth import check_s14_fisher_growth
from .s12_long_consolidation import check_s15_long_consolidation
from .s13_turtle import check_s16_turtle
from .s14_momentum import check_s17_momentum

# ── 策略注册表（编号 → 名称 + 函数）──
STRATEGY_REGISTRY = {
    "S01": {"name": "红肥绿瘦", "func": check_s01_red_fat_green_thin},
    "S02": {"name": "上涨波段", "func": check_s02_rising_wave},
    "S03": {"name": "回调缩量", "func": check_s03_pullback_shrink},
    "S04": {"name": "横盘调整", "func": check_s04_sideways_consolidation},
    "S05": {"name": "MACD底背离", "func": check_s05_macd_divergence},
    "S06": {"name": "高股息策略", "func": check_s06_high_dividend},
    "S07": {"name": "低估值策略", "func": check_s07_low_valuation},
    "S08": {"name": "放量突破", "func": check_s08_volume_breakout},
    "S09": {"name": "趋势分析", "func": check_s09_trend_analysis},
    "S10": {"name": "布林带下轨", "func": check_s10_bollinger},
    "S11": {"name": "筹码集中", "func": check_s11_chip_concentration},
    "S12": {"name": "现金流质量", "func": check_s12_cashflow_quality},
    "S13": {"name": "ROE杜邦筛选", "func": check_s13_roe_screening},
    "S14": {"name": "费雪成长股", "func": check_s14_fisher_growth},
    "S15": {"name": "长期蓄力", "func": check_s15_long_consolidation},
    "S16": {"name": "海龟交易", "func": check_s16_turtle},
    "S17": {"name": "动量策略", "func": check_s17_momentum},
}


def get_strategy(strategy_id: str):
    """按编号获取策略元信息。"""
    return STRATEGY_REGISTRY.get(strategy_id.upper())


__all__ = [
    "check_s01_red_fat_green_thin",
    "check_s02_rising_wave",
    "check_s03_pullback_shrink",
    "check_s04_sideways_consolidation",
    "check_s05_macd_divergence",
    "check_s06_high_dividend",
    "check_s07_low_valuation",
    "check_s08_volume_breakout",
    "check_s09_trend_analysis",
    "check_s10_bollinger",
    "check_s11_chip_concentration",
    "check_s12_cashflow_quality",
    "check_s13_roe_screening",
    "check_s14_fisher_growth",
    "check_s15_long_consolidation",
    "check_s16_turtle",
    "check_s17_momentum",
    "STRATEGY_REGISTRY",
    "get_strategy",
]
