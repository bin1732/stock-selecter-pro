"""
stock-selecter-pro v1.0.3 选股筛选主入口。

集成：批量并发K线获取 → 多策略并行判定 → 组合引擎 → HTML/Text/JSON报告生成。

主流程支持三市场执行：
- A股：全市场列表 + 基本面 + 资金流（完整能力）
- 港股：列表 + 日/周K线（技术面策略可用；无基本面/资金流公开数据）
- 美股：列表 + 日K线（技术面策略可用；无基本面/资金流公开数据；无周K线）

用法:
    python run_screening.py
    python run_screening.py --market A股 --mode full --strategies S01,S03,S05
    python run_screening.py --market 港股 --mode full --strategies S01,S05,S08
    python run_screening.py --market 美股 --strategy-mode weighted --weights "S01=0.2,S05=0.3,S07=0.15"
    python run_screening.py --market 全部 --format html --output ./reports --top 30
    python run_screening.py --multi-period --no-guide

数据源：东方财富公开行情API（push2.eastmoney.com / 79.push2his.eastmoney.com）。
全部为公开接口，不涉及认证，合规合法。
"""

import os
import sys
import time
import json
import random
import argparse
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config


# ── 引导状态检查 ──
def _check_guide_state() -> bool:
    """检查引导状态，决定是否启动交互式引导。

    优先级：
    1. 命令行 --guide / --no-guide 显式覆盖
    2. config.GUIDE_ENABLED 配置
    3. 引导标记文件是否存在（用户选择了 '下次不再显示'）

    Returns:
        bool: 是否应启动引导
    """
    # 检查标记文件
    if config.GUIDE_SKIP_ON_FLAGFILE:
        flag_path = os.path.join(os.path.expanduser("~"), config.GUIDE_FLAGFILE)
        if os.path.exists(flag_path):
            return False
    return config.GUIDE_ENABLED


def _set_guide_done():
    """写入引导完成标记文件。"""
    if config.GUIDE_SKIP_ON_FLAGFILE:
        flag_path = os.path.join(os.path.expanduser("~"), config.GUIDE_FLAGFILE)
        try:
            with open(flag_path, "w", encoding="utf-8") as f:
                f.write(f"done:{datetime.now().isoformat()}")
        except Exception:
            # 引导标记写入失败不阻塞主流程（下次运行仍会重新引导，无副作用）
            pass


# ── 数据层 ──
from data.a_share import (
    fetch_top_a_share_codes,
    fetch_batch_klines_parallel,
    fetch_weekly_kline,
)
from data.fundamental import (
    fetch_fundamental_batch,
    fetch_valuation,
)
from data.money_flow import (
    fetch_stock_money_flow,
)
from data.sector import (
    fetch_industry_ranking,
    fetch_concept_ranking,
)
from data.hk_share import (
    fetch_all_hk_codes,
    fetch_hk_batch_klines,
    fetch_hk_weekly_kline,
)
from data.us_share import (
    fetch_all_us_codes,
    fetch_us_batch_klines,
)

# ── 缓存 ──
from cache import KlineCacheManager

# ── 东财实时/历史接口共享客户端（多节点故障切换）──
from data._http import push2_get, kline_get

# ── 策略 ──
from strategies import (
    STRATEGY_REGISTRY,
)

# ── 历史回放回测 ──
from backtest import collect_signal_returns

# ── 组合引擎 ──
from composers import compose

# ── 报告 ──
from reports import (
    generate_text_report,
    generate_json_report,
    generate_html_report,
)

# ── 档案（可选模块）──
try:
    from archive import log_screening, refresh_performance
    from archive import refresh_strategy_stats, get_strategy_ranking
    from archive import text_archive_report, json_archive_report
    _ARCHIVE_AVAILABLE = True
except ImportError:
    _ARCHIVE_AVAILABLE = False


# 批量K线获取器分发（各市场公开接口的参数与secid前缀不同）
BATCH_FETCHERS = {
    config.MARKET_A: fetch_batch_klines_parallel,
    config.MARKET_HK: fetch_hk_batch_klines,
    config.MARKET_US: fetch_us_batch_klines,
}

# 周K线获取器分发（东方财富公开接口未提供美股周线，如实缺省）
WEEKLY_FETCHERS = {
    config.MARKET_A: fetch_weekly_kline,
    config.MARKET_HK: fetch_hk_weekly_kline,
}


# ============================================================
# 大盘环境判断
# ============================================================

def _fetch_index_klines(secid_mkt: str, secid_code: str, days: int = config.INDEX_KLINE_DAYS) -> list[dict]:
    """获取市场指数K线（上证/深证/恒生/纳指等）。

    Args:
        secid_mkt: 东方财富 secid 市场前缀（如 "1" 沪 / "0" 深 / "100" 指数）
        secid_code: 指数代码（如 "000001" / "HSI" / "IXIC"）
        days: 获取根数

    Returns:
        list[dict]: [{date, close, pct_chg}, ...]；失败返回 []
    """
    data = kline_get("/api/qt/stock/kline/get", params={
        "secid": f"{secid_mkt}.{secid_code}",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1",
        "end": "20500101",
        "lmt": str(days),
    })
    if not data:
        return []

    result = []
    for line in data.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) < 11:
            continue
        result.append({
            "date": parts[0],
            "close": round(float(parts[2]), 2),
            "amount": round(float(parts[6]), 2) if parts[6] != "-" else 0.0,
            "pct_chg": round(float(parts[8]), 2) if parts[8] != "-" else 0.0,
        })
    return result


def _fetch_market_breadth(market: str) -> Optional[dict]:
    """统计指定市场当前涨跌家数（市场宽度）。

    通过 clist 接口分页统计 f3 正负家数，仅对 A股 启用
    （港股/美股标的多、耗时高且无同口径数据声明，如实跳过）。

    Returns:
        dict: {up, down, flat, total, ratio}；失败返回 None
    """
    if market != config.MARKET_A:
        return None
    fs_map = {config.MARKET_A: "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"}
    fs = fs_map.get(market)
    if not fs:
        return None

    up = down = flat = 0
    page = 1
    while True:
        data = push2_get("/api/qt/clist/get", params={
            "pn": str(page), "pz": "1000", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": fs,
            "fields": "f3",
        })
        if not data:
            break
        items = data.get("data", {}).get("diff", [])
        if not items:
            break
        for it in items:
            pct = it.get("f3")
            if pct is None:
                continue
            try:
                pct = float(pct)
            except (TypeError, ValueError):
                continue
            if pct > 0:
                up += 1
            elif pct < 0:
                down += 1
            else:
                flat += 1
        total = data.get("data", {}).get("total", 0)
        if page * 1000 >= total or total == 0:
            break
        page += 1

    if up + down == 0:
        return None
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "total": up + down + flat,
        "ratio": round(up / (up + down), 4),
    }


