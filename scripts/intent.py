"""自然语言选股意图 → 参数组合（人性化入口，规则映射，零外部依赖）。

定位（如实，不夸大）：
本模块是**确定性规则映射**——把常见中文选股意图翻译成 skill 的策略组合与
参数建议（市场 / 策略 / 组合模式）。它不进行自由文本语义理解，仅匹配预定义
意图表；未匹配的输入如实返回空结果，由调用方（Agent）按用户明确需求用标准
参数执行，不猜测、不编造能力。

策略映射全部来自 17 种策略的真实能力（STRATEGY_REGISTRY），如"低估值"对应
S07 低估值策略、"高股息"对应 S06 高股息策略；本模块不新增任何策略逻辑。

用法：
    python intent.py "帮我选低估值高股息"     # 输出解析结果与建议命令
    from intent import resolve_intent
    resolve_intent("港股 高股息")              # -> {"market": "港股", "strategies": ["S06"], ...}
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from strategies import STRATEGY_REGISTRY  # noqa: E402  # 策略名称/编号真实来源

# 策略能力表：意图关键词 -> (策略ID, 说明)。说明取自策略注册表名称。
_STRATEGY_INTENTS = [
    (["低估值", "价值洼地", "便宜", "低估"], "S07"),
    (["高股息", "分红", "收息", "股息"], "S06"),
    (["成长", "高增长", "业绩好", "费雪"], "S14"),
    (["roe", "优质", "白马", "杜邦"], "S13"),
    (["现金流", "经营质量", "造血"], "S12"),
    (["macd", "底背离", "背离", "金叉"], "S05"),
    (["放量", "突破", "创新高"], "S08"),
    (["趋势", "均线", "多头", "上涨趋势"], "S09"),
    (["布林", "超跌", "反弹"], "S10"),
    (["蓄力", "横盘", "低位", "筑底"], "S15"),
    (["海龟", "通道突破"], "S16"),
    (["动量", "强势"], "S17"),
    (["红肥绿瘦", "吸筹", "量价"], "S01"),
    (["上涨波段"], "S02"),
    (["回调", "缩量"], "S03"),
    (["筹码", "集中"], "S11"),
]

# 市场意图
_MARKET_INTENTS = [
    (["港股", "hk", "香港"], config.MARKET_HK),
    (["美股", "us", "美国", "纳斯达克", "纽交所"], config.MARKET_US),
    (["全部", "全选", "所有市场", "都看看"], config.MARKET_ALL),
    (["a股", "a 股", "沪深", "国内"], config.MARKET_A),
]

# 组合模式意图
_MODE_INTENTS = [
    (["都要满足", "同时满足", "全部命中"], "intersection"),
    (["综合", "加权", "打分"], "weighted"),
    (["任一", "任一个"], "union"),
]

_STRATEGY_NAMES = {sid: STRATEGY_REGISTRY[sid]["name"] for sid in STRATEGY_REGISTRY}

# 否定词：出现在关键词前表示"排除该策略"（如"不要成长股""回避高股息""没有现金流"）。
# 规则如实定位：仅处理"否定词+关键词"相邻的显式否定；复杂句式（如"不要只选成长股"）
# 不做语义推断，由 Agent 按用户明确需求补正。
_NEGATIONS = ["不要", "不选", "回避", "排除", "剔除", "没有", "无", "不", "非", "别"]


def _is_negated(text: str, keyword: str) -> bool:
    """检测 keyword 是否被否定词紧邻修饰（"否定词+关键词"出现在文本中即视为否定）。"""
    return any(neg + keyword in text for neg in _NEGATIONS)


def resolve_intent(text: str) -> dict:
    """把自然语言选股意图解析为参数组合建议（确定性规则匹配）。

    Args:
        text: 用户意图文本，如 "帮我选低估值高股息" / "港股 高股息 都要满足"

    Returns:
        dict: {market, strategies, strategy_mode, hits, note}
            - market / strategies / strategy_mode: 匹配结果；未匹配项为 None
            - hits: 命中的意图关键词列表（如实展示匹配依据）
            - note: 一句如实说明（规则映射定位，非语义理解）
    """
    t = text.lower()
    hits = []

    strategies = []
    for kws, sid in _STRATEGY_INTENTS:
        # 策略级否定：任一关键词被否定词紧邻修饰 → 排除整个策略
        # （避免关键词子串绕过否定检测，如"回避高股息"中"股息"是"高股息"子串）
        negated = any(_is_negated(t, kw) for kw in kws)
        matched = any(kw in t for kw in kws)
        if matched and not negated:
            strategies.append(sid)
            hits.append(f"{sid}({_STRATEGY_NAMES[sid]})")

    market = None
    market_hits = []
    for kws, m in _MARKET_INTENTS:
        if any(kw in t for kw in kws):
            market_hits.append(m)
            hits.append(f"市场:{m}")
    if len(market_hits) == 1:
        market = market_hits[0]
    elif len(market_hits) > 1:
        # 多市场词并存（如"美股还是港股"）：不武断选择，交由用户明确（如实提示）
        market = None
        hits.append("多市场并存（需用户明确）")

    strategy_mode = None
    for kws, mode in _MODE_INTENTS:
        if any(kw in t for kw in kws):
            strategy_mode = mode
            hits.append(f"模式:{mode}")
            break

    if strategies:
        strategies = sorted(set(strategies))
    else:
        strategies = None

    return {
        "market": market,
        "strategies": strategies,
        "strategy_mode": strategy_mode,
        "hits": hits,
        "note": "确定性规则映射（关键词→策略能力表），非自由文本语义理解；未匹配项由调用方按用户明确需求补默认参数。",
    }


def build_command(intent: dict) -> str:
    """把意图解析结果组装成可执行的 run_screening 命令。"""
    parts = ["python run_screening.py", "--no-guide"]
    if intent["market"]:
        parts.append(f'--market "{intent["market"]}"')
    if intent["strategies"]:
        parts.append("--strategies " + ",".join(intent["strategies"]))
    if intent["strategy_mode"]:
        parts.append(f"--strategy-mode {intent['strategy_mode']}")
    parts.append("--top 20")
    return " \\\n    ".join(parts)


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python intent.py \"你的选股意图文本\"")
        print("示例: python intent.py \"帮我选低估值高股息\"")
        print("      python intent.py \"港股 高股息 都要满足\"")
        return
    text = " ".join(args)
    r = resolve_intent(text)
    print(f"意图: {text}")
    print(f"匹配依据: {', '.join(r['hits']) if r['hits'] else '（未匹配到任何策略/市场关键词）'}")
    print(f"建议市场: {r['market'] or '（默认 A股）'}")
    print(f"建议策略: {', '.join(r['strategies']) if r['strategies'] else '（默认全部 17 种）'}")
    print(f"建议组合: {r['strategy_mode'] or '（默认加权）'}")
    print(f"定位: {r['note']}")
    if r["market"] or r["strategies"] or r["strategy_mode"]:
        print("\n建议命令:")
        print(build_command(r))


if __name__ == "__main__":
    main()
