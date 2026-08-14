"""c3-c7 新增功能离线冒烟测试（不依赖网络）。"""
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from backtest import collect_signal_returns, backtest_strategy
from run_screening import (
    _fmt_table, _sample_backtest_stocks, _bt_summarize,
    _build_trend_outlook, _warn_strategy_applicability,
)
from data.fundamental import _secid_for_valuation
from reports.html_report import (
    render_env_badge, render_env_signals, render_trend_outlook, render_backtest,
)

passed = []
failed = []


def check(name, cond, extra=""):
    if cond:
        passed.append(name)
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name} {extra}")


# ── 1. ASCII 表格 ──
t = _fmt_table(["策略", "名称", "胜率"], [["S01", "红肥绿瘦", "58.3%"], ["S06", "高股息", "样本不足"]])
check("_fmt_table 生成含边框", t.startswith("+") and "|" in t and "样本不足" in t)


# ── 2. 抽样 ──
cands = [{"code": f"{i:06d}", "name": f"S{i}", "market": "A股"} for i in range(100)]
s = _sample_backtest_stocks(cands, "A股", 20)
check("_sample_backtest_stocks 抽样数量", len(s) == 20)
check("_sample_backtest_stocks 样本覆盖", len({c["code"] for c in s}) == 20)
s_full = _sample_backtest_stocks(cands, "A股", 200)
check("_sample_backtest_stocks 超出时全量", len(s_full) == 100)


# ── 3. 收益统计 ──
r = _bt_summarize([0.01, -0.02, 0.03, 0.04, 0.05, -0.01], 5)
check("_bt_summarize 胜率", abs(r["win_rate"] - round(4 / 6, 4)) < 1e-9)
exp_avg = round(sum([0.01, -0.02, 0.03, 0.04, 0.05, -0.01]) / 6, 4)
check("_bt_summarize 平均收益", abs(r["avg_return"] - exp_avg) < 1e-9)
check("_bt_summarize 样本不足", _bt_summarize([0.01], 5) is None)


# ── 4. 合成K线回测（真实信号回放框架） ──
random.seed(42)
klines = []
price = 10.0
for i in range(320):
    chg = random.uniform(-0.03, 0.03)
    price = max(price * (1 + chg), 1.0)
    open_ = price * (1 + random.uniform(-0.01, 0.01))
    klines.append({
        "date": f"2025-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}",
        "open": round(open_, 2),
        "close": round(price, 2),
        "high": round(max(open_, price) * 1.01, 2),
        "low": round(min(open_, price) * 0.99, 2),
        "volume": random.randint(100000, 500000),
        "amount": random.randint(1000000, 9000000),
        "pct_chg": round(chg * 100, 2),
    })

col = collect_signal_returns("S01", klines)
check("collect_signal_returns 返回结构", "samples" in col and 5 in col and 20 in col)
bt = backtest_strategy("S01", klines)
check("backtest_strategy 返回结构", "hold_days" in bt)
# S06 估值策略：空 fundamental 时不应抛异常
col6 = collect_signal_returns("S06", klines, fundamental={"pe_ttm": 8.0, "pb": 1.0, "dividend_yield": 4.0})
check("collect_signal_returns S06 估值快照", "samples" in col6)


# ── 4.5 S16海龟 / S17动量（真实判定框架，非摆设） ──
from strategies import STRATEGY_REGISTRY

check("注册表含 S16/S17", "S16" in STRATEGY_REGISTRY and "S17" in STRATEGY_REGISTRY)
res16_short = STRATEGY_REGISTRY["S16"]["func"](klines=klines[:50])
check("S16 数据不足不通过", not res16_short["passed"] and any("不足" in r for r in res16_short["reasons"]))
res17_short = STRATEGY_REGISTRY["S17"]["func"](klines=klines[:50])
check("S17 数据不足不通过", not res17_short["passed"] and any("不足" in r for r in res17_short["reasons"]))
res16 = STRATEGY_REGISTRY["S16"]["func"](klines=klines)
res17 = STRATEGY_REGISTRY["S17"]["func"](klines=klines)
check("S16 真实输出", "conditions" in res16["details"] and "break_pass" in res16["details"]["conditions"] and len(res16["reasons"]) >= 2)
check("S17 真实输出", "mom_mid" in res17["details"] and len(res17["reasons"]) >= 2)
bt16 = backtest_strategy("S16", klines)
bt17 = backtest_strategy("S17", klines)
check("回测 S16 结构", "hold_days" in bt16 and "samples" in bt16)
check("回测 S17 结构", "hold_days" in bt17 and "samples" in bt17)


