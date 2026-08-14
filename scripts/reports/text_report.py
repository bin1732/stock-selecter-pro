"""纯文本报告生成器。

生成包含大盘环境、策略统计、筛选结果、行业分布、风险声明的文本报告。
所有数据基于真实计算结果，不编造。
"""

from datetime import datetime
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config  # noqa: E402

def generate_text_report(
    results: list[dict],
    output_dir: str,
    market_env: dict = None,
    strategy_stats: dict = None,
) -> str:
    """生成纯文本选股报告。

    Args:
        results: 筛选结果列表，每项含 code/name/score/strategy_hits/reasons/details 等。
        output_dir: 输出目录。
        market_env: 大盘环境数据 {indices: {...}, environment: "多头"/"震荡"/"空头"}。
        strategy_stats: 策略统计 {strategy_code: {passed: int, total: int}, ...}。

    Returns:
        str: 报告文件路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now()
    filename = f"选股报告_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    report_path = os.path.join(output_dir, filename)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write(f"   stock-selecter-pro {config.VERSION} 选股报告\n")
        f.write(f"   生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"   数据源: 东方财富公开行情API（K线备选: 腾讯/新浪公开通道）\n")
        if market_env and market_env.get("data_channel"):
            f.write(f"   数据通道: {market_env['data_channel']}\n")
        f.write("=" * 70 + "\n\n")

        # 大盘环境
        if market_env:
            f.write("【大盘环境】\n")
            env = market_env.get("environment", "未知")
            factor = market_env.get("factor", 1.0)
            f.write(f"  市场状态: {env}（环境系数 {factor:.2f}）\n")
            indices = market_env.get("indices", {})
            for code, info in indices.items():
                direction = "上涨" if info.get("pct_change", 0) > 0 else ("下跌" if info.get("pct_change", 0) < 0 else "平盘")
                f.write(f"  {info.get('name', code)}: {info.get('price', 0):.2f}  "
                        f"{info.get('pct_change', 0):+.2f}% {direction}\n")

            # 指数信号（均线结构/短期动量/量能）
            signals = market_env.get("signals", {})
            if signals:
                f.write("  指数信号（真实数据）:\n")
                for code, sig in signals.items():
                    name = sig.get("name", code)
                    direction = sig.get("direction", "-")
                    mom = sig.get("momentum_5d")
                    mom_str = f"{mom:+.2f}%" if mom is not None else "-"
                    vol = sig.get("volume_note", "-")
                    vr = sig.get("volume_ratio")
                    vol_str = f"{vol}" + (f"({vr:.2f}x)" if vr is not None else "")
                    f.write(f"    {name}: MA{direction} | 近5日 {mom_str} | 量能 {vol_str}\n")

            # 市场宽度（A股）
            breadth = market_env.get("breadth")
            if breadth:
                f.write(f"  市场宽度: 上涨 {breadth['up']} / 下跌 {breadth['down']} / 平 {breadth['flat']} "
                        f"(上涨占比 {breadth['ratio'] * 100:.1f}%)\n")
            f.write("\n")

        # 趋势推演（条件式，非预测承诺）
        outlook = market_env.get("outlook", []) if market_env else []
        if outlook:
            f.write("【市场趋势推演】（基于实时真实信号 · 条件式表述 · 非预测承诺）\n")
            for it in outlook:
                f.write(f"  [{it.get('kind', '')}] {it.get('name', '')}（{it.get('signal', '')}）\n")
                f.write(f"    → {it.get('outlook', '')}\n")
            f.write("  推演仅为数据结构的条件式描述（若…则…），不构成涨跌承诺与投资建议。\n\n")

        # 策略统计
        if strategy_stats:
            f.write("【策略通过率】\n")
            for s_code, stat in sorted(strategy_stats.items()):
                passed = stat.get("passed", 0)
                total = stat.get("total", 0)
                rate = f"{passed}/{total}" if total > 0 else "0/0"
                f.write(f"  {s_code}: {rate}\n")
            f.write("\n")

        # 筛选结果
        if not results:
            f.write("【筛选结果】\n")
            f.write("  当日未筛选出符合条件的标的。\n\n")
        else:
            f.write(f"【筛选结果】（共 {len(results)} 只通过）\n\n")

            top_n = getattr(config, "TOP_N_OUTPUT", 50)
            for i, s in enumerate(results[:top_n]):
                code = s.get("code", "")
                name = s.get("name", "")
                score = s.get("score", 0)
                hits = s.get("strategy_hits", [])
                consensus = s.get("consensus_level", "")
                mkt = s.get("market", "")
                mkt_str = f"[{mkt}] " if mkt else ""
                f.write(f"#{i+1}  {mkt_str}{code}  {name}  评分: {score:.2f}\n")
                if consensus:
                    f.write(f"    共识度: {consensus}\n")
                if hits:
                    f.write(f"    命中策略: {', '.join(hits)}\n")
                reasons = s.get("reasons", [])
                for reason in reasons[:5]:
                    f.write(f"    · {reason}\n")
                f.write("\n")

        # 行业分布
        industry_map = {}
        for s in results:
            ind = s.get("industry", "未知")
            industry_map[ind] = industry_map.get(ind, 0) + 1
        if industry_map:
            f.write("【行业分布】\n")
            for ind, cnt in sorted(industry_map.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {ind}: {cnt}只\n")
            f.write("\n")

        # 关注方向
        f.write("【关注方向说明】\n")
        f.write("  本报告基于多种技术形态与基本面量化筛选，提供的选股列表仅作技术形态参考，\n")
        f.write("  不构成任何投资建议。投资者应结合基本面、消息面、市场情绪等多维因素综合\n")
        f.write("  判断，自主决策并承担风险。\n\n")

        # 风险声明
        f.write("=" * 70 + "\n")
        f.write("【风险声明】\n")
        f.write("1. 本报告基于东方财富公开行情接口生成（K线备选腾讯/新浪公开通道），数据可能存在3-5分钟延迟。\n")
        f.write("2. 技术形态筛选仅反映历史量价关系，不代表未来走势。\n")
        f.write("3. 本报告不构成任何投资建议，也不构成收益承诺。\n")
        f.write("4. 所有判定逻辑公开透明、可审计复现。\n")
        f.write(f"5. 数据时效: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("6. 股市有风险，投资需谨慎。\n")
        f.write("=" * 70 + "\n")

    return report_path