def _assess_market_environment(market: str = config.DEFAULT_MARKET) -> dict:
    """评估指定市场的大盘环境（真实信号增强）。

    基于对应市场真实指数（A股上证/深证、港股恒生/国企、美股道琼斯/纳指）
    的60日K线，综合三项真实信号：
    - 均线结构（MA5/20/60 方向）
    - 短期动量（近5日累计涨跌幅，动量与均线矛盾时降级为震荡）
    - 量能（近5日均额 / 前20日均额，放量/缩量）
    A股额外统计市场宽度（涨跌家数）。

    Args:
        market: A股 / 港股 / 美股

    Returns:
        dict: {environment, factor, detail, indices, signals, breadth}
    """
    indices_cfg = config.INDEX_SECIDS.get(market, {})
    env = {
        "environment": "未知",
        "factor": 1.0,
        "detail": "",
        "indices": {},
        "signals": {},
        "breadth": None,
    }

    bullish_count = 0
    bearish_count = 0
    total_signals = 0
    details = []

    for code, (name, mkt) in indices_cfg.items():
        klines = _fetch_index_klines(mkt, code, config.INDEX_KLINE_DAYS)
        if len(klines) < 20:
            details.append(f"{name}: K线数据不足")
            continue

        closes = [k["close"] for k in klines]
        amounts = [k.get("amount") or 0 for k in klines]

        # 报告层所需的指数快照
        latest = klines[-1]
        env["indices"][code] = {
            "name": name,
            "price": round(latest["close"], 2),
            "pct_change": round(latest.get("pct_chg", 0), 2),
        }

        # 均线结构方向
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else ma20

        if ma5 > ma20 > ma60:
            direction = "多头"
        elif ma5 < ma20 < ma60:
            direction = "空头"
        else:
            direction = "震荡"

        # 短期动量：近5日累计涨跌幅(%)
        momentum_5d = None
        if len(closes) >= 6 and closes[-6] > 0:
            momentum_5d = round((closes[-1] / closes[-6] - 1) * 100, 2)

        # 量能：近5日均额 / 前20日均额（成交额为0时不可用）
        volume_ratio = None
        recent_amount = [a for a in amounts[-5:] if a > 0]
        base_amount = [a for a in amounts[-config.ENV_VOLUME_MA_DAYS - 5: -5] if a > 0]
        if recent_amount and base_amount and sum(base_amount) > 0:
            volume_ratio = round(
                (sum(recent_amount) / len(recent_amount)) /
                (sum(base_amount) / len(base_amount)), 2,
            )

        # 动量修正：均线多头但近5日明显回调 → 降级震荡；均线空头但近5日明显回升 → 升级多头
        signal_direction = direction
        if direction == "多头" and momentum_5d is not None \
                and momentum_5d <= -config.ENV_MOMENTUM_DOWNGRADE_PCT:
            signal_direction = "震荡"
            details.append(f"{name}: MA多头但近5日{momentum_5d:+.1f}%，动量背离降级")
        elif direction == "空头" and momentum_5d is not None \
                and momentum_5d >= config.ENV_MOMENTUM_DOWNGRADE_PCT:
            signal_direction = "多头"
            details.append(f"{name}: MA空头但近5日{momentum_5d:+.1f}%，反弹信号")
        elif direction == "空头" and momentum_5d is not None \
                and momentum_5d <= -config.ENV_MOMENTUM_DOWNGRADE_PCT:
            signal_direction = "强空头"
            details.append(f"{name}: MA空头且近5日{momentum_5d:+.1f}%，加速下行")

        if signal_direction == "多头":
            bullish_count += 1
        elif signal_direction in ("空头", "强空头"):
            bearish_count += 1

        vol_note = ""
        if volume_ratio is not None:
            vol_note = ("放量" if volume_ratio >= config.ENV_VOLUME_RATIO
                        else ("缩量" if volume_ratio <= 1 / config.ENV_VOLUME_RATIO else "平量"))

        total_signals += 1
        env["signals"][code] = {
            "name": name,
            "direction": signal_direction,
            "ma5": round(ma5, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "momentum_5d": momentum_5d,
            "volume_ratio": volume_ratio,
            "volume_note": vol_note,
        }
        details.append(
            f"{name}: {signal_direction}"
            + (f" (近5日{momentum_5d:+.1f}%," if momentum_5d is not None else " (")
            + (f"量能{volume_ratio:.2f}x{vol_note})" if volume_ratio is not None else ")")
        )

    # 市场宽度（A股）
    breadth = None
    if config.ENV_BREADTH_ENABLED:
        breadth = _fetch_market_breadth(market)
    env["breadth"] = breadth
    if breadth:
        details.append(
            f"涨跌家数 {breadth['up']}/{breadth['down']} "
            f"(上涨占比 {breadth['ratio'] * 100:.1f}%)"
        )

    env["detail"] = "; ".join(details) if details else "无法获取大盘数据"

    if total_signals == 0:
        env["environment"] = "未知"
        env["factor"] = 1.0
    elif bullish_count == total_signals:
        env["environment"] = "多头"
        env["factor"] = config.MARKET_BULL_COEFFICIENT
    elif bearish_count == total_signals:
        env["environment"] = "空头"
        env["factor"] = config.MARKET_BEAR_COEFFICIENT
    else:
        env["environment"] = "震荡"
        env["factor"] = config.MARKET_OSCILLATE_COEFFICIENT

    return env


# ============================================================
# 候选池构建
# ============================================================

def _build_single_market_pool(market: str, mode: str, cap: int) -> list[dict]:
    """构建单一市场的候选池。

    Args:
        market: A股 / 港股 / 美股
        mode: full（全市场候选池，过滤后按公开数据顺序取前cap只；非指数成分精确匹配）
        cap: 候选池上限

    Returns:
        list[dict]: [{code, name, market}, ...]
    """
    if market == config.MARKET_A:
        print(f"  获取A股候选池（按总市值降序前 {cap} 只）...")
        # 市值降序候选池（与港股/美股口径一致）：
        # 替代按当日涨跌幅(f3)排序取前N —— 原实现只覆盖当日涨幅最大的股票，
        # 系统性漏掉回调/横盘/低位等大量符合技术形态的标的，导致结果失真
        filtered = fetch_top_a_share_codes(cap=cap)
        for s in filtered:
            s["market"] = config.MARKET_A
        print(f"  最终候选池: {len(filtered)} 只 (A股, 按总市值降序前{cap})")
        return filtered

    if market == config.MARKET_HK:
        print("  获取港股全市场列表...")
        stocks = fetch_all_hk_codes()
        print(f"  全市场共 {len(stocks)} 只标的")
        # 港股非指数成分匹配，按总市值降序近似采样
        stocks.sort(key=lambda x: x.get("total_mv", 0) or 0, reverse=True)
        stocks = stocks[:cap]
        for s in stocks:
            s["market"] = config.MARKET_HK
        print(f"  最终候选池: {len(stocks)} 只 (港股, 按总市值降序前{cap})")
        return stocks

    if market == config.MARKET_US:
        print("  获取美股全市场列表...")
        stocks = fetch_all_us_codes()
        print(f"  全市场共 {len(stocks)} 只标的")
        stocks.sort(key=lambda x: x.get("total_mv", 0) or 0, reverse=True)
        stocks = stocks[:cap]
        for s in stocks:
            s["market"] = config.MARKET_US
        print(f"  最终候选池: {len(stocks)} 只 (美股, 按总市值降序前{cap})")
        return stocks

    print(f"  错误: 不支持的市场 {market}，可用: {config.SUPPORTED_MARKETS}")
    return []


def _build_candidate_pool(
    market: str,
    mode: str,
    all_cap: Optional[int] = None,
    cap: Optional[int] = None,
) -> list[dict]:
    """构建筛选候选池。

    Args:
        market: A股/港股/美股/全部
        mode: full（全市场候选）
        all_cap: "全部"模式下每市场的取样上限（None 用 config.ALL_MARKET_SAMPLE_CAP，
            用户可通过快速引导/CLI 放大样本以覆盖更多优质标的）
        cap: 单市场候选池上限（None 用 config.MODE_MARKET_CAP；缩小可显著提速，
            适合快速预览/回测场景）

    Returns:
        list[dict]: [{code, name, market}, ...]
    """
    default_cap = config.MODE_MARKET_CAP.get(mode, 1000)
    pool_cap = cap if cap else default_cap

    if market == config.MARKET_ALL:
        pool = []
        per_mkt = all_cap if all_cap else config.ALL_MARKET_SAMPLE_CAP
        for m in (config.MARKET_A, config.MARKET_HK, config.MARKET_US):
            pool.extend(_build_single_market_pool(m, mode, cap=per_mkt))
        print(f"  全部市场候选池合计: {len(pool)} 只 (每市场 {per_mkt})")
        return pool

    if market in (config.MARKET_A, config.MARKET_HK, config.MARKET_US):
        return _build_single_market_pool(market, mode, cap=pool_cap)

    print(f"  错误: 不支持的市场 {market}，可用: {config.SUPPORTED_MARKETS}")
    return []


# ============================================================
# 数据获取（按市场分发）
# ============================================================

def _fetch_klines_by_market(candidates: list[dict], cache_mgr, days: int) -> dict[str, list[dict]]:
    """按市场分组批量获取K线数据（缓存 key 带市场前缀，避免跨市场混淆）。

    Returns:
        dict[str, list[dict]]: code -> K线列表
    """
    by_market = {}
    for s in candidates:
        by_market.setdefault(s["market"], []).append(s["code"])

    results = {}
    for mkt, codes in by_market.items():
        fetcher = BATCH_FETCHERS.get(mkt)
        if not fetcher:
            continue
        batch_size = config.KLINE_BATCH_SIZE
        total_batches = (len(codes) + batch_size - 1) // batch_size
        for batch_idx in range(total_batches):
            batch_codes = codes[batch_idx * batch_size:(batch_idx + 1) * batch_size]
            print(f"  [{mkt}] 批次 {batch_idx + 1}/{total_batches} ({len(batch_codes)} 只)...")

            batch_results = {}
            missing_codes = []
            if cache_mgr:
                for code in batch_codes:
                    cached = cache_mgr.get(f"{mkt}:{code}", days)
                    if cached:
                        batch_results[code] = cached
                    else:
                        missing_codes.append(code)
            else:
                missing_codes = batch_codes

            if missing_codes:
                fetched = fetcher(
                    missing_codes,
                    days=days,
                    max_workers=config.MAX_CONCURRENT_WORKERS,
                    delay=config.REQUEST_INTERVAL,
                )
                batch_results.update(fetched)

                # 更新缓存
                if cache_mgr:
                    for code, kls in fetched.items():
                        if kls:
                            cache_mgr.set(f"{mkt}:{code}", days, kls)

            results.update(batch_results)
            valid_count = sum(1 for kls in batch_results.values() if len(kls) >= 20)
            print(f"    本批有效: {valid_count}/{len(batch_results)}")
    return results


def _fetch_weekly_by_market(by_market_codes: dict[str, list[str]]) -> dict[str, list[dict]]:
    """按市场获取周K线（美股无周线公开接口，如实跳过；并发拉取，避免串行拖慢多周期模式）。"""
    weekly = {}
    tasks = []
    for mkt, codes in by_market_codes.items():
        fetcher = WEEKLY_FETCHERS.get(mkt)
        if not fetcher:
            continue
        print(f"  获取 {mkt} 周线数据 (多周期验证, {len(codes)} 只, 并发)...")
        for code in codes:
            tasks.append((code, fetcher))

    def _fetch_one(task):
        code, fetcher = task
        time.sleep(random.uniform(0, 0.1))
        try:
            wk = fetcher(code, weeks=30)
            if wk and len(wk) >= 10:
                return code, wk
        except Exception:
            pass
        return code, None

    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_WORKERS) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in tasks}
        for future in as_completed(futures):
            code, wk = future.result()
            if wk:
                weekly[code] = wk
    return weekly


