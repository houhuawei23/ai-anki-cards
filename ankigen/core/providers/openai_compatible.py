"""
OpenAI兼容API提供商基类

包含OpenAI兼容API的公共逻辑，供OpenAIProvider、DeepSeekProvider、CustomProvider继承。
"""

import asyncio
from typing import AsyncIterator, Dict, List, Optional, Tuple

import litellm
from loguru import logger

from ankigen.core.providers.base import BaseLLMProvider
from ankigen.exceptions import LLMProviderError
from ankigen.models.config import LLMConfig


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    OpenAI兼容API提供商基类

    提供OpenAI兼容API的公共实现，包括：
    - 消息构建
    - 请求负载构建
    - 响应处理
    - 流式响应解析
    """

    def __init__(self, config: LLMConfig):
        """
        初始化OpenAI兼容提供商

        Args:
            config: LLM配置对象
        """
        super().__init__(config)
        self.provider_name = self._get_provider_name()

    def _get_provider_name(self) -> str:
        """
        获取提供商名称（用于错误消息）

        Returns:
            提供商名称
        """
        return "OpenAI兼容API"

    def _build_messages(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        构建消息列表

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            消息列表
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
    ) -> Dict:
        """
        构建请求负载

        Args:
            messages: 消息列表
            stream: 是否启用流式输出

        Returns:
            请求负载字典
        """
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if stream:
            payload["stream"] = True

        # 添加提供商特定的参数
        self._add_provider_specific_params(payload)

        return payload

    def _add_provider_specific_params(self, payload: Dict) -> None:
        """
        添加提供商特定的参数（子类可覆盖）

        Args:
            payload: 请求负载字典
        """
        # 默认实现：不添加任何特定参数
        # 子类可以覆盖此方法来添加特定参数

    def _get_litellm_model_name(self) -> str:
        """
        获取 LiteLLM 模型名称

        根据提供商类型返回 LiteLLM 格式的模型名称。

        Returns:
            LiteLLM 模型名称
        """
        # 默认返回原始模型名称，子类可以覆盖
        return self.config.model_name

    def _get_litellm_api_key(self) -> Optional[str]:
        """
        获取 LiteLLM API 密钥

        Returns:
            API 密钥
        """
        return self.api_key

    def _get_litellm_api_base(self) -> Optional[str]:
        """
        获取 LiteLLM API Base URL

        Returns:
            API Base URL
        """
        return self.base_url

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        生成文本（异步）

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            生成的文本

        Raises:
            ValueError: 如果API密钥未设置
            Exception: 如果API调用失败
        """
        if not self.api_key:
            raise ValueError(f"{self.provider_name} API密钥未设置")

        messages = self._build_messages(prompt, system_prompt)
        payload = self._build_payload(messages, stream=False)

        # 构建 LiteLLM 调用参数
        litellm_kwargs = {
            "model": self._get_litellm_model_name(),
            "messages": messages,
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
            "top_p": payload.get("top_p"),
            "api_key": self._get_litellm_api_key(),
            "timeout": self.config.timeout,
        }

        # 添加 API base URL（如果提供）
        api_base = self._get_litellm_api_base()
        if api_base:
            litellm_kwargs["api_base"] = api_base

        # 添加提供商特定参数
        if "presence_penalty" in payload:
            litellm_kwargs["presence_penalty"] = payload["presence_penalty"]
        if "frequency_penalty" in payload:
            litellm_kwargs["frequency_penalty"] = payload["frequency_penalty"]
        if "response_format" in payload:
            litellm_kwargs["response_format"] = payload["response_format"]

        try:
            response = await litellm.acompletion(**litellm_kwargs)
            if not response or not response.choices or len(response.choices) == 0:
                raise LLMProviderError(f"{self.provider_name} API返回错误: 响应中没有choices字段")
            return response.choices[0].message.content or ""
        except Exception as e:
            # 捕获所有异常并记录详细信息
            error_msg = str(e)
            if "timeout" in error_msg.lower() or isinstance(e, asyncio.TimeoutError):
                raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}") from e
            logger.exception(f"{self.provider_name} API调用失败: {e}")
            raise LLMProviderError(f"{self.provider_name} API调用失败: {error_msg}") from e

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """
        流式生成文本

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Yields:
            (文本片段, 累计token数) 元组

        Raises:
            ValueError: 如果API密钥未设置
            Exception: 如果API调用失败
        """
        if not self.api_key:
            raise ValueError(f"{self.provider_name} API密钥未设置")

        messages = self._build_messages(prompt, system_prompt)
        payload = self._build_payload(messages, stream=True)

        # 构建 LiteLLM 调用参数
        litellm_kwargs = {
            "model": self._get_litellm_model_name(),
            "messages": messages,
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
            "top_p": payload.get("top_p"),
            "stream": True,
            "api_key": self._get_litellm_api_key(),
            "timeout": self.config.timeout,
        }

        # 添加 API base URL（如果提供）
        api_base = self._get_litellm_api_base()
        if api_base:
            litellm_kwargs["api_base"] = api_base

        # 添加提供商特定参数
        if "presence_penalty" in payload:
            litellm_kwargs["presence_penalty"] = payload["presence_penalty"]
        if "frequency_penalty" in payload:
            litellm_kwargs["frequency_penalty"] = payload["frequency_penalty"]
        if "response_format" in payload:
            litellm_kwargs["response_format"] = payload["response_format"]

        accumulated_tokens = 0

        try:
            # LiteLLM 使用 acompletion 配合 stream=True 进行异步流式调用
            response_stream = await litellm.acompletion(**litellm_kwargs)
            async for chunk in response_stream:
                if not chunk or not chunk.choices or len(chunk.choices) == 0:
                    continue

                delta = chunk.choices[0].delta
                if delta and delta.content:
                    content = delta.content
                    # 估算新增的 token 数
                    new_tokens = self._estimate_tokens(content)
                    accumulated_tokens += new_tokens
                    yield (content, accumulated_tokens)
        except Exception as e:
            # 捕获所有异常并记录详细信息
            error_msg = str(e)
            if "timeout" in error_msg.lower() or isinstance(e, asyncio.TimeoutError):
                raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}") from e
            logger.exception(f"{self.provider_name} API调用失败: {e}")
            raise LLMProviderError(f"{self.provider_name} API调用失败: {error_msg}") from e
