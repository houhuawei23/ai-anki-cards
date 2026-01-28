"""
LLM集成引擎模块

支持多个LLM提供商，提供统一的接口，包含重试、限流等机制。
"""

import asyncio
import json
import os
from typing import AsyncIterator, Optional, Tuple

import aiohttp
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
        """使用Ollama API生成文本"""
        url = f"{self.base_url}/api/generate"

        # Ollama使用不同的格式
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": self.config.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
                "top_p": self.config.top_p,
            },
        }

        # 设置超时：连接超时10秒，总超时使用配置值，读取超时使用配置值
        timeout = aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session, session.post(
                url, json=payload
            ) as response:
                if response.status != 200:
                    try:
                        error_text = await response.text()
                    except Exception:
                        error_text = f"无法读取错误响应 (状态码 {response.status})"
                    raise LLMProviderError(
                        f"Ollama API错误 (状态码 {response.status}): {error_text}"
                    )

                try:
                    data = await response.json()
                    if "response" not in data:
                        error_msg = (
                            data.get("error", "未知错误")
                            if "error" in data
                            else "响应中没有response字段"
                        )
                        raise LLMProviderError(f"Ollama API返回错误: {error_msg}")
                    return data.get("response", "")
                except KeyError as e:
                    error_msg = f"响应格式错误，缺少字段: {e}"
                    logger.error(
                        f"{error_msg}，响应数据: {data if 'data' in locals() else '无法获取'}"
                    )
                    raise LLMProviderError(error_msg) from e
                except asyncio.TimeoutError as e:
                    raise LLMProviderError(f"读取响应超时: {e}") from e
                except aiohttp.ClientError as e:
                    raise LLMProviderError(f"连接错误: {e}") from e
                except json.JSONDecodeError as e:
                    error_text = await response.text() if "response" in locals() else "无法读取响应"
                    logger.error(f"JSON解析失败: {e}，响应内容: {error_text[:500]}")
                    raise LLMProviderError(f"响应JSON解析失败: {e}") from e
        except asyncio.TimeoutError as e:
            raise LLMProviderError(f"请求超时 (超时时间: {self.config.timeout}秒): {e}") from e
        except aiohttp.ClientError as e:
            raise LLMProviderError(f"HTTP客户端错误: {e}") from e
        except Exception as e:
            # 捕获所有其他异常并记录详细信息
            logger.exception(f"Ollama API调用失败: {e}")
            raise


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