def _fetch_fundamental_by_market(
    candidates: list[dict],
    strategy_ids: Optional[list[str]] = None,
) -> dict[str, dict]:
    """按市场获取基本面/估值数据（按策略依赖裁剪，未启用对应策略则跳过，避免无谓请求）。

    - A股：财务摘要（S12/S13/S14 需要）+ 估值（S06/S07 需要）
    - 港股/美股：仅估值（push2 接口返回 PE/PB/股息率/总市值，
      财务摘要无公开数据源，如实缺省 → S12/S13/S14 判定不通过）

    估值来源：
    - 优先使用候选池 clist 批量字段（f9 动态PE / f23 PB / f133 股息率，
      三市场可靠），无需逐只请求，避免 f171 股息率失真。
    - 仅候选池缺失估值字段的标的回退逐只 fetch_valuation（PE/PB 真实，股息率如实 None）。
    """
    by_market = {}
    for s in candidates:
        by_market.setdefault(s["market"], []).append(s)

    selected = set(strategy_ids) if strategy_ids else set(STRATEGY_REGISTRY.keys())
    need_financial = bool(selected & config.FINANCIAL_STRATEGIES)
    need_valuation = bool(selected & config.VALUATION_STRATEGIES)
    if not need_financial and not need_valuation:
        # 纯技术面策略（S01-S05/S08-S11/S15-S17）不依赖基本面/估值
        print("  无需基本面/估值数据（未启用 S06/S07/S12/S13/S14），跳过")
        return {}

    # 候选池估值字典（clist 批量字段）：
    # clist 的 "-" 占位经 safe_float 清洗为 0.0，估值字段如实归一为 None（不把缺失伪造为真实0值）
    pool_valuation = {}
    for s in candidates:
        pe = s.get("pe")
        pb = s.get("pb")
        dy = s.get("dividend_yield")
        if any(v not in (None, 0.0) for v in (pe, pb, dy)):
            pool_valuation[s["code"]] = {
                "code": s["code"],
                # clist f9 为动态PE（push2 f162 为TTM PE，口径不同但同为真实估值；
                # 策略 PE 阈值为绝对值过滤，差异可接受，报告如实标注来源）
                "pe_ttm": None if pe in (None, 0.0) else pe,
                "pb": None if pb in (None, 0.0) else pb,
                "dividend_yield": None if dy in (None, 0.0) else dy,
                "total_mv": s.get("total_mv"),
                "valuation_source": "clist",
            }

    result = {}
    for mkt, stocks in by_market.items():
        codes = [s["code"] for s in stocks]
        if mkt == config.MARKET_A:
            tag = ("财务摘要+估值" if need_financial and need_valuation
                   else ("财务摘要" if need_financial else "估值"))
            print(f"  获取A股{tag}数据 ({len(codes)} 只, 估值用候选池字段)...")
            result.update(
                fetch_fundamental_batch(
                    codes,
                    max_workers=config.MAX_CONCURRENT_WORKERS,
                    market=config.MARKET_A,
                    need_financial=need_financial,
                    need_valuation=need_valuation,
                    pool_valuation=pool_valuation,
                )
            )
        else:
            if not need_valuation:
                print(f"  无需{mkt}估值数据（未启用 S06/S07），跳过")
                continue
            missing = [s["code"] for s in stocks if s["code"] not in pool_valuation]
            for s in stocks:
                if s["code"] in pool_valuation:
                    result[s["code"]] = pool_valuation[s["code"]]
            print(f"  获取{mkt}估值数据 ({len(codes)} 只, 候选池覆盖 {len(codes) - len(missing)} 只)")
            if missing:
                def _fetch_one(code: str):
                    val = fetch_valuation(code, market=mkt)
                    val["code"] = code
                    return code, val

                with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_WORKERS) as ex:
                    futures = {ex.submit(_fetch_one, c): c for c in missing}
                    for future in as_completed(futures):
                        code, val = future.result()
                        result[code] = val
    return result


def _fetch_a_share_money_flow(
    a_codes: list[str],
    strategy_ids: list[str],
) -> dict[str, list]:
    """获取A股资金流数据（抽样并发；仅 S15 依赖资金流，未启用则跳过）。

    港股/美股无对应公开数据源，如实不获取。
    """
    money_flow_data = {}
    if not a_codes:
        return money_flow_data
    if not (set(strategy_ids) & config.MONEY_FLOW_STRATEGIES):
        print("  无需资金流数据（未启用 S15），跳过")
        return money_flow_data

    sample_codes = a_codes[:config.MONEY_FLOW_SAMPLE]
    print(f"  获取A股资金流数据 (抽样 {len(sample_codes)} 只, 并发)...")

    def _fetch_one(code: str):
        try:
            return code, fetch_stock_money_flow(code)
        except Exception:
            # 资金流接口异常：该股如实降级为空数据，相关策略自动判不通过（不伪造）
            return code, []

    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_WORKERS) as ex:
        futures = {ex.submit(_fetch_one, c): c for c in sample_codes}
        for future in as_completed(futures):
            code, mf = future.result()
            money_flow_data[code] = mf
    return money_flow_data


def _warn_strategy_applicability(market: str, strategy_ids: list[str]):
    """对各市场策略数据能力边界给出如实提示（不伪造数据、不静默）。

    真实边界（config 中声明）：
    - 估值类 S06/S07：估值字段（候选池 clist f9/f23/f133，三市场可靠；
      缺失标的回退 push2 stock/get）对 A股/港股/美股 均真实返回 → 三市场可用
    - 财务摘要类 S12/S13/S14：emweb 接口仅 A股 → 港股/美股无公开数据，自动不通过
    - 资金流辅助类 S15：资金流数据仅 A股可获取；港股/美股资金流辅助条件不可用，
      但 S15 核心判定为技术面（长期低位+横盘蓄力），无资金流时仍如实判定、可独立通过
    """
    if market == config.MARKET_A:
        return

    selected = set(strategy_ids)
    # S12/S13/S14 财务摘要无公开数据 → 自动不通过；
    # S15 仅资金流辅助条件不可用（技术面核心条件仍如实判定，不夸大影响）
    lacking = sorted(selected & config.FINANCIAL_STRATEGIES)
    mf_lacking = sorted(selected & config.MONEY_FLOW_STRATEGIES)
    usable_val = sorted(selected & config.VALUATION_STRATEGIES)

    if market == config.MARKET_ALL:
        print("  [提示] 全部市场模式下：港股/美股标的的估值策略(S06/S07)可用（真实估值接口三市场返回），")
        print("         财务摘要(S12/S13/S14)无公开数据自动不通过；"
              "S15(长期蓄力)的资金流辅助条件不可用，技术面核心条件仍如实判定。")
        return

    notes = []
    if usable_val:
        notes.append(f"估值策略 {', '.join(usable_val)} 可用（真实估值字段三市场返回）")
    if lacking:
        notes.append(f"策略 {', '.join(lacking)} 无公开数据，将自动不通过（真实缺数据，不伪造）")
    if mf_lacking:
        notes.append(f"策略 {', '.join(mf_lacking)} 的资金流辅助条件不可用（技术面核心条件仍如实判定）")
    if notes:
        print(f"  [提示] {market}：" + "；".join(notes))
        if lacking:
            print("         建议港股/美股仅使用技术面策略 S01-S05、S08-S11、S15、S16-S17 与估值策略 S06/S07。")


