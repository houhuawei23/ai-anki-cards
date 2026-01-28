"""
统计显示器模块

负责显示生成统计信息和计算花费。
"""

from typing import TYPE_CHECKING, Optional

from loguru import logger

from ankigen.core.config_loader import load_model_info
from ankigen.models.config import LLMConfig

if TYPE_CHECKING:
    from ankigen.core.stats import GenerationStats


class StatsDisplay:
    """
    统计显示器类

    负责显示生成统计信息和计算API调用花费。
    """

    def __init__(self, llm_config: LLMConfig):
        """
        初始化统计显示器

        Args:
            llm_config: LLM配置对象
        """
        self.llm_config = llm_config
        self._pricing_config = self._load_pricing_config()

    def display(self, stats: "GenerationStats", card_count: int) -> None:
        """
        显示生成统计信息

        Args:
            stats: 统计信息
            card_count: 生成的卡片数量
        """
        if card_count == 0:
            return

        logger.info("=" * 60)
        logger.info("生成统计信息:")
        logger.info(f"  输入 Token 数: {stats.input_tokens:,}")
        if stats.input_cache_hit_tokens > 0:
            logger.info(f"    - Cache Hit: {stats.input_cache_hit_tokens:,}")
            logger.info(f"    - Cache Miss: {stats.input_cache_miss_tokens:,}")
        logger.info(f"  输出 Token 数: {stats.output_tokens:,}")
        logger.info(f"  总 Token 数: {stats.total_tokens:,}")
        logger.info(f"  总用时: {stats.total_time:.2f} 秒")
        logger.info(f"  平均每 Token 用时: {stats.avg_time_per_token * 1000:.2f} 毫秒")
        logger.info(f"  生成速度: {stats.tokens_per_second:.2f} tokens/秒")
        logger.info(f"  每张卡片平均 Token: {stats.output_tokens / card_count:.1f}")
        logger.info(f"  每张卡片平均用时: {stats.total_time / card_count:.2f} 秒")

        # 计算并显示花费
        cost = self.calculate_cost(stats)
        if cost is not None:
            logger.info(f"  预估花费: ¥{cost:.4f}")
            logger.info(f"  每张卡片平均花费: ¥{cost / card_count:.4f}")
        else:
            logger.debug("  未找到定价配置，跳过花费计算")

        logger.info("=" * 60)

    def calculate_cost(self, stats: "GenerationStats") -> Optional[float]:
        """
        计算 API 调用花费（人民币）

        Args:
            stats: 统计信息

        Returns:
            花费金额（人民币），如果配置不存在则返回 None
        """
        if not self._pricing_config:
            return None

        # 计算输入 token 花费（区分 cache hit 和 cache miss）
        input_cache_miss_tokens = stats.input_cache_miss_tokens
        input_cache_hit_tokens = stats.input_cache_hit_tokens

        input_cost = (
            input_cache_miss_tokens / 1_000_000 * self._pricing_config["input"]
            + input_cache_hit_tokens / 1_000_000 * self._pricing_config["input_cache_hit"]
        )

        # 计算输出 token 花费
        output_cost = stats.output_tokens / 1_000_000 * self._pricing_config["output"]

        total_cost = input_cost + output_cost
        return total_cost

    def _load_pricing_config(self) -> Optional[dict]:
        """
        从 model_info.yml 加载 pricing_per_million_tokens 配置

        Returns:
            包含 input, input_cache_hit, output 键的字典，如果未找到则返回 None
        """
        try:
            model_info_dict = load_model_info()
            if model_info_dict:
                models = model_info_dict.get("models", {})
                # 根据配置中的 model_name 查找对应的模型信息
                model_name = self.llm_config.model_name
                if model_name in models:
                    model_data = models[model_name]
                    pricing_config = model_data.get("pricing_per_million_tokens", {})
                    if pricing_config:
                        return {
                            "input": pricing_config.get("input", 2.0),
                            "input_cache_hit": pricing_config.get("input_cache_hit", 0.2),
                            "output": pricing_config.get("output", 3.0),
                        }
        except Exception as e:
            logger.debug(f"加载 pricing_per_million_tokens 配置失败: {e}")
        return None
