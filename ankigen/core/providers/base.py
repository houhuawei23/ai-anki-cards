"""
LLM提供商基类模块

包含所有LLM提供商的抽象基类。
"""

import asyncio
import re
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Tuple

from loguru import logger

from ankigen.core.config_loader import load_model_info
from ankigen.models.config import LLMConfig


class BaseLLMProvider(ABC):
    """
    LLM提供商抽象基类

    所有具体的LLM提供商都需要继承此类并实现抽象方法。
    """

    def __init__(self, config: LLMConfig):
        """
        初始化LLM提供商

        Args:
            config: LLM配置对象
        """
        self.config = config
        self.api_key = self._get_api_key()
        self.base_url = config.base_url or self._get_default_base_url()
        # 加载 token_per_character 配置
        self._token_per_char_config = self._load_token_per_character_config()

    def _get_api_key(self) -> Optional[str]:
        """
        获取API密钥

        优先从环境变量获取，然后使用配置中的密钥。

        Returns:
            API密钥
        """
        # 从环境变量获取
        env_key = self._get_env_api_key()
        if env_key:
            return env_key

        # 从配置获取
        return self.config.get_api_key()

    @abstractmethod
    def _get_env_api_key(self) -> Optional[str]:
        """
        从环境变量获取API密钥（子类实现）

        Returns:
            API密钥
        """

    @abstractmethod
    def _get_default_base_url(self) -> str:
        """
        获取默认API基础URL（子类实现）

        Returns:
            基础URL
        """

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        生成文本（异步）

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            生成的文本
        """

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """
        流式生成文本（默认实现：回退到非流式）

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Yields:
            (文本片段, 累计token数) 元组
        """
        # 默认实现：调用非流式方法并返回完整结果
        result = await self.generate(prompt, system_prompt)
        # 简单估算 token 数（中文约 1.5 字符/token，英文约 4 字符/token）
        estimated_tokens = self._estimate_tokens(result)
        yield (result, estimated_tokens)

    def _load_token_per_character_config(self) -> Optional[dict]:
        """
        从 model_info.yml 加载 token_per_character 配置

        Returns:
            包含 english 和 chinese 键的字典，如果未找到则返回 None
        """
        try:
            model_info_dict = load_model_info()
            if model_info_dict:
                models = model_info_dict.get("models", {})
                # 根据配置中的 model_name 查找对应的模型信息
                model_name = self.config.model_name
                if model_name in models:
                    model_data = models[model_name]
                    token_config = model_data.get("token_per_character", {})
                    if token_config:
                        return {
                            "english": token_config.get("english", 0.3),
                            "chinese": token_config.get("chinese", 0.6),
                        }
        except Exception as e:
            logger.debug(f"加载 token_per_character 配置失败: {e}")
        return None

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数

        优先使用 model_info.yml 中的配置：
        - 如果配置存在：使用配置中的 token_per_character 值
        - 如果配置不存在：使用默认启发式方法（中文字符约 1.5 字符/token，其他字符约 4 字符/token）

        Args:
            text: 文本内容

        Returns:
            估算的 token 数
        """
        # 统计中文字符数（CJK统一汉字）
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        # 统计其他字符数
        other_chars = len(text) - chinese_chars

        # 如果配置存在，使用配置值
        if self._token_per_char_config:
            chinese_token_ratio = self._token_per_char_config.get("chinese", 0.6)
            english_token_ratio = self._token_per_char_config.get("english", 0.3)
            # token_per_character 表示每个字符对应的 token 数
            # 例如：0.6 表示 1 个中文字符 ≈ 0.6 token，即 1 token ≈ 1.67 字符
            estimated = int(chinese_chars * chinese_token_ratio + other_chars * english_token_ratio)
        else:
            # 默认启发式方法：中文字符按 1.5 字符/token，其他字符按 4 字符/token
            estimated = int(chinese_chars / 1.5 + other_chars / 4)

        return max(estimated, 1)  # 至少返回 1

    async def generate_with_retry(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        带重试的文本生成

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            生成的文本

        Raises:
            Exception: 所有重试都失败后抛出异常
        """
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return await self.generate(prompt, system_prompt)
            except (asyncio.TimeoutError, ConnectionError) as e:
                # 网络错误和超时错误应该重试
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = 2**attempt  # 指数退避
                    error_msg = str(e)
                    if isinstance(e, asyncio.TimeoutError):
                        error_msg = f"超时错误: {error_msg}"
                    logger.warning(
                        f"生成失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {error_msg}"
                    )
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"所有重试都失败: {e}")
            except Exception as e:
                # 其他错误（如API错误、认证错误等）不重试，直接抛出
                error_msg = str(e)
                if "API错误" in error_msg or "密钥" in error_msg or "认证" in error_msg.lower():
                    logger.error(f"API错误（不重试）: {error_msg}")
                    raise
                # 其他未知错误也重试
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = 2**attempt
                    logger.warning(
                        f"生成失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {error_msg}"
                    )
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"所有重试都失败: {e}")

        raise last_error or Exception("生成失败")