# ============================================================
# 策略执行
# ============================================================

def _run_strategies(
    code: str,
    name: str,
    klines: list[dict],
    fundamental: dict,
    money_flow: dict,
    weekly_klines: Optional[list[dict]],
    strategy_ids: list[str],
    mode: str = "weighted",
    weights: Optional[dict] = None,
) -> dict:
    """对单只股票执行策略组合判定。

    Args:
        code: 股票代码
        name: 股票名称
        klines: 日K线数据
        fundamental: 基本面数据
        money_flow: 资金流数据
        weekly_klines: 周K线数据（多周期验证可选）
        strategy_ids: 启用策略编号列表（大写，如 ['S01','S05']）
        mode: 组合模式 union/intersection/weighted
        weights: 策略权重 dict（仅 weighted 模式生效）

    Returns:
        dict: {code, name, strategy_results, composite_score, passed,
               hit_count, consensus_level, strategy_hits, details}
    """
    composed = compose(
        strategy_ids=strategy_ids,
        klines=klines,
        fundamental=fundamental,
        money_flow=money_flow,
        weekly_klines=weekly_klines,
        mode=mode,
        weights=weights,
    )

    strategy_results = {
        r["id"]: r["result"] for r in composed.get("strategy_results", [])
    }
    strategy_hits = [
        sid for sid, res in strategy_results.items()
        if res.get("passed")
    ]

    # 聚合命中策略的判定理由（去重、截断），供文本/HTML报告展示"为什么入选"；
    # 此前该字段缺失导致报告永远读不到任何理由。
    reasons: list[str] = []
    for sid in strategy_hits:
        for reason in strategy_results.get(sid, {}).get("reasons", []):
            if reason and reason not in reasons:
                reasons.append(reason)

    return {
        "code": code,
        "name": name,
        "strategy_results": strategy_results,
        "composite_score": composed.get("score", 0.0),
        "passed": composed.get("passed", False),
        "hit_count": composed.get("hit_count", 0),
        "consensus_level": composed.get("consensus_level", "低共识"),
        "strategy_hits": strategy_hits,
        "reasons": reasons[:10],
        "details": composed.get("details", []),
    }


# ============================================================
# 共享筛选流水线（run_screening.main 与 guide 引导共用）
# ============================================================

