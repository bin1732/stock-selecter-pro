"""S01-S04 量价形态策略组。

基于日K线的四项核心技术形态判定：
- S01 红肥绿瘦：阳线主导，阳量>阴量
- S02 上涨波段：温和放量上攻
- S03 回调缩量：上涨后缩量健康调整
- S04 横盘调整：缩量窄幅蓄力

数据源：东方财富日K线公开API（push2his.eastmoney.com）
所有计算基于确定性数学公式，可审计复现。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from strategies.base import make_result, clean_klines


def _yang_ratio(klines: list, start: int, end: int) -> float:
    """计算区间阳线占比。"""
    n = end - start
    if n <= 0:
        return 0
    cnt = sum(1 for i in range(start, end) if klines[i]["close"] >= klines[i]["open"])
    return round(cnt / n, 4)


def _yang_volume_ratio(klines: list, start: int, end: int) -> float:
    """阳线日均量 / 阴线日均量；区间无阴线时返回 None（阳量完全主导，由调用方视为满足）。"""
    yv, iv = [], []
    for i in range(start, end):
        v = klines[i].get("volume", 0)
        if klines[i]["close"] >= klines[i]["open"]:
            yv.append(v)
        else:
            iv.append(v)
    ya = sum(yv) / len(yv) if yv else 0
    ia = sum(iv) / len(iv) if iv else 0
    if ia > 0:
        return round(ya / ia, 2)
    return None if ya > 0 else 0.0


def _avg_volume(klines: list, start: int, end: int) -> float:
    """区间日均成交量。"""
    n = end - start
    return sum(klines[i].get("volume", 0) for i in range(start, end)) / n if n > 0 else 0


def _price_range_pct(klines: list, start: int, end: int) -> float:
    """区间涨跌幅(%)。"""
    if start >= end:
        return 0
    p0 = klines[start]["close"]
    p1 = klines[end - 1]["close"]
    return round((p1 - p0) / p0 * 100, 2) if p0 else 0


def _yang_count(klines: list, start: int, end: int) -> int:
    """区间阳线数量。"""
    return sum(1 for i in range(start, end) if klines[i]["close"] >= klines[i]["open"])


# ══════════════════════════════════════════════════════════════
# S01: 红肥绿瘦（阳线主导）
# ══════════════════════════════════════════════════════════════

def check_s01_red_fat_green_thin(klines: list, fundamental: dict = None, money_flow: dict = None) -> dict:
    """S01 红肥绿瘦：近N日阳线占比高 + 阳线均量明显大于阴线均量。

    判定逻辑：
    - 回溯 8~15 个交易日
    - 阳线占比 >= 60%
    - 阳线/阴线均量比 >= 1.5

    信号分级：强(阳比>=70%且量比>=2.0) / 中(满足条件)；不满足条件则无信号
    """
    klines = clean_klines(klines)
    if not klines or len(klines) < config.S01_LOOKBACK_MIN:
        return make_result("S01", "红肥绿瘦", False, 0, ["K线数据不足"])

    n = min(config.S01_LOOKBACK_MAX, len(klines))
    start = max(0, len(klines) - n)
    end = len(klines)

    yr = _yang_ratio(klines, start, end)
    vr = _yang_volume_ratio(klines, start, end)

    p1 = yr >= config.S01_YANG_RATIO_MIN
    # 无阴线时 vr 为 None，视为阳量完全主导，量比条件满足
    p2 = (vr is None) or (vr >= config.S01_VOL_RATIO_MIN)
    passed = p1 and p2

    reasons = []
    reasons.append(f"近{n}日阳线占比{yr:.1%}（阈值≥{config.S01_YANG_RATIO_MIN:.0%}）")
    if vr is None:
        reasons.append("区间无阴线，阳量完全主导（量比视为满足）")
    else:
        reasons.append(f"阳阴均量比{vr:.1f}（阈值≥{config.S01_VOL_RATIO_MIN:.1f}）")

    if passed and yr >= 0.70 and vr is not None and vr >= 2.0:
        signal = "强"; score = 1.0
    elif passed:
        signal = "中"; score = 0.75
    else:
        signal = None; score = 0

    return make_result("S01", "红肥绿瘦", passed, score, reasons,
                       {"yang_ratio": yr, "vol_ratio": vr, "lookback_days": n},
                       signal)


# ══════════════════════════════════════════════════════════════
# S02: 上涨波段（温和放量上攻）
# ══════════════════════════════════════════════════════════════

def check_s02_rising_wave(klines: list, fundamental: dict = None, money_flow: dict = None) -> dict:
    """S02 上涨波段：近N日内有一段明确的温和上涨波段（涨幅5%~15%），
    期间阳线日均量 > 阴线日均量（阳放阴缩）。

    滑动窗口扫描，取涨幅最大的符合条件的波段。
    """
    klines = clean_klines(klines)
    if not klines or len(klines) < config.S02_LOOKBACK + 3:
        return make_result("S02", "上涨波段", False, 0, ["K线数据不足"])

    n = min(config.S02_LOOKBACK + 5, len(klines))
    start = max(0, len(klines) - n)
    end = len(klines)
    window = min(config.S02_LOOKBACK, end - start)

    best = None
    for i in range(start, end - window + 1):
        pct = _price_range_pct(klines, i, i + window)
        if pct < config.S02_RISE_MIN * 100 or pct > config.S02_RISE_MAX * 100:
            continue
        yang_vols = [klines[j]["volume"] for j in range(i, i + window) if klines[j]["close"] >= klines[j]["open"]]
        yin_vols = [klines[j]["volume"] for j in range(i, i + window) if klines[j]["close"] < klines[j]["open"]]
        ya = sum(yang_vols) / len(yang_vols) if yang_vols else 0
        ia = sum(yin_vols) / len(yin_vols) if yin_vols else 0
        if ya >= ia * config.S02_YANG_VOL_RATIO_MIN:
            if best is None or pct > best["pct"]:
                best = {
                    "start_idx": i, "end_idx": i + window - 1,
                    "pct": pct,
                    "date_start": klines[i]["date"],
                    "date_end": klines[i + window - 1]["date"],
                    "yang_avg_vol": round(ya, 0),
                    "yin_avg_vol": round(ia, 0),
                }

    passed = best is not None
    reasons = []
    if passed:
        reasons.append(f"上涨波段 {best['date_start']}~{best['date_end']}，涨幅{best['pct']:.1f}%")
        reasons.append(f"阳均量{best['yang_avg_vol']:.0f} > 阴均量{best['yin_avg_vol']:.0f}")
        if best["pct"] >= 10:
            signal = "强"; score = 0.9
        elif best["pct"] >= 7:
            signal = "中"; score = 0.7
        else:
            signal = "弱"; score = 0.5
    else:
        reasons.append(f"近{n}日未发现涨幅{config.S02_RISE_MIN*100:.0f}%~{config.S02_RISE_MAX*100:.0f}%且阳放阴缩的波段")
        signal = None; score = 0

    return make_result("S02", "上涨波段", passed, score, reasons, best or {}, signal)


# ══════════════════════════════════════════════════════════════
# S03: 回调缩量（健康调整）
# ══════════════════════════════════════════════════════════════

def check_s03_pullback_shrink(klines: list, fundamental: dict = None, money_flow: dict = None) -> dict:
    """S03 回调缩量：在S02检测到的上涨波段之后，回调段日均量 <= 上涨段日均量 × 阈值。

    回调段要求：阳线日均量 > 阴线日均量（回调中有资金承接）。
    """
    klines = clean_klines(klines)
    if not klines or len(klines) < 15:
        return make_result("S03", "回调缩量", False, 0, ["K线数据不足"])

    # 先找上涨波段
    wave = check_s02_rising_wave(klines)
    if not wave["passed"] or not wave["details"] or wave["details"].get("start_idx", None) is None:
        return make_result("S03", "回调缩量", False, 0, ["未找到上涨波段，跳过"], {})

    best = wave["details"]
    ws = best["start_idx"]
    we = best["end_idx"] + 1
    end = len(klines)

    pullback_start = we
    if pullback_start >= end:
        return make_result("S03", "回调缩量", False, 0, ["上涨波段后无回调数据"], {})

    wave_vol = _avg_volume(klines, ws, we)
    pb_vol = _avg_volume(klines, pullback_start, end)
    if wave_vol == 0:
        return make_result("S03", "回调缩量", False, 0, ["上涨段成交量为0"])

    ratio = round(pb_vol / wave_vol, 2)
    # 检查回调段阳放阴缩
    pb_yang_vols = [klines[i]["volume"] for i in range(pullback_start, end) if klines[i]["close"] >= klines[i]["open"]]
    pb_yin_vols = [klines[i]["volume"] for i in range(pullback_start, end) if klines[i]["close"] < klines[i]["open"]]
    pb_ya = sum(pb_yang_vols) / len(pb_yang_vols) if pb_yang_vols else 0
    pb_ia = sum(pb_yin_vols) / len(pb_yin_vols) if pb_yin_vols else 0

    vol_ok = ratio <= config.S03_VOL_RATIO_MAX
    # 回调段阳放阴缩（阳线日均量 ≥ 阴线日均量 × 配置倍数）
    yang_ok = pb_ya >= pb_ia * config.S03_YANG_VOL_RATIO_MIN if pb_ia > 0 else (pb_ya > 0)
    passed = vol_ok and yang_ok

    reasons = [f"上涨段日均量{wave_vol:.0f} → 回调段日均量{pb_vol:.0f}，量比{ratio:.1f}（需≤{config.S03_VOL_RATIO_MAX}）"]
    if yang_ok:
        reasons.append(f"回调段阳均量{pb_ya:.0f} >= 阴均量{pb_ia:.0f}，有资金承接")

    if passed and ratio < config.S03_VOL_RATIO_MAX * 0.5:
        signal = "强"; score = 0.9
    elif passed:
        signal = "中"; score = 0.7
    else:
        signal = None; score = 0

    return make_result("S03", "回调缩量", passed, score, reasons,
                       {"vol_ratio": ratio, "wave_vol": round(wave_vol, 0), "pb_vol": round(pb_vol, 0)},
                       signal)


# ══════════════════════════════════════════════════════════════
# S04: 横盘调整（缩量蓄力）
# ══════════════════════════════════════════════════════════════

def check_s04_sideways_consolidation(klines: list, fundamental: dict = None, money_flow: dict = None) -> dict:
    """S04 横盘调整：近期存在一段 3~8 日的窄幅横盘，缩量、小阳为主。

    判定：区间振幅<阈值 + 单日最大涨幅<阈值 + 较前段缩量 + 阳线占比≥50%
    """
    klines = clean_klines(klines)
    if not klines or len(klines) < config.S04_LOOKBACK_MIN + 10:
        return make_result("S04", "横盘调整", False, 0, ["K线数据不足"])

    lookback = min(30, len(klines))
    start = max(0, len(klines) - lookback)
    end = len(klines)

    min_len = config.S04_LOOKBACK_MIN
    max_len = config.S04_LOOKBACK_MAX

    best = None
    for i in range(start, end - min_len + 1):
        for j in range(i + min_len, min(i + max_len + 1, end + 1)):
            # 每日涨跌幅检查（pct_chg 为百分数，阈值×100 换算）
            if not all(abs(klines[t].get("pct_chg", 0)) <= config.S04_DAILY_RISE_MAX * 100 for t in range(i, j)):
                continue

            # 振幅检查
            highs = [klines[t]["high"] for t in range(i, j)]
            lows = [klines[t]["low"] for t in range(i, j)]
            amplitude = (max(highs) - min(lows)) / min(lows) if min(lows) > 0 else 999
            if amplitude > config.S04_AMPLITUDE_MAX:
                continue

            # 缩量检查
            pre_start = max(0, i - (j - i))
            pre_vol = _avg_volume(klines, pre_start, i)
            sec_vol = _avg_volume(klines, i, j)
            if pre_vol <= 0:
                continue
            if sec_vol / pre_vol > config.S04_VOL_RATIO_MAX:
                continue

            # 阳线检查
            yc = _yang_count(klines, i, j)
            yr = yc / (j - i)
            if yr >= config.S04_YANG_RATIO_MIN:
                pct = _price_range_pct(klines, i, j)
                if best is None or (j - i) > best["length"]:
                    best = {
                        "start_idx": i, "end_idx": j - 1,
                        "length": j - i,
                        "pct": pct,
                        "amplitude": round(amplitude, 4),
                        "yang_ratio": round(yr, 2),
                        "avg_vol": round(sec_vol, 0),
                        "date_start": klines[i]["date"],
                        "date_end": klines[j - 1]["date"],
                    }

    passed = best is not None
    reasons = []
    if passed:
        reasons.append(f"横盘段 {best['date_start']}~{best['date_end']}，跨度{best['length']}日")
        reasons.append(f"区间涨跌{best['pct']:.1f}%，振幅{best['amplitude']:.1%}，阳线比{best['yang_ratio']:.0%}")
        if best["length"] >= 6:
            signal = "强"; score = 0.85
        elif best["length"] >= 4:
            signal = "中"; score = 0.6
        else:
            signal = "弱"; score = 0.4
    else:
        reasons.append(f"近{lookback}日未发现{min_len}~{max_len}日缩量横盘整理区间")
        signal = None; score = 0

    return make_result("S04", "横盘调整", passed, score, reasons, best or {}, signal)


__all__ = [
    "check_s01_red_fat_green_thin",
    "check_s02_rising_wave",
    "check_s03_pullback_shrink",
    "check_s04_sideways_consolidation",
]
