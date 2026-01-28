"""
缓存管理模块

提供基于文件的内容缓存功能，避免重复API调用。
"""

import hashlib
import pickle
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class FileCache:
    """
    文件缓存类

    基于内容hash的缓存系统，用于缓存LLM生成结果。
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化文件缓存

        Args:
            cache_dir: 缓存目录路径，如果为None则使用默认目录
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".ankigen" / "cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, content: str, prefix: str = "") -> str:
        """
        生成缓存键

        Args:
            content: 缓存内容
            prefix: 键前缀

        Returns:
            缓存键（hash值）
        """
        hash_obj = hashlib.sha256()
        hash_obj.update(f"{prefix}:{content}".encode())
        return hash_obj.hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        获取缓存文件路径

        Args:
            cache_key: 缓存键

        Returns:
            缓存文件路径
        """
        # 使用前两位作为子目录，避免单个目录文件过多
        subdir = cache_key[:2]
        subdir_path = self.cache_dir / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)
        return subdir_path / f"{cache_key}.pkl"

    def get(self, content: str, prefix: str = "") -> Optional[Any]:
        """
        从缓存获取数据

        Args:
            content: 缓存内容
            prefix: 键前缀

        Returns:
            缓存的数据，如果不存在则返回None
        """
        cache_key = self._get_cache_key(content, prefix)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)  # nosec B301  # 内部缓存，安全可控
            logger.debug(f"Cache hit: {cache_key[:8]}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def set(self, content: str, value: Any, prefix: str = "") -> None:
        """
        设置缓存数据

        Args:
            content: 缓存内容
            value: 要缓存的值
            prefix: 键前缀
        """
        cache_key = self._get_cache_key(content, prefix)
        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(value, f)
            logger.debug(f"Cache saved: {cache_key[:8]}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def clear(self, prefix: Optional[str] = None) -> int:
        """
        清空缓存

        Args:
            prefix: 如果指定，只清空匹配该前缀的缓存

        Returns:
            删除的缓存文件数量
        """
        count = 0
        if prefix:
            # 只清空匹配前缀的缓存
            cache_key_prefix = self._get_cache_key("", prefix)[:2]
            subdir_path = self.cache_dir / cache_key_prefix
            if subdir_path.exists():
                for cache_file in subdir_path.glob("*.pkl"):
                    cache_file.unlink()
                    count += 1
        else:
            # 清空所有缓存
            for cache_file in self.cache_dir.rglob("*.pkl"):
                cache_file.unlink()
                count += 1

        logger.info(f"Cleared {count} cache files")
        return count

    def get_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            包含缓存文件数量和总大小的字典
        """
        cache_files = list(self.cache_dir.rglob("*.pkl"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "count": len(cache_files),
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