def run_pipeline(
    market: str = config.DEFAULT_MARKET,
    mode: str = config.SCREEN_MODE,
    strategy_ids: Optional[list[str]] = None,
    strategy_mode: str = config.DEFAULT_STRATEGY_MODE,
    weights: Optional[dict] = None,
    multi_period: bool = False,
    output_dir: Optional[str] = None,
    output_format: str = "all",
    top_n: int = config.TOP_N_OUTPUT,
    no_cache: bool = False,
    track: bool = False,
    backtest: bool = False,
    all_cap: Optional[int] = None,
    cap: Optional[int] = None,
) -> dict:
    """执行完整筛选流水线（多市场）。

    Args:
        market: A股/港股/美股/全部
        mode: full（全市场候选）
        strategy_ids: 启用策略列表（None=全部）
        strategy_mode: union/intersection/weighted
        weights: 自定义权重
        multi_period: 是否启用周线确认（美股无周线，自动跳过）
        output_dir: 报告输出目录
        output_format: text/json/html/all
        top_n: 输出前N只
        no_cache: 禁用缓存
        track: 筛选结果存档到策略表现档案库
        backtest: 是否执行策略历史回测（真实K线信号回放）
        all_cap: "全部"市场模式下每市场取样上限
        cap: 单市场候选池上限（覆盖 config.MODE_MARKET_CAP，可用于扩大/缩小候选覆盖）

    Returns:
        dict: {market_env, strategy_stats, results, final_results,
               market_env_map, backtest_results, outlook}
    """
    output_dir = output_dir or config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    if not strategy_ids:
        strategy_ids = list(STRATEGY_REGISTRY.keys())

    start_time = time.time()

    # ------ 1. 大盘环境 ------
    print("\n[1/5] 评估大盘环境...")
    if market == config.MARKET_ALL:
        markets = [config.MARKET_A, config.MARKET_HK, config.MARKET_US]
    else:
        markets = [market]
    market_env_map = {}
    for m in markets:
        env = _assess_market_environment(m)
        market_env_map[m] = env
        print(f"  {m} 大盘: {env['environment']} | 系数: {env['factor']}")

    if market != config.MARKET_ALL:
        market_env = market_env_map[market]
    else:
        # 全部市场：报告主环境取A股基准，指数与细节合并三市场
        market_env = dict(market_env_map[config.MARKET_A])
        indices = {}
        for m, e in market_env_map.items():
            indices.update(e.get("indices", {}))
        market_env["indices"] = indices
        market_env["detail"] = "; ".join(
            f"{m}: {e['environment']}" for m, e in market_env_map.items()
        )

    # ------ 2. 候选池 ------
    print("\n[2/5] 构建候选股票池...")
    candidates = _build_candidate_pool(market, mode, all_cap=all_cap, cap=cap)
    if not candidates:
        print("  错误: 候选池为空")
        return {
            "market_env": market_env,
            "market_env_map": market_env_map,
            "strategy_stats": {},
            "results": [],
            "final_results": [],
            "backtest_results": [],
            "outlook": [],
        }

    # 如实记录当前实际数据通道（主节点/官方延迟节点），随报告展示
    # （须在候选池构建后记录：列表接口已真实请求，节点信息才有依据）
    from data._http import current_host_label
    market_env["data_channel"] = current_host_label()

    codes = [s["code"] for s in candidates]
    code_name_map = {s["code"]: s["name"] for s in candidates}
    code_market_map = {s["code"]: s["market"] for s in candidates}

    _warn_strategy_applicability(market, strategy_ids)

    # 数据通道如实提示（延迟节点下部分能力真实受限，明确告知用户）
    dc_label = market_env.get("data_channel", "")
    if "延迟节点" in dc_label:
        print(f"  [提示] 当前数据通道: {dc_label}。")
        print("         延迟节点下：美股候选池可能仅覆盖部分标的、个股资金流历史可能仅最近1日，")
        print("         相关策略将按实际返回数据如实判定，不伪造、不静默。")

    # ------ 3. 批量获取K线 ------
    print(f"\n[3/5] 批量获取K线数据 (共 {len(codes)} 只)...")
    cache_mgr = KlineCacheManager() if not no_cache else None

    klines_start = time.time()
    klines_data = _fetch_klines_by_market(candidates, cache_mgr, config.KLINE_DAYS)
    elapsed_klines = time.time() - klines_start
    valid_codes = [c for c in codes if c in klines_data and len(klines_data[c]) >= 20]
    print(f"  K线获取完成: {len(valid_codes)}/{len(codes)} 只有效, 耗时 {elapsed_klines:.1f}s")

    # 如实记录K线实际数据通道（东财 push2his / 腾讯备选通道），随报告展示
    from data._http import current_kline_host_label
    kline_channel = current_kline_host_label()
    if kline_channel:
        market_env["kline_channel"] = kline_channel
        print(f"  [提示] K线数据通道: {kline_channel}。")

    if len(valid_codes) < 10:
        print("  错误: 有效K线数据过少，终止")
        # 如实提示可能原因（历史K线接口不可达 / 缓存为空 / 标的无K线）
        if not any(klines_data.values()):
            print("  提示: K线数据获取失败（push2his 多节点与腾讯备选通道均不可达），且本地缓存为空。")
            print("        请检查网络后重试；此前已获取并缓存的数据将自动复用。")
        return {
            "market_env": market_env,
            "market_env_map": market_env_map,
            "strategy_stats": {},
            "results": [],
            "final_results": [],
            "backtest_results": [],
            "outlook": [],
        }

    # 多周期K线（可选；美股无周线接口，如实跳过）
    weekly_klines_all = {}
    if multi_period:
        by_mkt_valid = {}
        for code in valid_codes:
            by_mkt_valid.setdefault(code_market_map.get(code, config.MARKET_A), []).append(code)
        us_codes = by_mkt_valid.pop(config.MARKET_US, [])
        if us_codes:
            print(f"  提示: 东方财富公开接口未提供美股周K线，美股 {len(us_codes)} 只标的跳过周线确认")
        weekly_klines_all = _fetch_weekly_by_market(by_mkt_valid)
        print(f"  周线有效: {len(weekly_klines_all)}/{len(valid_codes)} 只")

    # ------ 4. 并行策略判定 ------
    print(f"\n[4/5] 执行策略判定 ({len(strategy_ids)} 种策略 × {len(valid_codes)} 只)...")

    # 基本面/估值：A股全量（财务摘要+估值），港股/美股仅估值（S06/S07 真实可用）；
    # 资金流仅A股可获取；港股/美股标的如实使用空数据（策略内部判定为不通过）
    valid_candidates = [s for s in candidates if s["code"] in valid_codes]
    fundamental_data = _fetch_fundamental_by_market(valid_candidates, strategy_ids)
    a_codes = [c for c in valid_codes if code_market_map.get(c) == config.MARKET_A]
    money_flow_data = _fetch_a_share_money_flow(a_codes, strategy_ids)

    strategy_start = time.time()
    all_results = []

    def _evaluate_one(code):
        klines = klines_data.get(code, [])
        fund = fundamental_data.get(code, {})
        mf = money_flow_data.get(code, {})
        wk = weekly_klines_all.get(code)
        name = code_name_map.get(code, "")
        mkt = code_market_map.get(code, config.MARKET_A)

        result = _run_strategies(
            code, name, klines, fund, mf, wk, strategy_ids,
            mode=strategy_mode, weights=weights,
        )
        # 应用对应市场的大盘环境系数（全部市场模式下各市场独立）
        env = market_env_map.get(mkt, market_env)
        result["composite_score"] = round(
            result["composite_score"] * env["factor"], 2
        )
        # 报告层兼容字段
        result["score"] = result["composite_score"]
        result["recent_pcts"] = [k.get("pct_chg", 0) for k in klines[-20:]]
        result["industry"] = "未知"
        result["market"] = mkt
        # 供档案追踪回填快照价使用（策略详情未记录收盘价时的回退值）
        result["latest_close"] = klines[-1]["close"] if klines else 0
        return result

    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_WORKERS) as executor:
        futures = {executor.submit(_evaluate_one, c): c for c in valid_codes}
        completed = 0
        failed_count = 0
        for future in as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
            except Exception:
                # 单股评估异常：如实跳过该股（数据异常导致策略内部错误），统计缺失数量
                failed_count += 1
            completed += 1
            if completed % 50 == 0:
                print(f"  进度: {completed}/{len(valid_codes)}")
    if failed_count:
        print(f"  提示: {failed_count} 只标的评估异常被跳过（如实缺失，不伪造结果）")

    strategy_elapsed = time.time() - strategy_start
    print(f"  策略判定完成: {len(all_results)} 只, 耗时 {strategy_elapsed:.1f}s")

    # ------ 5. 组合结果筛选 & 报告生成 ------
    print("\n[5/5] 组合结果筛选 & 报告生成...")

    # 组合判定已在单股维度通过 compose() 完成，此处按通过状态过滤并排序
    final_results = [r for r in all_results if r.get("passed")]
    passed_total = len(final_results)  # 截断前的真实通过总数（报告如实标注）
    final_results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    final_results = final_results[: top_n]
    print(f"  组合模式: {strategy_mode} | 通过: {len(final_results)} 只")

    # 合并行业信息（真实数据，如实标注）：
    # 1) 候选池接口（f100 行业字段）→ 覆盖候选池内全部A股标的（主映射）
    # 2) 行业/概念排行领涨股代码 → 补充映射（覆盖候选池外的领涨股）
    # 行业合并采用"候选池主映射 + 领涨股补充映射"，覆盖候选池外领涨股。
    # 港股/美股无对应行业字段，保持"未知"，如实标注。
    pool_industry_map = {
        s["code"]: s.get("industry", "") for s in candidates if s.get("industry")
    }

    if config.MARKET_A in markets:
        print("  获取板块排行数据...")
        try:
            industry_ranking = fetch_industry_ranking()
        except Exception:
            industry_ranking = []

        try:
            concept_ranking = fetch_concept_ranking()
        except Exception:
            concept_ranking = []
    else:
        industry_ranking = []
        concept_ranking = []

    industry_map = {
        it.get("lead_stock_code"): it.get("name", "")
        for it in industry_ranking if it.get("lead_stock_code")
    }
    concept_map = {
        it.get("lead_stock_code"): it.get("name", "")
        for it in concept_ranking if it.get("lead_stock_code")
    }
    for r in final_results:
        code = r.get("code")
        if not code:
            continue
        if pool_industry_map.get(code):
            r["industry"] = pool_industry_map[code]
        elif industry_map.get(code):
            r["industry"] = industry_map[code]
        elif concept_map.get(code):
            r["industry"] = concept_map[code]

    # 趋势推演（真实数据驱动：指数信号 + 板块实时涨幅排行，条件式合规措辞）
    outlook = _build_trend_outlook(market_env, industry_ranking, concept_ranking)
    market_env["outlook"] = outlook

    # ── 策略历史回测（真实K线信号回放，可选）──
    backtest_results = []
    if backtest:
        for m in markets:
            res = run_market_backtest(
                market=m,
                strategy_ids=strategy_ids,
                valid_candidates=valid_candidates,
                output_dir=output_dir,
                cache_mgr=cache_mgr,
            )
            if res:
                backtest_results.append(res)
    backtest_data = {res["market"]: res for res in backtest_results}

    # 生成报告
    report_files = []

    # 策略统计
    strategy_stats = {}
    for sid in strategy_ids:
        hit_count = 0
        for r in all_results:
            sr = r.get("strategy_results", {}).get(sid, {})
            if sr.get("passed"):
                hit_count += 1
        strategy_stats[sid] = {
            "name": STRATEGY_REGISTRY.get(sid, {}).get("name", sid),
            "passed": hit_count,
            "total": len(all_results),
        }

    # Text 报告
    if output_format in ("text", "all"):
        text_path = generate_text_report(final_results, output_dir, market_env, strategy_stats, passed_total)
        report_files.append(("Text", text_path))

    # JSON 报告
    if output_format in ("json", "all"):
        json_path = generate_json_report(final_results, output_dir, market_env, strategy_stats, passed_total)
        report_files.append(("JSON", json_path))

    # HTML 报告
    if output_format in ("html", "all"):
        html_path = generate_html_report(
            final_results, output_dir, market_env, strategy_stats, backtest_data, passed_total
        )
        report_files.append(("HTML", html_path))

    # ------ 输出摘要 ------
    print("\n" + "-" * 70)
    for fmt, path in report_files:
        print(f"  [{fmt}] {path}")

    # 大盘环境信号表（真实数据可视化）
    sig_rows = []
    for code, sig in market_env.get("signals", {}).items():
        mom = sig.get("momentum_5d")
        mom_str = f"{mom:+.2f}%" if mom is not None else "-"
        vr = sig.get("volume_ratio")
        vol_str = sig.get("volume_note", "-") + (f"({vr:.2f}x)" if vr is not None else "")
        sig_rows.append([sig.get("name", code), f"MA{sig.get('direction', '-')}", mom_str, vol_str])
    if sig_rows:
        print(f"\n  [{market}] 大盘信号表（均线结构/动量/量能）:")
        print(_fmt_table(["指数", "均线结构", "近5日动量", "量能"], sig_rows))
    breadth = market_env.get("breadth")
    if breadth:
        print(f"  市场宽度: 上涨 {breadth['up']} / 下跌 {breadth['down']} / 平 {breadth['flat']} "
              f"(上涨占比 {breadth['ratio'] * 100:.1f}%)")

    print(f"\n  总耗时: {time.time() - start_time:.1f}s")
    print(f"  最终通过: {len(final_results)} 只")
    dc = market_env.get("data_channel")
    if dc:
        print(f"  数据通道: {dc}")

    if final_results:
        top_rows = []
        for i, r in enumerate(final_results[:10]):
            code = r.get("code", "")
            name = r.get("name", "")
            score = r.get("composite_score", 0)
            hits = r.get("strategy_hits", [])
            mkt = r.get("market", "")
            top_rows.append([str(i + 1), mkt, code, name, f"{score:.1f}", ", ".join(hits[:3])])
        print(f"\n  ** TOP{len(top_rows)} 结果表:")
        print(_fmt_table(["#", "市场", "代码", "名称", "评分", "命中策略"], top_rows))
        print(f"  （完整列表见报告文件，共 {len(final_results)} 只通过）")

    print("-" * 70)
    print("\n  以上结果仅供技术分析参考，不构成投资建议。股市有风险，投资需谨慎。")

    # ── 筛选结果存档 ──
    if track and _ARCHIVE_AVAILABLE:
        _do_archive_tracking(
            market=market,
            mode=mode,
            strategy_ids=strategy_ids,
            candidates_count=len(candidates),
            final_results=final_results,
        )

    return {
        "market_env": market_env,
        "market_env_map": market_env_map,
        "strategy_stats": strategy_stats,
        "results": all_results,
        "final_results": final_results,
        "backtest_results": backtest_results,
        "outlook": outlook,
    }


# ============================================================
# 主流程
# ============================================================

