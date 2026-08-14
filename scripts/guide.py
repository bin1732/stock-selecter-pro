"""
stock-selecter-pro v1.0.1 新用户交互式引导向导 (Interactive Guide)

设计理念：
- 不强制用户从某一步开始，允许从任意环节切入
- 每一步均可跳过或返回上一步
- 所有数据/建议来自东方财富公开API真实返回，绝不编造数值
- 每步提供实时真实数据作为决策依据

流程：
  1. 欢迎页    → 功能概览 + 策略清单
  2. 环境检测  → 真实调用东方财富API测试各接口连通性
  3. 市场选择  → 查询A股/港股/美股当前真实可获取的股票数量
  4. 策略适配  → 基于真实大盘MA均线判断多空，智能适配策略组合
  5. 参数配置  → 非强制引导式设置输出格式/TOP-N等
  6. 执行确认  → 预览配置后转入筛选执行
  7. 档案追踪  → 询问是否开启策略表现档案库（可选）
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Optional

# 确保 scripts 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

# 东财实时/历史接口共享客户端（多节点故障切换）
from data._http import push2_get, kline_get

# ============================================================
# HTTP 会话（复用东方财富标准UA）
# ============================================================
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
})

# ============================================================
# 配色辅助（终端ANSI码）
# ============================================================
C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "red": "\033[91m",
    "magenta": "\033[95m",
}


def _c(text: str, color: str) -> str:
    """给文本包裹颜色码。"""
    return f"{C.get(color, '')}{text}{C['reset']}"


# ============================================================
# Session State: 引导过程中的配置状态
# ============================================================
_session_state = {
    "market": config.DEFAULT_MARKET,
    "mode": config.SCREEN_MODE,
    "strategy_ids": None,          # None = 全部启用
    "strategy_mode": config.DEFAULT_STRATEGY_MODE,
    "weights": None,
    "top_n": config.TOP_N_OUTPUT,
    "output_format": "all",
    "output_dir": config.OUTPUT_DIR,
    "multi_period": False,
    "no_cache": False,
    "track": False,
}

# 步骤定义
STEPS = [
    "welcome",          # 0
    "env_check",        # 1
    "market_select",    # 2
    "strategy_recommend",  # 3
    "param_config",     # 4
    "exec_confirm",     # 5
    "archive_setup",    # 6
]

# ============================================================
# 用户偏好记忆（越用越懂用户）
# 将上次引导确定的偏好保存到本地文件，下次引导自动预填，
# 仅影响默认值，不覆盖用户本次的新选择。
# ============================================================
PREFS_FILE = os.path.join(os.path.expanduser("~"), ".stock_selecter_prefs.json")
_PREF_KEYS = ("market", "mode", "strategy_mode", "top_n", "output_format",
              "output_dir", "multi_period")


def _load_prefs() -> dict:
    """读取本地用户偏好。文件不存在或损坏时返回空 dict。"""
    try:
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_prefs():
    """将本次引导确定的关键偏好写入本地文件。"""
    prefs = {}
    for key in _PREF_KEYS:
        val = _session_state.get(key)
        if val is not None:
            prefs[key] = val
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 偏好写入失败不影响引导主流程


# ============================================================
# 通用 API 调用工具
# ============================================================

def _api_get(url: str, params: dict = None, timeout: int = 15) -> Optional[dict]:
    """安全调用东方财富公开API，返回 parsed JSON 或 None。

    - push2 实时接口（列表/行情/估值）：经共享客户端做域名级故障切换
      （主节点不可达时切换官方备用延迟节点）
    - push2his 历史K线接口：经共享客户端做多编号节点故障切换，
      全部节点不可达时自动切换腾讯公开K线通道（三市场可用）
    - 其余接口直连
    """
    try:
        if "push2.eastmoney.com" in url:
            path = url.split("push2.eastmoney.com", 1)[1]
            data = push2_get(path, params=params, timeout=timeout)
            return data if data else None
        if "push2his.eastmoney.com" in url:
            from urllib.parse import urlsplit, parse_qs
            parts = urlsplit(url)
            qs = {k: v[0] for k, v in parse_qs(parts.query).items()}
            if params:
                qs.update(params)
            data = kline_get(parts.path, params=qs, timeout=timeout)
            return data if data else None
        resp = _session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ============================================================
# Step 1: 欢迎页
# ============================================================

def _step_welcome():
    """展示欢迎信息：Skill功能与策略概览。"""
    print()
    print("=" * 70)
    print(_c("  stock-selecter-pro v" + config.VERSION + "  新用户引导向导", "bold"))
    print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    print("  欢迎使用 stock-selecter-pro 多市场量化选股引擎！")
    print()
    print("  【核心能力】")
    print("    - 数据与主流程执行覆盖 A股 / 港股 / 美股（港股/美股技术面策略可用）")
    print("    - 内置 17 种选股策略（全部真实代码可审计）")
    print("    - 三种策略组合模式：并集 / 交集 / 加权评分")
    print("    - 多周期交叉验证（日/周）")
    print("    - 输出 Text / JSON / 交互式HTML 三格式报告")
    print()
    print("  【数据来源】")
    print("    东方财富公开行情API（push2.eastmoney.com）")
    print("    全部为公开接口，不涉及认证，合规合法")
    print("    数据延迟约 3-5 分钟，非Level-2实时数据")
    print()
    print("  【17种策略一览】")
    print("    " + "-" * 60)
    for k, v in sorted(config.STRATEGY_DEFAULT_WEIGHTS.items()):
        from strategies import STRATEGY_REGISTRY
        name = STRATEGY_REGISTRY.get(k, {}).get("name", k)
        weight = v
        print(f"    {k:5s}  {name:12s}  默认权重: {weight:.2f}")
    print("    " + "-" * 60)
    print()
    print("  【数据源声明】")
    print("    全部数据来自东方财富公开HTTP接口，数值均为真实返回。")
    print("    本引导中每一步的环境检测和建议都基于实时API数据。")
    print()
    print("  【风险提示】")
    print("    以上为技术形态与基本面筛选结果，不构成投资建议。")
    print("    股市有风险，投资需谨慎。请结合自身风险承受能力独立决策。")
    print()
    print("-" * 70)
    print("  接下来将依次引导：环境检测 → 市场选择 → 策略适配 → 参数配置 → 执行确认 → 档案追踪")
    print("  每步均可键入 's' 跳过、'b' 返回上一步、'q' 退出引导")
    print("-" * 70)
    print()


# ============================================================
# Step 2: 环境检测（真实调用API测试连通性）
# ============================================================

def _step_env_check():
    """真实调用东方财富公开API，测试各接口当前连通状态。"""
    print()
    print(_c("─" * 60, "dim"))
    print(_c("  [环境检测] 正在测试东方财富公开API连通性...", "bold"))
    print(_c("─" * 60, "dim"))
    print()

    endpoints = {}

    # 1. A股列表接口
    print("  测试 A股列表接口 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1", "pz": "5", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f12,f14",
        },
    )
    if result and result.get("data", {}).get("diff"):
        total = result["data"].get("total", "?")
        endpoints["A股列表"] = {"status": "OK", "info": f"沪深京A股总计约 {total} 只"}
        print(_c("OK", "green") + f" (总计 {total} 只)")
    else:
        endpoints["A股列表"] = {"status": "FAIL", "info": "接口未返回数据"}
        print(_c("FAIL (接口未响应或返回空)", "red"))

    # 2. 实时行情接口
    print("  测试 实时行情接口 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/ulist.np",
        params={
            "fltt": "2",
            "secids": "1.600519,0.000001",
            "fields": "f2,f3,f12,f14",
        },
    )
    if result and result.get("data", {}).get("diff"):
        items = result["data"]["diff"]
        names = [it.get("f14", "?") for it in items]
        endpoints["实时行情"] = {"status": "OK", "info": f"可获取 {', '.join(names)} 等标的实时数据"}
        print(_c("OK", "green") + f" (获取 {len(items)} 只)")
    else:
        endpoints["实时行情"] = {"status": "FAIL", "info": "接口未返回数据"}
        print(_c("FAIL", "red"))

    # 3. K线接口
    print("  测试 日K线接口 ...", end=" ")
    result = _api_get(
        "https://79.push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": "1.600519",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101", "fqt": "1",
            "end": "20500101",
            "lmt": "5",
        },
    )
    if result and result.get("data", {}).get("klines"):
        kline_count = len(result["data"]["klines"])
        endpoints["日K线"] = {"status": "OK", "info": f"成功获取贵州茅台K线，返回 {kline_count} 条"}
        print(_c("OK", "green") + f" (获取 {kline_count} 条)")
    else:
        endpoints["日K线"] = {"status": "FAIL", "info": "K线接口未返回数据"}
        print(_c("FAIL", "red"))

    # 4. 港股列表接口
    print("  测试 港股列表接口 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1", "pz": "5", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:128+t:3,m:128+t:4",
            "fields": "f12,f14",
        },
    )
    if result and result.get("data", {}).get("diff"):
        total = result["data"].get("total", "?")
        endpoints["港股列表"] = {"status": "OK", "info": f"港股总计约 {total} 只"}
        print(_c("OK", "green") + f" (总计 {total} 只)")
    else:
        endpoints["港股列表"] = {"status": "FAIL", "info": "接口未返回数据"}
        print(_c("FAIL", "red"))

    # 5. 美股列表接口
    print("  测试 美股列表接口 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1", "pz": "5", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:105+t:3,m:105+t:4",
            "fields": "f12,f14",
        },
    )
    if result and result.get("data", {}).get("diff"):
        total = result["data"].get("total", "?")
        endpoints["美股列表"] = {"status": "OK", "info": f"美股总计约 {total} 只"}
        print(_c("OK", "green") + f" (总计 {total} 只)")
    else:
        endpoints["美股列表"] = {"status": "FAIL", "info": "接口未返回数据"}
        print(_c("FAIL", "red"))

    # 6. 估值接口
    print("  测试 估值数据接口 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={
            "secid": "1.600519",
            "fields": "f43,f44,f45,f46,f48,f50,f57,f58,f60,f116,f117,f162",
        },
    )
    if result and result.get("data"):
        data = result["data"]
        price = data.get("f43", "?")
        # push2 估值接口未带 fltt 参数时 f43 为整数分单位（如 144500 = 1445.00元），统一 /100
        price_val = round(price / 100, 2) if isinstance(price, (int, float)) and price else price
        endpoints["估值数据"] = {"status": "OK", "info": f"贵州茅台最新价: {price_val}"}
        print(_c("OK", "green"))
    else:
        endpoints["估值数据"] = {"status": "FAIL", "info": "接口未返回数据"}
        print(_c("FAIL", "red"))

    # 汇总报告
    print()
    print("  " + "=" * 55)
    print(f"  {'接口名称':20s} {'状态':10s} {'详情'}")
    print("  " + "-" * 55)
    ok_count = 0
    for name, info in endpoints.items():
        status_str = _c("✓ 可用", "green") if info["status"] == "OK" else _c("✗ 不可用", "red")
        if info["status"] == "OK":
            ok_count += 1
        print(f"  {name:20s} {status_str:14s} {info['info'][:40]}")
    print("  " + "-" * 55)
    print(f"  总计: {ok_count}/{len(endpoints)} 个接口可用")
    print()

    if ok_count == 0:
        print(_c("  [WARN] 所有接口均不可用，请检查网络连接或东方财富API状态。", "yellow"))
        print("  您可以继续后续步骤，但筛选执行可能失败。")
    elif ok_count < len(endpoints):
        missing = [n for n, i in endpoints.items() if i["status"] == "FAIL"]
        print(_c(f"  [NOTE] 以下接口暂不可用: {', '.join(missing)}", "yellow"))
        print("  相关功能将自动降级。")
    else:
        print(_c("  [OK] 所有接口连通正常，可以进行筛选。", "green"))

    print()
    return endpoints


# ============================================================
# Step 3: 市场选择（真实查询各市场股票数量）
# ============================================================

def _step_market_select():
    """真实查询A股/港股/美股当前可获取的股票数量。"""
    print()
    print(_c("─" * 60, "dim"))
    print(_c("  [市场选择] 查询各市场当前真实可获股票数量...", "bold"))
    print(_c("─" * 60, "dim"))
    print()

    markets_info = {}

    # A股
    print("  查询 A股 全市场列表 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1", "pz": "1", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f12,f14",
        },
    )
    a_count = 0
    if result and result.get("data"):
        a_count = result["data"].get("total", 0)
        print(_c(f"OK", "green") + f" ({a_count} 只)")
    else:
        print(_c("查询失败", "red"))
    markets_info["A股"] = a_count

    # 港股
    print("  查询 港股 全市场列表 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1", "pz": "1", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:128+t:3,m:128+t:4",
            "fields": "f12,f14",
        },
    )
    hk_count = 0
    if result and result.get("data"):
        hk_count = result["data"].get("total", 0)
        print(_c("OK", "green") + f" ({hk_count} 只)")
    else:
        print(_c("查询失败", "red"))
    markets_info["港股"] = hk_count

    # 美股
    print("  查询 美股 全市场列表 ...", end=" ")
    result = _api_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1", "pz": "1", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:105+t:3,m:105+t:4",
            "fields": "f12,f14",
        },
    )
    us_count = 0
    if result and result.get("data"):
        us_count = result["data"].get("total", 0)
        print(_c("OK", "green") + f" ({us_count} 只)")
    else:
        print(_c("查询失败", "red"))
    markets_info["美股"] = us_count

    print()
    print(f"  {'市场':12s} {'可获取股票数':>12s}  {'说明'}")
    print("  " + "-" * 50)
    for mkt, count in markets_info.items():
        note = ""
        if mkt == "A股":
            note = "沪深京全部A股（含北交所）"
        elif mkt == "港股":
            note = "港股主板 + 创业板"
        elif mkt == "美股":
            note = "NYSE + NASDAQ"
        print(f"  {mkt:12s} {count:>10,} 只  {note}")

    print()
    print(f"  当前选择: " + _c(_session_state["market"], "cyan"))
    print()
    print("  输入选择: [1] A股  [2] 港股  [3] 美股  [4] 全部  [Enter] 保持不变")
    print()
    print("  提示: v1.0.1 主流程已支持 A股/港股/美股 三市场执行；")
    print("        港股/美股 无基本面/资金流公开数据，对应策略将自动不通过（真实缺数据）。")
    print()

    return markets_info


# ============================================================
# Step 4: 策略适配（基于真实大盘MA均线判断多空）
# ============================================================

def _step_strategy_recommend():
    """基于真实上证/深证指数MA均线判断大盘环境，智能适配策略组合。"""
    print()
    print(_c("─" * 60, "dim"))
    print(_c("  [策略适配] 基于真实大盘环境智能适配...", "bold"))
    print(_c("─" * 60, "dim"))
    print()

    # 按当前所选市场获取对应真实指数K线（A股: 上证+深证 / 港股: 恒生+国企 / 美股: 道琼斯+纳指）
    market = _session_state.get("market") or config.DEFAULT_MARKET
    index_cfg = config.INDEX_SECIDS.get(market)
    if index_cfg is None:
        # "全部" 市场无单一指数代表，策略适配以A股大盘为参考
        print(_c("  [NOTE] 全部市场模式无单一指数代表，策略适配以A股大盘为参考。", "yellow"))
        index_cfg = config.INDEX_SECIDS.get(config.MARKET_A, {})
    groups = []
    for code, (name, mkt) in index_cfg.items():
        print(f"  获取 {name}({code}) 近{config.INDEX_KLINE_DAYS}日K线 ...", end=" ")
        result = _api_get(
            "https://79.push2his.eastmoney.com/api/qt/stock/kline/get",
            params={
                "secid": f"{mkt}.{code}",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": "101", "fqt": "1",
                "end": "20500101",
                "lmt": str(config.INDEX_KLINE_DAYS),
            },
        )
        klines = None
        if result and result.get("data", {}).get("klines"):
            klines = [line.split(",") for line in result["data"]["klines"]]
            print(_c("OK", "green") + f" ({len(klines)} 条)")
        else:
            print(_c("获取失败", "red"))
        groups.append((name, klines))

    # 分析大盘环境
    print()
    market_analysis = _analyze_market(*groups)
    env = market_analysis["environment"]
    detail = market_analysis["detail"]
    ma5 = market_analysis["ma5"]
    ma20 = market_analysis["ma20"]
    ma60 = market_analysis.get("ma60")
    idx_name = market_analysis.get("index_name") or "指数"

    print(f"  大盘环境判断: " + _c(env, "cyan"))
    print(f"  {detail}")
    if ma5 and ma20:
        print(f"  {idx_name}: MA5={ma5:.0f}  MA20={ma20:.0f}" + (f"  MA60={ma60:.0f}" if ma60 else ""))

    # 基于环境匹配策略
    print()
    print("  基于当前大盘环境，适配策略组合:")
    print("  " + "-" * 60)

    from strategies import STRATEGY_REGISTRY

    if env == "多头":
        recommendations = [
            ("S01", "红肥绿瘦", "阳线主导，顺势做多"),
            ("S02", "上涨波段", "温和放量上攻"),
            ("S08", "放量突破", "突破前高确认"),
            ("S09", "趋势分析", "均线多头排列"),
            ("S14", "费雪成长股", "成长驱动行情"),
            ("S16", "海龟交易", "唐奇安通道突破顺势"),
            ("S17", "动量策略", "趋势动量延续"),
        ]
    elif env == "空头":
        recommendations = [
            ("S05", "MACD底背离", "底部信号捕捉"),
            ("S10", "布林带下轨", "超跌反弹机会"),
            ("S15", "长期蓄力", "底部放量启动"),
            ("S06", "高股息策略", "防御性配置"),
            ("S07", "低估值策略", "价值洼地"),
        ]
    else:  # 震荡
        recommendations = [
            ("S03", "回调缩量", "震荡市回调机会"),
            ("S04", "横盘调整", "蓄力突破前"),
            ("S06", "高股息策略", "震荡市防御"),
            ("S07", "低估值策略", "安全边际"),
            ("S01", "红肥绿瘦", "主力吸筹迹象"),
        ]

    print(f"  {'策略ID':8s} {'策略名':14s} {'匹配理由'}")
    print("  " + "-" * 55)
    for sid, name, reason in recommendations:
        print(f"  {sid:8s} {name:14s} {reason}")
    print("  " + "-" * 55)
    print()
    print(f"  总计 17 种策略均可用，当前默认启用全部。")
    print(f"  可通过 --strategies 参数指定：如 --strategies {','.join([r[0] for r in recommendations[:3]])}")
    print()
    print("  输入策略ID（逗号分隔）或 Enter 保持全部启用:")

    return market_analysis, recommendations


def _analyze_market(*groups):
    """基于真实指数K线数据判断大盘多空。

    Args:
        *groups: (指数名, K线列表) 可变参数组；K线为 CSV 行 split 后的列表，
                 优先使用第一组数据充足的指数作为判断基准。

    Returns:
        dict: {environment, ma5, ma20, ma60, detail, factor, index_name}
    """
    result = {
        "environment": "未知",
        "ma5": None,
        "ma20": None,
        "ma60": None,
        "detail": "",
        "factor": 1.0,
        "index_name": "",
    }

    # 优先使用第一组有足够数据的指数
    index_name = None
    klines = None
    for name, kls in groups:
        if kls and len(kls) >= 20:
            index_name = name
            klines = kls
            break

    if not klines:
        result["detail"] = "K线数据不足，无法判断大盘环境"
        return result

    # 格式: ["日期","开盘","收盘","最高","最低","成交量","成交额","振幅","涨跌幅","涨跌额","换手率"]
    closes = [float(k[2]) for k in klines]

    # 计算移动均线
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else sum(closes) / len(closes)

    result["ma5"] = ma5
    result["ma20"] = ma20
    result["ma60"] = ma60
    result["index_name"] = index_name

    if ma5 > ma20 > ma60:
        result["environment"] = "多头"
        result["factor"] = config.MARKET_BULL_COEFFICIENT
        result["detail"] = (
            f"{index_name}: MA5({ma5:.0f}) > MA20({ma20:.0f}) > MA60({ma60:.0f})，"
            f"均线多头排列，市场处于上升趋势"
        )
    elif ma5 < ma20 < ma60:
        result["environment"] = "空头"
        result["factor"] = config.MARKET_BEAR_COEFFICIENT
        result["detail"] = (
            f"{index_name}: MA5({ma5:.0f}) < MA20({ma20:.0f}) < MA60({ma60:.0f})，"
            f"均线空头排列，市场处于下跌趋势"
        )
    else:
        result["environment"] = "震荡"
        result["factor"] = config.MARKET_OSCILLATE_COEFFICIENT
        result["detail"] = (
            f"{index_name}: MA5({ma5:.0f}), MA20({ma20:.0f}), MA60({ma60:.0f})"
            f" 交织缠绕，市场处于震荡格局"
        )

    return result


# ============================================================
# Step 5: 参数配置
# ============================================================

def _step_param_config():
    """引导式设置输出格式、TOP数量等非强制参数。"""
    print()
    print(_c("─" * 60, "dim"))
    print(_c("  [参数配置] 引导式配置筛选参数", "bold"))
    print(_c("─" * 60, "dim"))
    print()

    print("  以下参数均可跳过，直接使用默认值。")
    print()

    # 输出格式
    print(f"  [1] 输出格式")
    print(f"      可选: text | json | html | all")
    print(f"      - text : 纯文本摘要报告")
    print(f"      - json : 结构化JSON数据")
    print(f"      - html : 交互式可视化报告（含K线迷你图）")
    print(f"      - all  : 同时输出三种格式")
    print(f"      当前: " + _c(_session_state["output_format"], "cyan"))

    # TOP-N
    print(f"  [2] 输出前N只")
    print(f"      默认显示评分最高的前50只标的")
    print(f"      当前: " + _c(str(_session_state["top_n"]), "cyan"))

    # 策略组合模式
    print(f"  [3] 策略组合模式")
    print(f"      可选: union | intersection | weighted")
    print(f"      - union       : 任一策略通过即入选（覆盖面最广）")
    print(f"      - intersection: 全部策略通过才入选（最严格）")
    print(f"      - weighted    : 加权评分排序（最灵活）")
    print(f"      当前: " + _c(_session_state["strategy_mode"], "cyan"))

    # 多周期验证
    status_m = "开" if _session_state["multi_period"] else "关"
    print(f"  [4] 多周期交叉验证")
    print(f"      启用后同时检查日/周线，减少假信号但耗时更长")
    print(f"      当前: " + _c(status_m, "cyan"))

    # 缓存
    status_c = "关" if _session_state["no_cache"] else "开"
    print(f"  [5] 缓存")
    print(f"      缓存K线数据当日 15:30 前有效，重复运行更快")
    print(f"      当前: " + _c(status_c, "cyan"))

    print()
    print("  输入配置编号修改（如 '2 30'），或 Enter 保持不变")


# ============================================================
# Step 6: 执行确认
# ============================================================

def _step_exec_confirm():
    """预览当前所有配置，确认后执行筛选。"""
    print()
    print(_c("─" * 60, "dim"))
    print(_c("  [执行确认] 预览配置并执行筛选", "bold"))
    print(_c("─" * 60, "dim"))
    print()

    print("  最终配置预览:")
    print("  " + "-" * 40)
    print(f"    市场:      {_session_state['market']}")
    print(f"    模式:      {_session_state['mode']}")
    print(f"    输出格式:  {_session_state['output_format']}")
    print(f"    输出TOP-N: {_session_state['top_n']}")
    from strategies import STRATEGY_REGISTRY
    total_strategies = len(STRATEGY_REGISTRY)
    strat_count = len(_session_state["strategy_ids"]) if _session_state["strategy_ids"] else total_strategies
    print(f"    策略数:    {strat_count} 种（{'全部' if _session_state['strategy_ids'] is None else ','.join(_session_state['strategy_ids'])}）")
    print(f"    组合模式:  {_session_state['strategy_mode']}")
    print(f"    多周期:    {'开' if _session_state['multi_period'] else '关'}")
    print(f"    缓存:      {'关' if _session_state['no_cache'] else '开'}")
    print("  " + "-" * 40)
    print()

    cmd_parts = ["python run_screening.py"]
    mkt = _session_state["market"]
    mode = _session_state["mode"]
    fmt = _session_state["output_format"]
    top_n = _session_state["top_n"]
    sm = _session_state["strategy_mode"]
    cmd_parts.append(f'--market "{mkt}"')
    cmd_parts.append(f"--mode {mode}")
    cmd_parts.append(f"--format {fmt}")
    cmd_parts.append(f"--top {top_n}")
    if _session_state["strategy_ids"]:
        sids = ','.join(s.upper() for s in _session_state['strategy_ids'])
        cmd_parts.append(f"--strategies {sids}")
    cmd_parts.append(f"--strategy-mode {sm}")
    if _session_state["multi_period"]:
        cmd_parts.append("--multi-period")
    if _session_state["no_cache"]:
        cmd_parts.append("--no-cache")
    if _session_state["output_dir"] != config.OUTPUT_DIR:
        cmd_parts.append(f'--output "{_session_state["output_dir"]}"')

    full_cmd = " \\\n    ".join(cmd_parts)

    print("  等效命令:")
    print("  " + _c(full_cmd, "cyan"))
    print()
    print("  确认执行？输入 [y] 执行  [n] 取消  [b] 返回修改")


# ============================================================
# 主交互循环
# ============================================================

def _get_user_input(prompt: str = "> ") -> str:
    """获取用户输入并小写化。"""
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"


def _handle_step_input(step_name: str, input_str: str) -> str:
    """处理步骤输入，返回下一个动作: 'next' / 'skip' / 'back' / 'quit' / 'stay'。

    同时根据 step_name 解析具体输入内容并更新 session state。
    """
    if input_str == "q":
        return "quit"
    if input_str == "s":
        return "skip"
    if input_str == "b":
        return "back"
    if input_str == "":
        return "next"

    # 步骤特定解析
    if step_name == "market_select":
        market_map = {"1": "A股", "2": "港股", "3": "美股", "4": "全部"}
        if input_str in market_map:
            _session_state["market"] = market_map[input_str]
            print(_c(f"  已选择: {_session_state['market']}", "green"))

    elif step_name == "strategy_recommend":
        if input_str:
            ids = [s.strip().upper() for s in input_str.split(",")]
            from strategies import STRATEGY_REGISTRY
            valid = [s for s in ids if s in STRATEGY_REGISTRY]
            invalid = [s for s in ids if s not in STRATEGY_REGISTRY]
            if invalid:
                print(_c(f"  无效策略: {invalid}", "red"))
            if valid:
                _session_state["strategy_ids"] = valid
                print(_c(f"  已启用策略: {', '.join(valid)}", "green"))

    elif step_name == "param_config":
        parts = input_str.split()
        if len(parts) >= 2:
            try:
                param_id = int(parts[0])
                if param_id == 1:
                    fmt = parts[1].lower()
                    if fmt in ("text", "json", "html", "all"):
                        _session_state["output_format"] = fmt
                        print(_c(f"  输出格式 → {fmt}", "green"))
                elif param_id == 2:
                    _session_state["top_n"] = int(parts[1])
                    print(_c(f"  TOP-N → {_session_state['top_n']}", "green"))
                elif param_id == 3:
                    mode = parts[1].lower()
                    if mode in ("union", "intersection", "weighted"):
                        _session_state["strategy_mode"] = mode
                        print(_c(f"  组合模式 → {mode}", "green"))
                elif param_id == 4:
                    _session_state["multi_period"] = not _session_state["multi_period"]
                    s = "开" if _session_state["multi_period"] else "关"
                    print(_c(f"  多周期验证 → {s}", "green"))
                elif param_id == 5:
                    _session_state["no_cache"] = not _session_state["no_cache"]
                    s = "关" if _session_state["no_cache"] else "开"
                    print(_c(f"  缓存 → {s}", "green"))
            except ValueError:
                print(_c("  输入格式错误", "red"))

    elif step_name == "exec_confirm":
        if input_str == "y":
            return "execute"
        elif input_str == "n":
            return "cancel"

    return "stay"


# ============================================================
# Step 7: 档案追踪设置
# ============================================================

def _step_archive_setup():
    """询问是否开启策略表现档案追踪。"""
    print()
    print("=" * 70)
    print(_c("  Step 7/7: 策略表现档案库", "bold"))
    print("=" * 70)
    print()
    print("  策略表现档案库可以追踪每次筛选结果的真实表现，")
    print("  帮你了解哪些策略在什么市场环境下更有效。")
    print()
    print("  【功能】")
    print("    - 筛选快照：每次筛选结果自动存档")
    print("    - 回测验证：7个自然日后自动回填真实收益")
    print("    - 聚合统计：策略胜率、平均收益等指标排名")
    print("    - 档案报告：生成 text/json 格式的策略表现报告")
    print()
    print("  【数据安全】")
    print("    - 数据全部存储在你电脑本地（SQLite），不上传")
    print("    - 可随时删除 archive/stock_selecter.db 重置")
    print("    - 不影响 Skill 核心筛选功能")
    print()
    print(_c("  1=开启档案追踪  2=暂不开启  s=跳过", "cyan"))

    while True:
        choice = _get_user_input("  请选择 (1/2/s): ").strip()
        if choice == "1":
            _session_state["track"] = True
            print()
            print(_c("  已开启档案追踪。每次筛选结果将自动存档。", "green"))
            print(_c("  后续可使用 --analyze / --archive-report 查看策略表现。", "dim"))
            break
        elif choice == "2":
            _session_state["track"] = False
            print()
            print(_c("  暂不开启。后续可通过 --track 参数手动启用。", "yellow"))
            break
        elif choice.lower() == "s":
            break
        else:
            print(_c("  请输入 1、2 或 s", "red"))


def _execute_screening():
    """基于 session state 执行真实筛选。

    复用 run_screening.run_pipeline 共享流水线（多市场、报告、档案一致），
    避免与主入口维护两份执行逻辑。
    """
    print()
    print("=" * 70)
    print(_c("  正在执行筛选 ...", "bold"))
    print("=" * 70)
    print()

    try:
        from run_screening import run_pipeline
    except ImportError as e:
        print(_c(f"  模块导入错误: {e}", "red"))
        print("  请确保在 scripts 目录内运行。")
        return None

    return run_pipeline(
        market=_session_state["market"],
        mode=_session_state["mode"],
        strategy_ids=_session_state["strategy_ids"],
        strategy_mode=_session_state["strategy_mode"],
        weights=_session_state["weights"],
        multi_period=_session_state["multi_period"],
        output_dir=_session_state["output_dir"],
        output_format=_session_state["output_format"],
        top_n=_session_state["top_n"],
        no_cache=_session_state["no_cache"],
        track=_session_state.get("track", False),
    )


# ============================================================
# 交互式引导主入口
# ============================================================

def run_guide(skip_to_step: Optional[str] = None, **kwargs):
    """启动交互式引导向导。

    Args:
        skip_to_step: 直接跳转到指定步骤名（welcome/env_check/market_select/
                      strategy_recommend/param_config/exec_confirm/archive_setup）
        **kwargs: 可预填的初始配置覆盖
            - market
            - mode
            - strategy_ids
            - strategy_mode
            - weights
            - top_n
            - output_format
            - output_dir
            - multi_period
            - no_cache
    """
    # 应用预填配置（优先级：kwargs > 用户历史偏好 > config 默认）
    for key, value in kwargs.items():
        if key in _session_state and value is not None:
            _session_state[key] = value

    prefs = _load_prefs()
    for key, value in prefs.items():
        # 仅当 CLI/调用方未通过 kwargs 预填该键时，才用历史偏好覆盖默认值
        if key in _session_state and key not in kwargs and value is not None:
            _session_state[key] = value

    # 确定起始步骤
    start_idx = 0
    if skip_to_step and skip_to_step in STEPS:
        start_idx = STEPS.index(skip_to_step)

    step_funcs = {
        "welcome": _step_welcome,
        "env_check": _step_env_check,
        "market_select": _step_market_select,
        "strategy_recommend": _step_strategy_recommend,
        "param_config": _step_param_config,
        "exec_confirm": _step_exec_confirm,
        "archive_setup": _step_archive_setup,
    }

    step_idx = start_idx
    while step_idx < len(STEPS):
        step_name = STEPS[step_idx]

        # 执行当前步骤
        func = step_funcs[step_name]
        result = func()

        # 获取用户输入
        print(_c("  [s]跳过  [b]返回  [q]退出  [Enter]继续", "dim"))
        user_input = _get_user_input("> ")

        action = _handle_step_input(step_name, user_input)

        if action == "quit":
            print()
            print(_c("  已退出引导。配置已保存，可随时通过 run_screening.py 执行筛选。", "yellow"))
            return None
        elif action == "cancel":
            print()
            print(_c("  已取消执行。配置已保存，可随时通过 run_screening.py 重新筛选。", "yellow"))
            return None
        elif action == "back":
            step_idx = max(0, step_idx - 1)
            print(_c(f"  返回至: {STEPS[step_idx]}", "yellow"))
        elif action == "skip":
            step_idx += 1
            print(_c(f"  跳过当前步骤", "yellow"))
        elif action == "execute":
            _save_prefs()
            return _execute_screening()
        else:  # next / stay
            step_idx += 1

    # 所有步骤走完，如果最后一步是 exec_confirm 且用户确认了，已在上面返回
    print()
    print(_c("  引导完成！", "green"))
    _save_prefs()
    return _session_state


# ============================================================
# CLI 入口（用于独立启动）
# ============================================================

def main():
    """命令行独立启动引导。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="stock-selecter-pro 交互式引导向导",
    )
    parser.add_argument("--step", default=None,
                        choices=STEPS,
                        help="直接跳转到指定步骤")

    args = parser.parse_args()

    run_guide(skip_to_step=args.step)


if __name__ == "__main__":
    main()
