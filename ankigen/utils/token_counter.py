"""
Token计算模块

使用tiktoken计算文本的token数量，支持多种模型编码。
"""

from typing import ClassVar

import tiktoken


class TokenCounter:
    """
    Token计数器类

    支持多种模型的token编码计算。
    """

    # 模型编码映射
    MODEL_ENCODINGS: ClassVar[dict[str, str]] = {
        # OpenAI模型
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "gpt-3.5-turbo-16k": "cl100k_base",
        # DeepSeek模型（使用GPT-4编码）
        "deepseek-chat": "cl100k_base",
        "deepseek-coder": "cl100k_base",
        # 其他模型默认使用cl100k_base
        "default": "cl100k_base",
    }

    def __init__(self, model_name: str = "default"):
        """
        初始化Token计数器

        Args:
            model_name: 模型名称，用于选择对应的编码
        """
        self.model_name = model_name
        encoding_name = self.MODEL_ENCODINGS.get(model_name, "cl100k_base")
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            # 如果获取编码失败，使用默认编码
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        """
        计算文本的token数量

        Args:
            text: 要计算的文本

        Returns:
            token数量
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_messages(
        self, messages: list[dict[str, str]], extra_tokens_per_message: int = 3
    ) -> int:
        """
        计算消息列表的token数量（用于Chat API）

        Args:
            messages: 消息列表，每个消息包含role和content字段
            extra_tokens_per_message: 每条消息的额外token数（用于格式）

        Returns:
            token数量
        """
        tokens = 0
        for message in messages:
            tokens += extra_tokens_per_message
            for _key, value in message.items():
                tokens += self.count(str(value))
        tokens += 3  # 回复助手消息的额外token
        return tokens

    def truncate(self, text: str, max_tokens: int) -> str:
        """
        截断文本到指定的token数量

        Args:
            text: 要截断的文本
            max_tokens: 最大token数量

        Returns:
            截断后的文本
        """
        if not text:
            return text

        encoded = self.encoding.encode(text)
        if len(encoded) <= max_tokens:
            return text

        truncated = encoded[:max_tokens]
        return self.encoding.decode(truncated)

    @classmethod
    def estimate_tokens(cls, text: str, model_name: str = "default") -> int:
        """
        快速估算token数量（类方法）

        Args:
            text: 要估算的文本
            model_name: 模型名称

        Returns:
            估算的token数量
        """
        counter = cls(model_name)
        return counter.count(text)