def _quick_prompt(args):
    """终端交互环境下的轻量市场确认（每次运行的合规引导，可跳过）。

    在用户未显式指定 --market 且不处于 --no-guide 模式时，
    于交互终端中询问目标市场；非交互环境（管道/脚本调用）自动跳过。
    """
    if args.no_guide or not sys.stdin.isatty():
        return
    if args.market is not None:
        return

    print("=" * 70)
    print("  stock-selecter-pro 每次运行引导")
    print("  · 数据来源: 东方财富公开行情API（真实数据，非Level-2实时）")
    print("  · 请选择本次筛选的目标市场：")
    print("    [1] A股   [2] 港股   [3] 美股")
    print("    [4] 全部市场（每市场取样200只，耗时适中）")
    print("    [5] 全部市场·加大样本（每市场500只，覆盖更全，耗时更长）")
    print("  · 输入 'q' 退出，Enter 使用默认(A股)")
    print("=" * 70)
    try:
        choice = input("  请选择市场: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("  未输入，使用默认市场 A股")
        return
    if choice == "q":
        sys.exit(0)
    if choice == "5":
        args.market = config.MARKET_ALL
        args.all_cap = 500
        print("  已选择: 全部市场（每市场取样500只）")
        return
    market_map = {"1": config.MARKET_A, "2": config.MARKET_HK,
                  "3": config.MARKET_US, "4": config.MARKET_ALL}
    if choice in market_map:
        args.market = market_map[choice]
        print(f"  已选择: {args.market}")
    else:
        args.market = config.DEFAULT_MARKET
        print(f"  输入无效，使用默认市场: {args.market}")


def main():
    parser = argparse.ArgumentParser(
        description=f"stock-selecter-pro {config.VERSION} 多策略量化选股工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_screening.py --market A股 --mode full
  python run_screening.py --market 港股 --strategies S01,S05,S08
  python run_screening.py --market 美股 --strategy-mode union
  python run_screening.py --market 全部 --format html --output ./reports
  python run_screening.py --strategy-mode weighted --weights "S01=0.2,S05=0.3"
  python run_screening.py --multi-period --no-guide
        """,
    )

    parser.add_argument("--market", default=None,
                        choices=config.SUPPORTED_MARKETS,
                        help="目标市场: A股/港股/美股/全部 (默认: A股)")
    parser.add_argument("--mode", default=config.SCREEN_MODE,
                        choices=["full"],
                        help="筛选范围: full=全市场候选 (默认: %(default)s)")
    parser.add_argument("--strategies", default=None,
                        help="指定策略ID，逗号分隔 (默认: 全部)。如: S01,S03,S05")
    parser.add_argument("--strategy-mode", default=config.DEFAULT_STRATEGY_MODE,
                        choices=["union", "intersection", "weighted"],
                        help="策略组合模式 (默认: %(default)s)")
    parser.add_argument("--weights", default=None,
                        help="权重配置，格式: s01=0.2,s05=0.3 (仅weighted模式)")
    parser.add_argument("--multi-period", action="store_true",
                        help="启用多周期验证 (日+周线确认; 美股无周线自动跳过)")
    parser.add_argument("--output", default=None,
                        help="报告输出目录 (默认: config.OUTPUT_DIR)")
    parser.add_argument("--format", default="all",
                        choices=["text", "json", "html", "all"],
                        help="报告输出格式 (默认: all)")
    parser.add_argument("--no-cache", action="store_true",
                        help="禁用缓存")
    parser.add_argument("--top", type=int, default=config.TOP_N_OUTPUT,
                        help="输出前N只标的 (默认: %(default)s)")
    parser.add_argument("--guide", action="store_true", default=None,
                        help="强制启动新用户引导向导")
    parser.add_argument("--no-guide", action="store_true", default=None,
                        help="跳过引导，直接执行筛选")
    parser.add_argument("--track", action="store_true", default=None,
                        help="筛选完成后将结果存档，用于后续回测跟踪")
    parser.add_argument("--analyze", action="store_true", default=None,
                        help="回填持仓收益并刷新策略统计（可与 --track 组合）")
    parser.add_argument("--archive-report", action="store_true", default=None,
                        help="仅生成档案报告（不执行筛选，与 --track 互斥）")
    parser.add_argument("--backtest", action="store_true", default=None,
                        help="筛选后执行策略历史回测（真实K线信号回放，输出真实胜率与平均收益）")
    parser.add_argument("--all-cap", type=int, default=None,
                        help="\"全部\"市场模式下每市场取样上限 (默认: 200；放大可覆盖更多标的，耗时增加)")
    parser.add_argument("--cap", type=int, default=None,
                        help="单市场候选池上限（默认按 config.MODE_MARKET_CAP=1000；"
                             "放大如 3000 可覆盖更多市值靠后的标的，筛选更全但耗时更长）")

    args = parser.parse_args()

    # 注意：args.market 保持 None（用户未显式指定）直到 _quick_prompt 之后，
    # 以便区分"用户明确选择"与"默认值"（--market 默认 A股）。

    # ── 参数互斥校验 ──
    if args.track and args.archive_report:
        print("错误: --track 与 --archive-report 互斥，请二选一")
        return

    # ── 参数合法性校验 ──
    if args.top is not None and args.top <= 0:
        print("错误: --top 必须为正整数")
        return

    # ── 独立档案报告模式 ──
    if args.archive_report:
        _run_archive_report(args.output or config.OUTPUT_DIR, args.format)
        return

    # ── 引导状态决策 ──
    should_guide = _check_guide_state()
    if args.guide:
        should_guide = True
    if args.no_guide:
        should_guide = False

    if should_guide:
        # 非交互环境（管道/脚本/Agent 自动化调用）不启动 7 步向导：
        # 交互向导依赖 stdin 实时输入，自动化场景下会阻塞等待，拖慢执行。
        if not sys.stdin.isatty():
            print("  检测到非交互环境，跳过交互式引导，直接执行筛选（--guide 可强制启动）")
            should_guide = False
        else:
            print("=" * 70)
            print("  检测到新用户，启动交互式引导向导 ...")
            print("  提示: 随时输入 'q' 退出引导，使用 --no-guide 跳过")
            print("=" * 70)
            try:
                from guide import run_guide
                # 引导收口约定：
                # - 引导走完全部步骤或 exec_confirm 确认后，内部已完成筛选并输出报告（返回非 None），
                #   此处写"下次跳过"标记并直接返回，避免与下方 run_pipeline 重复执行（双重执行）；
                # - 用户 q 退出 / n 取消返回 None → 尊重用户选择：不写标记、不执行默认筛选。
                guide_result = run_guide(market=args.market)
                if guide_result is not None:
                    _set_guide_done()
                return
            except ImportError as e:
                print(f"  引导模块加载失败: {e}，直接进入筛选流程")
            except (EOFError, KeyboardInterrupt):
                print("\n  引导已中断，进入筛选流程")
            print()

    # ── 每次运行的轻量市场询问（非首次用户，交互终端下）──
    if not should_guide:
        _quick_prompt(args)

    output_dir = args.output or config.OUTPUT_DIR

    # ── 档案分析（在筛选前执行收益回填 + 统计刷新）──
    if args.analyze and _ARCHIVE_AVAILABLE:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               config.ARCHIVE_DB_PATH)
        if os.path.exists(db_path):
            print("\n  [分析] 回填持仓收益...")
            perf_result = refresh_performance(db_path)
            print(f"    检查: {perf_result['checked']} 条 | "
                  f"1周: {perf_result['updated_1w']} | "
                  f"1月: {perf_result['updated_1m']} | "
                  f"失败: {perf_result['failed']}")
            print("  [分析] 刷新策略统计...")
            refresh_strategy_stats(db_path)
            print("    策略统计已刷新")
        else:
            print("\n  [分析] 档案数据库尚未创建，跳过")

    # 解析策略列表
    if args.strategies:
        strategy_ids = [s.strip().upper() for s in args.strategies.split(",")]
        # 校验策略ID
        valid_ids = set(STRATEGY_REGISTRY.keys())
        invalid = [s for s in strategy_ids if s not in valid_ids]
        if invalid:
            print(f"  警告: 无效策略ID {invalid}，已忽略")
        strategy_ids = [s for s in strategy_ids if s in valid_ids]
        if not strategy_ids:
            # 全部无效时如实提示并回退全部，避免静默"启用全部"造成误解
            print("  警告: 未指定任何有效策略ID，将启用全部策略")
            strategy_ids = None
    else:
        strategy_ids = None

    # 解析权重（大写标准化，与 STRATEGY_REGISTRY 键一致）
    weights = None
    if args.weights:
        weights = {}
        for pair in args.weights.split(","):
            try:
                k, v = pair.strip().split("=")
            except ValueError:
                print(f"  警告: 权重格式错误 '{pair}'，应为 k=v 形式")
                continue
            try:
                weights[k.strip().upper()] = float(v.strip())
            except ValueError:
                print(f"  警告: 权重值非法 '{v}'，已忽略")
        if not weights:
            print("  警告: 未解析到有效权重，回退为默认等权")
            weights = None

    print("=" * 70)
    print(f"   stock-selecter-pro {config.VERSION} 多策略量化选股")
    print(f"   启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _market = args.market or config.DEFAULT_MARKET
    print(f"   市场: {_market} | 模式: {args.mode} | 策略数: {len(strategy_ids) if strategy_ids else len(STRATEGY_REGISTRY)}")
    print(f"   组合模式: {args.strategy_mode} | 多周期: {'开' if args.multi_period else '关'}")
    print(f"   缓存: {'关' if args.no_cache else '开'} | 输出TOP: {args.top}")
    print("=" * 70)

    run_pipeline(
        market=_market,
        mode=args.mode,
        strategy_ids=strategy_ids,
        strategy_mode=args.strategy_mode,
        weights=weights,
        multi_period=args.multi_period,
        output_dir=output_dir,
        output_format=args.format,
        top_n=args.top,
        no_cache=args.no_cache,
        track=bool(args.track),
        backtest=bool(args.backtest),
        all_cap=args.all_cap,
        cap=args.cap,
    )


def _run_archive_report(output_dir: str, fmt: str = "all"):
    """独立档案报告模式：不执行筛选，仅生成回测档案报告。"""
    if not _ARCHIVE_AVAILABLE:
        print("错误: archive 模块不可用")
        return

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           config.ARCHIVE_DB_PATH)
    if not os.path.exists(db_path):
        print(f"档案数据库尚未创建: {db_path}")
        print("请先执行至少一次 --track 筛选以初始化数据库。")
        return

    if fmt == "html":
        print("提示: 档案报告仅支持 text/json 两种格式，--format html 已忽略（等价 text）")
        fmt = "text"

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 先刷新收益和统计
    print("回填持仓收益...")
    perf = refresh_performance(db_path)
    print(f"  检查: {perf['checked']} | 1周: {perf['updated_1w']} | "
          f"1月: {perf['updated_1m']} | 失败: {perf['failed']}")
    print("刷新策略统计...")
    refresh_strategy_stats(db_path)

    if fmt in ("text", "all"):
        text_report = text_archive_report(db_path)
        text_path = os.path.join(output_dir, f"档案报告_{timestamp}.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text_report)
        print(f"\n{text_report}")
        print(f"\n[Text] {text_path}")

    if fmt in ("json", "all"):
        json_report = json_archive_report(db_path)
        json_path = os.path.join(output_dir, f"档案报告_{timestamp}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_report, f, ensure_ascii=False, indent=2)
        print(f"[JSON] {json_path}")

        # 打印摘要
        summary = json_report.get("screening_summary", {})
        ranking = json_report.get("strategy_ranking", [])
        print(f"\n数据覆盖: {summary.get('total_runs', 0)} 次筛选, "
              f"{summary.get('total_picks', 0)} 只入选")
        if ranking:
            print("TOP3 策略（按1月胜率）:")
            for item in ranking[:3]:
                mv = item.get("metric_value")
                wr = f"{mv*100:.1f}%" if mv else "N/A"
                print(f"  {item.get('strategy_id', '?')}: {wr}")


def _do_archive_tracking(market, mode, strategy_ids, candidates_count, final_results):
    """执行筛选结果存档。"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           config.ARCHIVE_DB_PATH)
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    passed_count = len(final_results)

    print(f"\n  存档筛选结果 (run_id: {run_id})...")
    try:
        log_screening(
            db_path=db_path,
            run_id=run_id,
            market=market,
            strategy_ids=strategy_ids,
            mode=mode,
            candidate_count=candidates_count,
            passed_count=passed_count,
            results=final_results,
        )
        print(f"  存档完成: {passed_count} 只标的已记录到 pick_performance")

        # 先刷新策略统计，再输出排名（否则排名基于上次快照，恒过期）
        refresh_strategy_stats(db_path)
        ranking = get_strategy_ranking(db_path)
        if ranking:
            print("  当前策略排名（1月胜率）:")
            for item in ranking[:5]:
                mv = item.get("metric_value")
                wr = f"{mv*100:.1f}%" if mv else "N/A"
                print(f"    {item.get('strategy_id', '?')}: {wr} "
                      f"(运行 {item.get('total_runs', 0)} 次)")
    except Exception as e:
        print(f"  存档失败: {e}")


# ============================================================
# 终端 ASCII 表格（可视化输出，替代纯文字）
# ============================================================

def _fmt_table(headers: list, rows: list[list], max_col_width: int = 28) -> str:
    """生成对齐的 ASCII 表格文本（终端/回测报告通用）。

    Args:
        headers: 表头列表
        rows: 行数据（每行与表头等长）
        max_col_width: 单列最大宽度（超长截断，确保表格不溢出）

    Returns:
        str: 表格文本（含边框与分隔线）
    """
    str_rows = [[str(c) if c is not None else "-" for c in row] for row in rows]
    widths = []
    for c in range(len(headers)):
        w = max([len(str(headers[c]))] + [len(r[c]) for r in str_rows])
        widths.append(min(w + 2, max_col_width))

    def _line() -> str:
        return "+" + "+".join("-" * w for w in widths) + "+"

    def _fmt(row: list) -> str:
        cells = []
        for i, cell in enumerate(row):
            txt = cell[: max_col_width - 2] if len(cell) > max_col_width - 2 else cell
            cells.append(txt.ljust(widths[i]))
        return "|" + "|".join(cells) + "|"

    lines = [_line(), _fmt([str(h) for h in headers]), _line()]
    for row in str_rows:
        lines.append(_fmt(row))
    lines.append(_line())
    return "\n".join(lines)


# ============================================================
# 策略历史回测（真实K线信号回放，非虚构）
# ============================================================

def _sample_backtest_stocks(valid_candidates: list[dict], market: str, n: int) -> list[dict]:
    """按候选池顺序等间隔抽样回测标的（市值分层近似，避免只测高分标的的选择偏差）。"""
    mkt = [s for s in valid_candidates if s["market"] == market]
    if len(mkt) <= n:
        return mkt
    step = len(mkt) / n
    picked = []
    for k in range(n):
        idx = min(int((k + 0.5) * step), len(mkt) - 1)
        picked.append(mkt[idx])
    return picked


def _fetch_backtest_klines(sample: list[dict], cache_mgr=None) -> dict[str, list[dict]]:
    """获取回测用长历史日K线（BACKTEST_HISTORY_DAYS 日，缓存 key 带市场前缀与天数）。"""
    by_market = {}
    for s in sample:
        by_market.setdefault(s["market"], []).append(s["code"])

    result = {}
    for mkt, codes in by_market.items():
        fetcher = BATCH_FETCHERS.get(mkt)
        if not fetcher:
            continue
        for i in range(0, len(codes), 20):
            batch = codes[i:i + 20]
            missing_codes = []
            if cache_mgr:
                # 优先读缓存，未命中才请求（与主流程 K 线缓存一致）
                for code in batch:
                    cached = cache_mgr.get(f"{mkt}:{code}", config.BACKTEST_HISTORY_DAYS)
                    if cached:
                        result[code] = cached
                    else:
                        missing_codes.append(code)
            else:
                missing_codes = batch
            if not missing_codes:
                continue
            fetched = fetcher(
                missing_codes,
                days=config.BACKTEST_HISTORY_DAYS,
                max_workers=config.MAX_CONCURRENT_WORKERS,
                delay=config.REQUEST_INTERVAL,
            )
            if cache_mgr:
                for code, kls in fetched.items():
                    if kls:
                        cache_mgr.set(f"{mkt}:{code}", config.BACKTEST_HISTORY_DAYS, kls)
            result.update(fetched)
    return result


def _bt_summarize(returns: list[float], min_signals: int) -> Optional[dict]:
    """从收益列表统计胜率/平均收益；样本不足返回 None（如实标注）。"""
    if len(returns) < min_signals:
        return None
    win = sum(1 for r in returns if r > 0)
    return {
        "samples": len(returns),
        "win_rate": round(win / len(returns), 4),
        "avg_return": round(sum(returns) / len(returns), 4),
    }


def run_market_backtest(
    market: str,
    strategy_ids: list[str],
    valid_candidates: list[dict],
    output_dir: str,
    cache_mgr=None,
) -> Optional[dict]:
    """对指定市场执行策略历史回测（真实K线信号回放，输出真实胜率）。

    真实性说明（如实标注，不修饰）：
    - 技术面策略（S01-S05/S08-S11/S16-S17）：信号在历史K线上逐日完整重放，无前视偏差。
    - 估值策略（S06/S07）：估值取当前快照（历史估值无公开数据源），
      信号频率受当前估值影响，报告明确标注快照偏差，不作为历史胜率依据。
    - 全部回测基于当前仍在交易标的的历史K线，存在幸存者偏差；
      样本为同一标的多信号（非独立），胜率为历史统计，不代表未来。

    Returns:
        dict: {market, strategies: [...], report_path} 或 None（样本为空）
    """
    sample = _sample_backtest_stocks(valid_candidates, market, config.BACKTEST_SAMPLE_PER_MARKET)
    if not sample:
        return None

    print(f"\n[回测] {market}：抽样 {len(sample)} 只，获取 {config.BACKTEST_HISTORY_DAYS} 日历史K线...")
    bt_klines = _fetch_backtest_klines(sample, cache_mgr)
    valid_bt = [
        s for s in sample
        if s["code"] in bt_klines
        and len(bt_klines[s["code"]]) >= config.BACKTEST_WINDOW + 40
    ]
    if not valid_bt:
        print("[回测] 无足够历史K线标的，跳过")
        return None
    print(f"[回测] 有效标的 {len(valid_bt)} 只，获取估值快照（估值策略用）...")

    # 估值快照（港股/美股仅估值，A股全量）——估值策略判定需要
    # （传入 strategy_ids 触发依赖裁剪，回测按需拉取估值）
    fund_snapshot = _fetch_fundamental_by_market(valid_bt, strategy_ids)

    print(f"[回测] 逐日信号回放 {len(strategy_ids)} 策略 × {len(valid_bt)} 只...")
    merged = {}
    for sid in strategy_ids:
        merged[sid] = {hold: [] for hold in config.BACKTEST_HOLD_DAYS}
        merged[sid]["covered"] = 0

    def _bt_one(sid: str, code: str, klines: list[dict], fund: dict):
        col = collect_signal_returns(sid, klines, fundamental=fund)
        return sid, code, col

    tasks = [
        (sid, s["code"], bt_klines[s["code"]], fund_snapshot.get(s["code"]) or {})
        for sid in strategy_ids for s in valid_bt
    ]
    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_WORKERS) as ex:
        futures = [ex.submit(_bt_one, *t) for t in tasks]
        for future in as_completed(futures):
            sid, code, col = future.result()
            if col.get("samples", 0) > 0:
                merged[sid]["covered"] += 1
            for hold in config.BACKTEST_HOLD_DAYS:
                merged[sid][hold].extend(col.get(hold, []))

    # 汇总
    strategies_out = []
    rows = []
    min_sig = config.BACKTEST_MIN_SIGNALS
    for sid in strategy_ids:
        name = STRATEGY_REGISTRY.get(sid, {}).get("name", sid)
        hold_summary = {}
        for hold in config.BACKTEST_HOLD_DAYS:
            hold_summary[hold] = _bt_summarize(merged[sid][hold], min_sig)
        snapshot_bias = sid in config.VALUATION_STRATEGIES
        strategies_out.append({
            "strategy_id": sid,
            "name": name,
            "stocks_covered": merged[sid]["covered"],
            "snapshot_bias": snapshot_bias,
            "hold_days": hold_summary,
        })
        h5 = hold_summary.get(5)
        h20 = hold_summary.get(20)
        rows.append([
            sid,
            name,
            f"{merged[sid]['covered']}/{len(valid_bt)}",
            f"{h5['samples'] if h5 else 0}",
            f"{h5['win_rate'] * 100:.1f}%" if h5 else "样本不足",
            f"{h5['avg_return'] * 100:+.2f}%" if h5 else "-",
            f"{h20['win_rate'] * 100:.1f}%" if h20 else "样本不足",
            f"{h20['avg_return'] * 100:+.2f}%" if h20 else "-",
            "当前估值" if snapshot_bias else "历史重放",
        ])

    table = _fmt_table(
        ["策略", "名称", "覆盖标的", "5日样本", "5日胜率", "5日均收益",
         "20日胜率", "20日均收益", "信号来源"],
        rows,
    )

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    report_lines = [
        "=" * 72,
        "   策略历史回测报告（真实K线信号回放）",
        f"   市场: {market} | 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"   抽样: {len(valid_bt)} 只标的 | 历史K线: {config.BACKTEST_HISTORY_DAYS} 日",
        f"   持有期: {config.BACKTEST_HOLD_DAYS[0]}日/{config.BACKTEST_HOLD_DAYS[1]}日 | 最小样本: {min_sig}",
        "=" * 72,
        "",
        table,
        "",
        "【统计口径说明】",
        "1. 技术面策略(S01-S05/S08-S11/S16-S17)：信号在历史K线上逐日完整重放，无前视偏差，胜率为历史真实统计。",
        "2. 估值策略(S06/S07)：估值使用当前快照（历史估值无公开数据源），信号频率受当前估值影响，",
        "   不作为历史胜率依据，仅供形态参考。",
        "3. 全部回测基于当前仍在交易标的的历史K线，存在幸存者偏差。",
        "4. 同一标的多信号之间非独立，样本合并统计仅供参考。",
        "5. 胜率为历史统计，不代表未来收益；不构成投资建议，不构成收益承诺。",
        "6. 股市有风险，投资需谨慎。",
        "=" * 72,
    ]
    report_text = "\n".join(report_lines)

    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, f"回测报告_{market}_{timestamp}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n" + table)
    print(f"\n[回测报告] {report_path}")

    return {
        "market": market,
        "strategies": strategies_out,
        "report_path": report_path,
    }


