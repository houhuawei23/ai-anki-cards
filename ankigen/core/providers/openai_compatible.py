"""
OpenAI兼容API提供商基类

包含OpenAI兼容API的公共逻辑，供OpenAIProvider、DeepSeekProvider、CustomProvider继承。
"""

import asyncio
import json
from typing import AsyncIterator, Dict, List, Optional, Tuple

import aiohttp
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

    def _build_headers(self) -> Dict[str, str]:
        """
        构建请求头

        Returns:
            请求头字典
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_timeout(self) -> aiohttp.ClientTimeout:
        """
        获取超时配置

        Returns:
            超时配置对象
        """
        return aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

    async def _handle_response(self, response: aiohttp.ClientResponse) -> str:
        """
        处理HTTP响应

        Args:
            response: HTTP响应对象

        Returns:
            生成的文本内容

        Raises:
            Exception: 如果响应状态码不是200或响应格式错误
        """
        if response.status != 200:
            try:
                error_text = await response.text()
            except Exception:
                error_text = f"无法读取错误响应 (状态码 {response.status})"
            raise Exception(
                f"{self.provider_name} API错误 (状态码 {response.status}): {error_text}"
            )

        try:
            data = await response.json()
            if "choices" not in data or len(data["choices"]) == 0:
                error_msg = (
                    data.get("error", {}).get("message", "未知错误")
                    if "error" in data
                    else "响应中没有choices字段"
                )
                raise LLMProviderError(f"{self.provider_name} API返回错误: {error_msg}")
            return data["choices"][0]["message"]["content"]
        except KeyError as e:
            error_msg = f"响应格式错误，缺少字段: {e}"
            logger.error(f"{error_msg}，响应数据: {data if 'data' in locals() else '无法获取'}")
            raise LLMProviderError(error_msg) from e
        except asyncio.TimeoutError as e:
            raise LLMProviderError(f"读取响应超时: {e}") from e
        except aiohttp.ClientError as e:
            raise LLMProviderError(f"连接错误: {e}") from e
        except json.JSONDecodeError as e:
            error_text = await response.text() if "response" in locals() else "无法读取响应"
            logger.error(f"JSON解析失败: {e}，响应内容: {error_text[:500]}")
            raise LLMProviderError(f"响应JSON解析失败: {e}") from e

    async def _parse_stream_response(
        self, response: aiohttp.ClientResponse
    ) -> AsyncIterator[Tuple[str, int]]:
        """
        解析流式响应（SSE格式）

        Args:
            response: HTTP响应对象

        Yields:
            (文本片段, 累计token数) 元组

        Raises:
            Exception: 如果响应状态码不是200
        """
        if response.status != 200:
            try:
                error_text = await response.text()
            except Exception:
                error_text = f"无法读取错误响应 (状态码 {response.status})"
            raise Exception(
                f"{self.provider_name} API错误 (状态码 {response.status}): {error_text}"
            )

        accumulated_text = ""
        accumulated_tokens = 0
        buffer = ""

        async for chunk in response.content.iter_any():
            buffer += chunk.decode("utf-8", errors="ignore")
            # 按行处理
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()

                if not line or line == "data: [DONE]":
                    continue

                if line.startswith("data: "):
                    line = line[6:]  # 移除 "data: " 前缀

                try:
                    data = json.loads(line)
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            accumulated_text += content
                            # 估算新增的 token 数
                            new_tokens = self._estimate_tokens(content)
                            accumulated_tokens += new_tokens
                            yield (content, accumulated_tokens)
                except json.JSONDecodeError:
                    # 忽略无效的 JSON 行
                    continue

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

        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        messages = self._build_messages(prompt, system_prompt)
        payload = self._build_payload(messages, stream=False)
        timeout = self._get_timeout()

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session, session.post(
                url, headers=headers, json=payload
            ) as response:
                return await self._handle_response(response)
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")
        except Exception as e:
            # 捕获所有其他异常并记录详细信息
            logger.exception(f"{self.provider_name} API调用失败: {e}")
            raise

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

        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        messages = self._build_messages(prompt, system_prompt)
        payload = self._build_payload(messages, stream=True)
        timeout = self._get_timeout()

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session, session.post(
                url, headers=headers, json=payload
            ) as response:
                async for chunk in self._parse_stream_response(response):
                    yield chunk
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")
