"""数据缓存层。

为K线数据、基本面数据、资金流数据提供内存+文件双层缓存。
减少重复HTTP请求，提升批量筛选性能。

缓存策略：
- K线数据：同一交易日同一股票缓存至当日 15:30 后自动失效
- 基本面数据（PE/PB/ROE）：缓存 4 小时
- 财报数据：缓存到下一季报披露周期（默认 7 天）
- 行业均值：每日更新一次（缓存至次日 00:00）

使用方式：
    from cache import KlineCacheManager
    cache = KlineCacheManager()
    klines = cache.get_or_fetch("000001", fetch_daily_kline, days=60)
"""

import os
import json
import time
import hashlib
from datetime import datetime
from typing import Optional, Callable


class KlineCacheManager:
    """
    K线数据缓存管理器。

    内存缓存 + 文件缓存双层架构：
    - L1 内存缓存：进程内 dict，毫秒级访问
    - L2 文件缓存：磁盘 JSON，跨进程复用

    缓存键：code + days → 文件名为 code_days.json
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """初始化缓存管理器。

        Args:
            cache_dir: 文件缓存目录，默认 scripts/../cache_data/
        """
        if cache_dir is None:
            # 默认缓存在项目 scripts 同级的 cache_data 目录
            base = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(os.path.dirname(base), "cache_data")
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

        # L1 内存缓存: {code_days: {"data": [], "cached_at": timestamp}}
        self._mem_cache: dict[str, dict] = {}

    def _cache_key(self, code: str, days: int) -> str:
        """生成缓存键。"""
        return f"{code}_{days}"

    def _cache_file_path(self, cache_key: str) -> str:
        """生成文件缓存路径。"""
        # 用 md5 缩短路径避免非法字符
        safe_name = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        return os.path.join(self.cache_dir, f"kline_{safe_name}.json")

    def get(self, code: str, days: int) -> Optional[list[dict]]:
        """从缓存中获取K线数据。

        Returns:
            list[dict] 或 None（缓存未命中或已过期）
        """
        cache_key = self._cache_key(code, days)

        # L1 内存缓存
        if cache_key in self._mem_cache:
            entry = self._mem_cache[cache_key]
            if not self._is_kline_expired(entry.get("cached_at", 0)):
                return entry["data"]

        # L2 文件缓存
        file_path = self._cache_file_path(cache_key)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                if not self._is_kline_expired(entry.get("cached_at", 0)):
                    # 回填内存缓存
                    self._mem_cache[cache_key] = entry
                    return entry["data"]
            except (json.JSONDecodeError, KeyError):
                pass

        return None

    def set(self, code: str, days: int, data: list[dict]):
        """将K线数据写入缓存。"""
        cache_key = self._cache_key(code, days)
        entry = {
            "code": code,
            "days": days,
            "data": data,
            "cached_at": time.time(),
            "cache_date": datetime.now().strftime("%Y-%m-%d"),
        }

        # L1 内存
        self._mem_cache[cache_key] = entry

        # L2 文件
        file_path = self._cache_file_path(cache_key)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
        except IOError:
            pass  # 文件写入失败不阻塞

    def get_or_fetch(
        self, code: str, days: int, fetcher: Callable, **kwargs
    ) -> list[dict]:
        """缓存优先获取，未命中则调用 fetcher 并缓存。

        Args:
            code: 股票代码
            days: K线天数
            fetcher: 获取函数，签名为 fetcher(code, days=days, **kwargs) -> list[dict]
            **kwargs: 传递给 fetcher 的额外参数

        Returns:
            list[dict]: K线数据
        """
        cached = self.get(code, days)
        if cached is not None:
            return cached

        data = fetcher(code, days=days, **kwargs)
        if data:
            self.set(code, days, data)
        return data

    def invalidate(self, code: Optional[str] = None):
        """主动失效缓存。

        Args:
            code: 为 None 则清空全部缓存
        """
        if code is None:
            self._mem_cache.clear()
            # 清空文件缓存目录
            for fname in os.listdir(self.cache_dir):
                if fname.startswith("kline_"):
                    os.remove(os.path.join(self.cache_dir, fname))
        else:
            # 清理所有该代码的缓存（不同 days）
            keys_to_del = [k for k in self._mem_cache if k.startswith(f"{code}_")]
            for k in keys_to_del:
                file_path = self._cache_file_path(k)
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self._mem_cache[k]

    @staticmethod
    def _is_kline_expired(cached_at: float) -> bool:
        """K线缓存过期判断：当日 15:30 后过期。

        Args:
            cached_at: 缓存时间戳

        Returns:
            bool: True 表示已过期
        """
        cached_date = datetime.fromtimestamp(cached_at)
        now = datetime.now()

        # 同一天内且在 15:30 之前不过期
        if cached_date.date() == now.date():
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            return now >= market_close

        # 不是同一天，一定过期
        return True


class FundamentalCacheManager:
    """
    基本面/估值数据缓存管理器。

    缓存策略：
    - PE/PB/ROE等：缓存 4 小时
    - 财报数据：缓存 7 天
    """

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def get(self, code: str, cache_type: str = "valuation") -> Optional[dict]:
        """获取缓存的基本面数据。

        Args:
            code: 股票代码
            cache_type: 'valuation' 或 'financial'

        Returns:
            dict 或 None
        """
        key = f"{code}_{cache_type}"
        entry = self._cache.get(key)
        if entry is None:
            return None

        ttl = 4 * 3600 if cache_type == "valuation" else 7 * 24 * 3600
        if time.time() - entry["cached_at"] > ttl:
            del self._cache[key]
            return None
        return entry["data"]

    def set(self, code: str, data: dict, cache_type: str = "valuation"):
        """写入缓存。"""
        key = f"{code}_{cache_type}"
        self._cache[key] = {"data": data, "cached_at": time.time()}

    def get_or_fetch(
        self, code: str, fetcher: Callable, cache_type: str = "valuation", **kwargs
    ) -> dict:
        """缓存优先获取。"""
        cached = self.get(code, cache_type)
        if cached is not None:
            return cached
        data = fetcher(code, **kwargs)
        if data:
            self.set(code, data, cache_type)
        return data

    def invalidate(self, code: Optional[str] = None):
        """失效缓存。"""
        if code is None:
            self._cache.clear()
        else:
            keys = [k for k in self._cache if k.startswith(f"{code}_")]
            for k in keys:
                del self._cache[k]