# ============================================================
# 未来趋势推演（真实数据驱动，条件式合规措辞）
# ============================================================

def _build_trend_outlook(
    market_env: dict,
    industry_ranking: list[dict],
    concept_ranking: list[dict],
) -> list[dict]:
    """基于真实市场数据生成条件式趋势推演（非预测承诺）。

    数据全部来自实时真实信号：
    - 市场级：指数均线结构 + 近5日动量 + 量能（_assess_market_environment 的 signals）
    - 板块级：行业/概念板块实时涨幅排行与领涨股（东方财富公开排行接口，A股适用）

    措辞一律为条件式（"若…则…"），只描述数据呈现出的结构关系，
    不做涨跌承诺、不构成投资建议，合规合法。

    Returns:
        list[dict]: [{kind, name, signal, outlook}, ...]
    """
    outlook = []

    # 市场级推演（三市场通用）
    signals = market_env.get("signals", {})
    for code, sig in signals.items():
        name = sig.get("name", code)
        direction = sig.get("direction", "未知")
        mom = sig.get("momentum_5d")
        vol_note = sig.get("volume_note", "")
        mom_str = f"近5日{mom:+.1f}%" if mom is not None else ""
        signal_str = "，".join(
            x for x in [f"MA{direction}", mom_str, f"量能{vol_note}" if vol_note else ""] if x
        )
        if direction == "多头":
            outlook.append({
                "kind": "市场",
                "name": name,
                "signal": signal_str,
                "outlook": (
                    f"若{name}站稳20日均线上方且量能延续，则多头结构有望保持；"
                    f"若放量滞涨或收盘跌破MA20，则可能转入震荡。"
                ),
            })
        elif direction == "空头":
            outlook.append({
                "kind": "市场",
                "name": name,
                "signal": signal_str,
                "outlook": (
                    f"若{name}未现放量止跌信号，则下行结构可能延续；"
                    f"若缩量企稳并站回MA5，则可能出现技术性反弹。"
                ),
            })
        else:
            outlook.append({
                "kind": "市场",
                "name": name,
                "signal": signal_str,
                "outlook": (
                    f"若{name}放量突破近期震荡区间上沿，则可能转为上行；"
                    f"若跌破区间下沿且量能放大，则可能转入下行。"
                ),
            })

    # 板块级推演（行业/概念排行仅A股有公开数据；港股/美股如实跳过）
    for label, ranking in (("行业", industry_ranking), ("概念", concept_ranking)):
        top = [r for r in ranking if r.get("pct_chg") is not None][:3]
        for r in top:
            name = r.get("name", "")
            if not name:
                continue
            pct = r.get("pct_chg", 0)
            lead = r.get("lead_stock_name", "")
            lead_note = f"（领涨：{lead}）" if lead else ""
            outlook.append({
                "kind": label,
                "name": name,
                "signal": f"实时涨幅{pct:+.2f}%",
                "outlook": (
                    f"若{label}板块「{name}」涨幅延续且领涨股强势保持{lead_note}，"
                    f"则相关方向活跃度可能维持；若板块龙头放量滞涨或涨幅回落，则短线热度可能降温。"
                ),
            })

    return outlook


if __name__ == "__main__":
    main()