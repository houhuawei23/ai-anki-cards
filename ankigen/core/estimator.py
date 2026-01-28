"""
资源估算模块

根据卡片类型、模型信息和目标卡片数量，自动计算最优的内容切分策略和API调用参数，
并估算所需的时间和token消耗。
"""

import math
from dataclasses import dataclass
from typing import Dict, Optional

from loguru import logger

from ankigen.core.config_loader import load_model_info
from ankigen.models.config import LLMConfig


@dataclass
class CardTypeMetrics:
    """卡片类型性能指标"""

    avg_time_per_card: float  # 平均每张卡片用时（秒）
    avg_tokens_per_card: int  # 平均每张卡片token数


@dataclass
class ModelInfo:
    """模型信息"""

    provider: str
    context_length: int
    max_output_default: int
    max_output_maximum: int
    speed_tokens_per_second: float
    card_metrics: Dict[str, CardTypeMetrics]


@dataclass
class ChunkingStrategy:
    """内容切分策略"""

    num_chunks: int  # 需要切分的块数
    cards_per_chunk: int  # 每个块生成的卡片数
    max_tokens_per_request: int  # 每次API请求的max_tokens


class ResourceEstimator:
    """资源估算器"""

    def __init__(self, model_info: Optional[ModelInfo] = None):
        """
        初始化资源估算器

        Args:
            model_info: 模型信息，如果为None则尝试从配置文件加载
        """
        self.model_info = model_info or self._load_default_model_info()

    @staticmethod
    def _load_default_model_info() -> Optional[ModelInfo]:
        """加载默认模型信息"""
        try:
            model_info_dict = load_model_info()
            if model_info_dict:
                # 尝试加载第一个模型的信息
                models = model_info_dict.get("models", {})
                if models:
                    # 默认使用第一个模型
                    model_name = next(iter(models.keys()))
                    model_data = models[model_name]
                    return ResourceEstimator._parse_model_info(model_data)
        except Exception as e:
            logger.warning(f"加载模型信息失败: {e}，将使用默认值")
        return None

    @staticmethod
    def _parse_model_info(model_data: dict) -> ModelInfo:
        """解析模型信息字典为ModelInfo对象"""
        card_metrics = {}
        metrics_data = model_data.get("card_metrics", {})
        for card_type, metrics in metrics_data.items():
            card_metrics[card_type] = CardTypeMetrics(
                avg_time_per_card=metrics.get("avg_time_per_card", 5.0),
                avg_tokens_per_card=metrics.get("avg_tokens_per_card", 150),
            )

        max_output = model_data.get("max_output", {})
        return ModelInfo(
            provider=model_data.get("provider", "deepseek"),
            context_length=model_data.get("context_length", 128000),
            max_output_default=max_output.get("default", 4000),
            max_output_maximum=max_output.get("maximum", 8000),
            speed_tokens_per_second=model_data.get("speed_tokens_per_second", 30),
            card_metrics=card_metrics,
        )

    def estimate_tokens(self, card_type: str, card_count: int) -> int:
        """
        估算生成指定数量卡片所需的总token数

        Args:
            card_type: 卡片类型（basic/cloze/mcq）
            card_count: 卡片数量

        Returns:
            估算的总token数
        """
        if not self.model_info:
            # 使用默认值
            if card_type.lower() == "mcq":
                return card_count * 500
            else:
                return card_count * 150

        metrics = self.model_info.card_metrics.get(card_type.lower())
        if not metrics:
            # 如果找不到该卡片类型的指标，使用默认值
            logger.warning(f"未找到卡片类型 {card_type} 的指标，使用默认值")
            if card_type.lower() == "mcq":
                return card_count * 500
            else:
                return card_count * 150

        return card_count * metrics.avg_tokens_per_card

    def estimate_time(self, card_type: str, card_count: int) -> float:
        """
        估算生成指定数量卡片所需的总时间（秒）

        Args:
            card_type: 卡片类型（basic/cloze/mcq）
            card_count: 卡片数量

        Returns:
            估算的总时间（秒）
        """
        if not self.model_info:
            # 使用默认值
            if card_type.lower() == "mcq":
                return card_count * 15.0
            else:
                return card_count * 5.0

        metrics = self.model_info.card_metrics.get(card_type.lower())
        if not metrics:
            # 如果找不到该卡片类型的指标，使用默认值
            logger.warning(f"未找到卡片类型 {card_type} 的指标，使用默认值")
            if card_type.lower() == "mcq":
                return card_count * 15.0
            else:
                return card_count * 5.0

        return card_count * metrics.avg_time_per_card

    def get_max_tokens_for_request(
        self, card_type: str, model_info: Optional[ModelInfo] = None
    ) -> int:
        """
        根据卡片类型和模型信息返回单次API请求的max_tokens

        默认使用4000以平衡生成质量和耗时。

        Args:
            card_type: 卡片类型（basic/cloze/mcq）
            model_info: 模型信息，如果为None则使用self.model_info

        Returns:
            单次API请求的max_tokens值
        """
        info = model_info or self.model_info
        if info:
            # 使用模型配置的default值，但确保不超过maximum
            max_tokens = min(info.max_output_default, info.max_output_maximum)
            # 默认使用4000以平衡质量和耗时
            return min(4000, max_tokens)
        return 4000  # 默认值

    def calculate_optimal_chunks(
        self,
        target_cards: int,
        card_type: str,
        model_info: Optional[ModelInfo] = None,
    ) -> ChunkingStrategy:
        """
        计算最优的内容切分策略

        根据目标卡片数量、卡片类型和模型信息，计算：
        - 需要切分成多少块
        - 每个块应该生成多少张卡片
        - 每次API请求的max_tokens

        Args:
            target_cards: 目标卡片总数
            card_type: 卡片类型（basic/cloze/mcq）
            model_info: 模型信息，如果为None则使用self.model_info

        Returns:
            切分策略对象
        """
        info = model_info or self.model_info

        # 估算总token数
        total_tokens = self.estimate_tokens(card_type, target_cards)

        # 获取单次请求的max_tokens（默认4000）
        max_tokens_per_request = self.get_max_tokens_for_request(card_type, info)

        # 计算需要切分成多少块
        # 公式：ceil(total_tokens / max_tokens_per_request)
        num_chunks = math.ceil(total_tokens / max_tokens_per_request)

        # 确保至少1个块
        num_chunks = max(1, num_chunks)

        # 计算每个块应该生成的卡片数
        # 公式：ceil(target_cards / num_chunks)
        cards_per_chunk = math.ceil(target_cards / num_chunks)

        logger.info(
            f"切分策略计算完成: 目标{target_cards}张{card_type}卡片, "
            f"总token约{total_tokens}, 分{num_chunks}次生成, "
            f"每次{cards_per_chunk}张卡片, max_tokens={max_tokens_per_request}"
        )

        return ChunkingStrategy(
            num_chunks=num_chunks,
            cards_per_chunk=cards_per_chunk,
            max_tokens_per_request=max_tokens_per_request,
        )

    def estimate_for_generation(
        self, content: str, card_type: str, target_cards: int
    ) -> Dict[str, any]:
        """
        为生成任务估算资源需求

        Args:
            content: 输入内容
            card_type: 卡片类型
            target_cards: 目标卡片数量

        Returns:
            包含估算信息的字典：
            - total_tokens: 总token数
            - total_time: 总时间（秒）
            - strategy: 切分策略
        """
        total_tokens = self.estimate_tokens(card_type, target_cards)
        total_time = self.estimate_time(card_type, target_cards)
        strategy = self.calculate_optimal_chunks(target_cards, card_type)

        return {
            "total_tokens": total_tokens,
            "total_time": total_time,
            "strategy": strategy,
            "content_length": len(content),
        }


def create_estimator_from_config(llm_config: LLMConfig) -> ResourceEstimator:
    """
    从LLM配置创建资源估算器

    Args:
        llm_config: LLM配置对象

    Returns:
        资源估算器实例
    """
    try:
        model_info_dict = load_model_info()
        if model_info_dict:
            models = model_info_dict.get("models", {})
            # 根据配置中的model_name查找对应的模型信息
            model_name = llm_config.model_name
            if model_name in models:
                model_data = models[model_name]
                model_info = ResourceEstimator._parse_model_info(model_data)
                return ResourceEstimator(model_info)
    except Exception as e:
        logger.warning(f"从配置创建估算器失败: {e}，使用默认估算器")

    return ResourceEstimator()
