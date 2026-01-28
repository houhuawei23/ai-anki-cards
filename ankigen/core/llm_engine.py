"""
LLM集成引擎模块

支持多个LLM提供商，提供统一的接口，包含重试、限流等机制。
"""

import os
from typing import AsyncIterator, Optional, Tuple

from loguru import logger

from ankigen.core.config_loader import load_model_info
from ankigen.core.providers.base import BaseLLMProvider
from ankigen.core.providers.openai_compatible import OpenAICompatibleProvider
from ankigen.exceptions import LLMProviderError
from ankigen.models.config import LLMConfig, LLMProvider


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI API提供商"""

    def _get_env_api_key(self) -> Optional[str]:
        """从环境变量获取OpenAI API密钥"""
        return os.getenv("OPENAI_API_KEY")

    def _get_default_base_url(self) -> str:
        """获取OpenAI默认API URL"""
        return "https://api.openai.com/v1"

    def _get_provider_name(self) -> str:
        """获取提供商名称"""
        return "OpenAI"

    def _get_litellm_model_name(self) -> str:
        """获取 LiteLLM 模型名称"""
        # LiteLLM 格式: openai/model_name
        return f"openai/{self.config.model_name}"

    def _add_provider_specific_params(self, payload: dict) -> None:
        """
        添加OpenAI特定的参数

        Args:
            payload: 请求负载字典
        """
        # OpenAI支持presence_penalty和frequency_penalty
        if hasattr(self.config, "presence_penalty"):
            payload["presence_penalty"] = self.config.presence_penalty
        if hasattr(self.config, "frequency_penalty"):
            payload["frequency_penalty"] = self.config.frequency_penalty


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek API提供商（OpenAI兼容）"""

    def __init__(self, config: LLMConfig):
        """
        初始化DeepSeek提供商

        Args:
            config: LLM配置对象
        """
        super().__init__(config)
        # 加载 JSON output 配置
        self._json_output_enabled = self._load_json_output_config()

    def _load_json_output_config(self) -> bool:
        """
        从 model_info.yml 加载 functions.json_output 配置

        Returns:
            如果配置为 true 则返回 True，否则返回 False
        """
        try:
            model_info_dict = load_model_info()
            if model_info_dict:
                models = model_info_dict.get("models", {})
                # 根据配置中的 model_name 查找对应的模型信息
                model_name = self.config.model_name
                if model_name in models:
                    model_data = models[model_name]
                    functions = model_data.get("functions", {})
                    return functions.get("json_output", False)
        except Exception as e:
            logger.debug(f"加载 json_output 配置失败: {e}")
        return False

    def _get_env_api_key(self) -> Optional[str]:
        """从环境变量获取DeepSeek API密钥"""
        return os.getenv("DEEPSEEK_API_KEY")

    def _get_default_base_url(self) -> str:
        """获取DeepSeek默认API URL"""
        return "https://api.deepseek.com/v1"

    def _get_provider_name(self) -> str:
        """获取提供商名称"""
        return "DeepSeek"

    def _get_litellm_model_name(self) -> str:
        """获取 LiteLLM 模型名称"""
        # LiteLLM 格式: deepseek/model_name
        return f"deepseek/{self.config.model_name}"

    def _add_provider_specific_params(self, payload: dict) -> None:
        """
        添加DeepSeek特定的参数

        Args:
            payload: 请求负载字典
        """
        # 如果启用了 JSON output，添加 response_format
        if self._json_output_enabled:
            payload["response_format"] = {"type": "json_object"}


class OllamaProvider(BaseLLMProvider):
    """Ollama本地模型提供商"""

    def _get_env_api_key(self) -> Optional[str]:
        """Ollama不需要API密钥"""
        return None

    def _get_default_base_url(self) -> str:
        """获取Ollama默认API URL"""
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """使用Ollama API生成文本（通过LiteLLM）"""
        import litellm

        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # LiteLLM 格式: ollama/model_name
        model_name = f"ollama/{self.config.model_name}"

        try:
            response = await litellm.acompletion(
                model=model_name,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
                api_base=self.base_url,
                timeout=self.config.timeout,
            )
            if not response or not response.choices or len(response.choices) == 0:
                raise LLMProviderError("Ollama API返回错误: 响应中没有choices字段")
            return response.choices[0].message.content or ""
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Ollama API调用失败: {e}")
            raise LLMProviderError(f"Ollama API调用失败: {error_msg}") from e

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """使用Ollama API流式生成文本（通过LiteLLM）"""
        import litellm

        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # LiteLLM 格式: ollama/model_name
        model_name = f"ollama/{self.config.model_name}"

        accumulated_tokens = 0

        try:
            # LiteLLM 使用 acompletion 配合 stream=True 进行异步流式调用
            response_stream = await litellm.acompletion(
                model=model_name,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
                stream=True,
                api_base=self.base_url,
                timeout=self.config.timeout,
            )
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
            error_msg = str(e)
            logger.exception(f"Ollama API调用失败: {e}")
            raise LLMProviderError(f"Ollama API调用失败: {error_msg}") from e


class CustomProvider(OpenAICompatibleProvider):
    """自定义OpenAI兼容API提供商"""

    def _get_env_api_key(self) -> Optional[str]:
        """从环境变量获取自定义API密钥"""
        return os.getenv("CUSTOM_API_KEY")

    def _get_default_base_url(self) -> str:
        """获取自定义API URL"""
        return os.getenv("CUSTOM_API_BASE_URL", "https://api.example.com/v1")

    def _get_provider_name(self) -> str:
        """获取提供商名称"""
        return "自定义API"

    def _get_litellm_model_name(self) -> str:
        """获取 LiteLLM 模型名称"""
        # 对于自定义API，使用 openai/ 前缀表示 OpenAI 兼容格式
        return f"openai/{self.config.model_name}"


class LLMEngine:
    """
    LLM引擎统一接口

    根据配置自动选择合适的提供商，并提供统一的调用接口。
    """

    def __init__(self, config: LLMConfig):
        """
        初始化LLM引擎

        Args:
            config: LLM配置对象
        """
        self.config = config
        self.provider = self._create_provider()

    def _create_provider(self) -> BaseLLMProvider:
        """
        创建LLM提供商实例

        Returns:
            LLM提供商实例

        Raises:
            ValueError: 不支持的提供商
        """
        provider_map = {
            LLMProvider.OPENAI: OpenAIProvider,
            LLMProvider.DEEPSEEK: DeepSeekProvider,
            LLMProvider.OLLAMA: OllamaProvider,
            LLMProvider.CUSTOM: CustomProvider,
        }

        provider_class = provider_map.get(self.config.provider)
        if not provider_class:
            raise ValueError(f"不支持的LLM提供商: {self.config.provider}")

        return provider_class(self.config)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        生成文本

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            生成的文本
        """
        return await self.provider.generate_with_retry(prompt, system_prompt)

    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """
        流式生成文本

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Yields:
            (文本片段, 累计token数) 元组
        """
        async for chunk in self.provider.generate_stream(prompt, system_prompt):
            yield chunk
