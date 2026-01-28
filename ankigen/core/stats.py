"""
生成统计信息模块

定义卡片生成过程中的统计数据结构。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class GenerationStats:
    """生成统计信息

    Attributes:
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        total_time: 总用时（秒）
        api_responses: API 响应列表
        input_cache_hit_tokens: cache hit 的输入 token 数
        prompts: 生成的提示词列表
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_time: float = 0.0
    api_responses: List[str] = field(default_factory=list)
    input_cache_hit_tokens: int = 0
    prompts: List[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        """总 token 数"""
        return self.input_tokens + self.output_tokens

    @property
    def avg_time_per_token(self) -> float:
        """平均每 token 用时（秒）"""
        if self.total_tokens == 0:
            return 0.0
        return self.total_time / self.total_tokens

    @property
    def tokens_per_second(self) -> float:
        """每秒生成的 token 数"""
        if self.total_time == 0:
            return 0.0
        return self.output_tokens / self.total_time

    @property
    def input_cache_miss_tokens(self) -> int:
        """cache miss 的输入 token 数"""
        return self.input_tokens - self.input_cache_hit_tokens