# ── 5. 三市场估值 secid ──
check("secid A股沪", _secid_for_valuation("600000", "A股") == "1.600000")
check("secid A股深", _secid_for_valuation("000001", "A股") == "0.000001")
check("secid 港股", _secid_for_valuation("700", "港股") == "116.00700")
check("secid 美股", _secid_for_valuation("AAPL", "美股") == "105.AAPL")


# ── 6. 趋势推演（假数据，条件式） ──
env = {
    "environment": "多头", "factor": 1.05,
    "signals": {
        "000001": {"name": "上证指数", "direction": "多头", "momentum_5d": 2.5,
                   "volume_ratio": 1.2, "volume_note": "放量"},
    },
    "breadth": {"up": 3000, "down": 1500, "flat": 200, "total": 4700, "ratio": 0.667},
    "outlook": [
        {"kind": "市场", "name": "上证指数", "signal": "MA多头，近5日+2.50%，量能放量",
         "outlook": "若上证指数站稳20日均线上方且量能延续，则多头结构有望保持；若放量滞涨或收盘跌破MA20，则可能转入震荡。"},
    ],
}
industry = [{"name": "半导体", "pct_chg": 3.2, "lead_stock_name": "中芯国际"}]
concept = []
outlook = _build_trend_outlook("A股", env, industry, concept)
check("_build_trend_outlook 生成条目", len(outlook) == 2)
check("_build_trend_outlook 条件式措辞", all("若" in it["outlook"] and "则" in it["outlook"] for it in outlook))


# ── 7. 能力边界提示（不依赖网络） ──
print("\n  [_warn_strategy_applicability 输出预览]")
_warn_strategy_applicability("港股", ["S01", "S06", "S07", "S12", "S13", "S14", "S15"])
_warn_strategy_applicability(config.MARKET_ALL, ["S06", "S15"])
_warn_strategy_applicability("A股", ["S15"])


# ── 8. HTML 渲染函数 ──
html_badge = render_env_badge(env)
html_sig = render_env_signals(env)
html_ot = render_trend_outlook(env)
html_bt = render_backtest({
    "A股": {"market": "A股", "strategies": [
        {"strategy_id": "S01", "name": "红肥绿瘦", "stocks_covered": 15, "snapshot_bias": False,
         "hold_days": {5: {"samples": 300, "win_rate": 0.583, "avg_return": 0.012},
                       20: {"samples": 290, "win_rate": 0.61, "avg_return": 0.024}}},
    ]},
})
html_bt_empty = render_backtest(None)
check("html 环境徽章", "badge-bull" in html_badge and "多头" in html_badge)
check("html 信号表", "sig-table" in html_sig and "近5日动量" in html_sig)
check("html 趋势推演", "outlook-item" in html_ot and "若" in html_ot)
check("html 回测表", "bt-win" in html_bt and "58.3%" in html_bt)
check("html 回测未启用提示", "未启用历史回测" in html_bt_empty)


# ── 9. 配置边界 ──
check("config 三市场集合不重叠",
      not (config.VALUATION_STRATEGIES & config.FINANCIAL_STRATEGIES)
      and not (config.VALUATION_STRATEGIES & config.MONEY_FLOW_STRATEGIES)
      and not (config.FINANCIAL_STRATEGIES & config.MONEY_FLOW_STRATEGIES))
check("config 集合覆盖 S06/S07/S12/S13/S14/S15",
      config.VALUATION_STRATEGIES == {"S06", "S07"}
      and config.FINANCIAL_STRATEGIES == {"S12", "S13", "S14"}
      and config.MONEY_FLOW_STRATEGIES == {"S15"})


print(f"\n结果: {len(passed)} 通过, {len(failed)} 失败")
if failed:
    print("失败项:", failed)
    sys.exit(1)
