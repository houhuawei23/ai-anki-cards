"""
LLM集成引擎模块

支持多个LLM提供商，提供统一的接口，包含重试、限流等机制。
"""

import asyncio
import json
import os
import re
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Tuple

import aiohttp
from loguru import logger

from ankigen.models.config import LLMConfig, LLMProvider


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
        pass

    @abstractmethod
    def _get_default_base_url(self) -> str:
        """
        获取默认API基础URL（子类实现）

        Returns:
            基础URL
        """
        pass

    @abstractmethod
    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """
        生成文本（异步）

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            生成的文本
        """
        pass

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

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数
        
        使用简单的启发式方法：
        - 中文字符：约 1.5 字符/token
        - 英文单词：约 4 字符/token
        
        Args:
            text: 文本内容
            
        Returns:
            估算的 token 数
        """
        # 统计中文字符数（CJK统一汉字）
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 统计其他字符数
        other_chars = len(text) - chinese_chars
        # 估算：中文字符按 1.5 字符/token，其他字符按 4 字符/token
        estimated = int(chinese_chars / 1.5 + other_chars / 4)
        return max(estimated, 1)  # 至少返回 1

    async def generate_with_retry(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
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
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                # 网络错误和超时错误应该重试
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = 2 ** attempt  # 指数退避
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
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"生成失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {error_msg}"
                    )
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"所有重试都失败: {e}")

        raise last_error or Exception("生成失败")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API提供商"""

    def _get_env_api_key(self) -> Optional[str]:
        """从环境变量获取OpenAI API密钥"""
        return os.getenv("OPENAI_API_KEY")

    def _get_default_base_url(self) -> str:
        """获取OpenAI默认API URL"""
        return "https://api.openai.com/v1"

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """使用OpenAI API生成文本"""
        if not self.api_key:
            raise ValueError("OpenAI API密钥未设置")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "presence_penalty": self.config.presence_penalty,
            "frequency_penalty": self.config.frequency_penalty,
        }

        # 设置超时：连接超时10秒，总超时使用配置值，读取超时使用配置值
        timeout = aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        try:
                            error_text = await response.text()
                        except Exception:
                            error_text = f"无法读取错误响应 (状态码 {response.status})"
                        raise Exception(
                            f"OpenAI API错误 (状态码 {response.status}): {error_text}"
                        )

                    try:
                        data = await response.json()
                        if "choices" not in data or len(data["choices"]) == 0:
                            error_msg = data.get("error", {}).get("message", "未知错误") if "error" in data else "响应中没有choices字段"
                            raise Exception(f"OpenAI API返回错误: {error_msg}")
                        return data["choices"][0]["message"]["content"]
                    except KeyError as e:
                        error_msg = f"响应格式错误，缺少字段: {e}"
                        logger.error(f"{error_msg}，响应数据: {data if 'data' in locals() else '无法获取'}")
                        raise Exception(error_msg)
                    except asyncio.TimeoutError as e:
                        raise Exception(f"读取响应超时: {e}")
                    except aiohttp.ClientError as e:
                        raise Exception(f"连接错误: {e}")
                    except json.JSONDecodeError as e:
                        error_text = await response.text() if 'response' in locals() else "无法读取响应"
                        logger.error(f"JSON解析失败: {e}，响应内容: {error_text[:500]}")
                        raise Exception(f"响应JSON解析失败: {e}")
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")
        except Exception as e:
            # 捕获所有其他异常并记录详细信息
            logger.exception(f"OpenAI API调用失败: {e}")
            raise

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """使用OpenAI API流式生成文本"""
        if not self.api_key:
            raise ValueError("OpenAI API密钥未设置")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "presence_penalty": self.config.presence_penalty,
            "frequency_penalty": self.config.frequency_penalty,
            "stream": True,  # 启用流式输出
        }

        timeout = aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

        accumulated_text = ""
        accumulated_tokens = 0

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        try:
                            error_text = await response.text()
                        except Exception:
                            error_text = f"无法读取错误响应 (状态码 {response.status})"
                        raise Exception(
                            f"OpenAI API错误 (状态码 {response.status}): {error_text}"
                        )

                    # 读取流式响应（SSE 格式）
                    buffer = ""
                    async for chunk in response.content.iter_any():
                        buffer += chunk.decode('utf-8', errors='ignore')
                        # 按行处理
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
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
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API提供商（OpenAI兼容）"""

    def _get_env_api_key(self) -> Optional[str]:
        """从环境变量获取DeepSeek API密钥"""
        return os.getenv("DEEPSEEK_API_KEY")

    def _get_default_base_url(self) -> str:
        """获取DeepSeek默认API URL"""
        return "https://api.deepseek.com/v1"

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """使用DeepSeek API生成文本（OpenAI兼容接口）"""
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未设置")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        # 设置超时：连接超时10秒，总超时使用配置值，读取超时使用配置值
        timeout = aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        try:
                            error_text = await response.text()
                        except Exception:
                            error_text = f"无法读取错误响应 (状态码 {response.status})"
                        raise Exception(
                            f"DeepSeek API错误 (状态码 {response.status}): {error_text}"
                        )

                    try:
                        data = await response.json()
                        if "choices" not in data or len(data["choices"]) == 0:
                            error_msg = data.get("error", {}).get("message", "未知错误") if "error" in data else "响应中没有choices字段"
                            raise Exception(f"DeepSeek API返回错误: {error_msg}")
                        return data["choices"][0]["message"]["content"]
                    except KeyError as e:
                        error_msg = f"响应格式错误，缺少字段: {e}"
                        logger.error(f"{error_msg}，响应数据: {data if 'data' in locals() else '无法获取'}")
                        raise Exception(error_msg)
                    except asyncio.TimeoutError as e:
                        raise Exception(f"读取响应超时: {e}")
                    except aiohttp.ClientError as e:
                        raise Exception(f"连接错误: {e}")
                    except json.JSONDecodeError as e:
                        error_text = await response.text() if 'response' in locals() else "无法读取响应"
                        logger.error(f"JSON解析失败: {e}，响应内容: {error_text[:500]}")
                        raise Exception(f"响应JSON解析失败: {e}")
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")
        except Exception as e:
            # 捕获所有其他异常并记录详细信息
            logger.exception(f"DeepSeek API调用失败: {e}")
            raise

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """使用DeepSeek API流式生成文本（OpenAI兼容接口）"""
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未设置")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "stream": True,  # 启用流式输出
        }

        timeout = aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

        accumulated_text = ""
        accumulated_tokens = 0

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        try:
                            error_text = await response.text()
                        except Exception:
                            error_text = f"无法读取错误响应 (状态码 {response.status})"
                        raise Exception(
                            f"DeepSeek API错误 (状态码 {response.status}): {error_text}"
                        )

                    # 读取流式响应（SSE 格式）
                    buffer = ""
                    async for chunk in response.content.iter_any():
                        buffer += chunk.decode('utf-8', errors='ignore')
                        # 按行处理
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
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
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")


class OllamaProvider(BaseLLMProvider):
    """Ollama本地模型提供商"""

    def _get_env_api_key(self) -> Optional[str]:
        """Ollama不需要API密钥"""
        return None

    def _get_default_base_url(self) -> str:
        """获取Ollama默认API URL"""
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
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
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        try:
                            error_text = await response.text()
                        except Exception:
                            error_text = f"无法读取错误响应 (状态码 {response.status})"
                        raise Exception(
                            f"Ollama API错误 (状态码 {response.status}): {error_text}"
                        )

                    try:
                        data = await response.json()
                        if "response" not in data:
                            error_msg = data.get("error", "未知错误") if "error" in data else "响应中没有response字段"
                            raise Exception(f"Ollama API返回错误: {error_msg}")
                        return data.get("response", "")
                    except KeyError as e:
                        error_msg = f"响应格式错误，缺少字段: {e}"
                        logger.error(f"{error_msg}，响应数据: {data if 'data' in locals() else '无法获取'}")
                        raise Exception(error_msg)
                    except asyncio.TimeoutError as e:
                        raise Exception(f"读取响应超时: {e}")
                    except aiohttp.ClientError as e:
                        raise Exception(f"连接错误: {e}")
                    except json.JSONDecodeError as e:
                        error_text = await response.text() if 'response' in locals() else "无法读取响应"
                        logger.error(f"JSON解析失败: {e}，响应内容: {error_text[:500]}")
                        raise Exception(f"响应JSON解析失败: {e}")
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")
        except Exception as e:
            # 捕获所有其他异常并记录详细信息
            logger.exception(f"Ollama API调用失败: {e}")
            raise


class CustomProvider(BaseLLMProvider):
    """自定义OpenAI兼容API提供商"""

    def _get_env_api_key(self) -> Optional[str]:
        """从环境变量获取自定义API密钥"""
        return os.getenv("CUSTOM_API_KEY")

    def _get_default_base_url(self) -> str:
        """获取自定义API URL"""
        return os.getenv("CUSTOM_API_BASE_URL", "https://api.example.com/v1")

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """使用自定义OpenAI兼容API生成文本"""
        if not self.api_key:
            raise ValueError("自定义API密钥未设置")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        # 设置超时：连接超时10秒，总超时使用配置值，读取超时使用配置值
        timeout = aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        try:
                            error_text = await response.text()
                        except Exception:
                            error_text = f"无法读取错误响应 (状态码 {response.status})"
                        raise Exception(
                            f"自定义API错误 (状态码 {response.status}): {error_text}"
                        )

                    try:
                        data = await response.json()
                        if "choices" not in data or len(data["choices"]) == 0:
                            error_msg = data.get("error", {}).get("message", "未知错误") if "error" in data else "响应中没有choices字段"
                            raise Exception(f"DeepSeek API返回错误: {error_msg}")
                        return data["choices"][0]["message"]["content"]
                    except KeyError as e:
                        error_msg = f"响应格式错误，缺少字段: {e}"
                        logger.error(f"{error_msg}，响应数据: {data if 'data' in locals() else '无法获取'}")
                        raise Exception(error_msg)
                    except asyncio.TimeoutError as e:
                        raise Exception(f"读取响应超时: {e}")
                    except aiohttp.ClientError as e:
                        raise Exception(f"连接错误: {e}")
                    except json.JSONDecodeError as e:
                        error_text = await response.text() if 'response' in locals() else "无法读取响应"
                        logger.error(f"JSON解析失败: {e}，响应内容: {error_text[:500]}")
                        raise Exception(f"响应JSON解析失败: {e}")
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")
        except Exception as e:
            # 捕获所有其他异常并记录详细信息
            logger.exception(f"DeepSeek API调用失败: {e}")
            raise

    async def generate_stream(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """使用自定义OpenAI兼容API流式生成文本"""
        if not self.api_key:
            raise ValueError("自定义API密钥未设置")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "stream": True,  # 启用流式输出
        }

        timeout = aiohttp.ClientTimeout(
            connect=10,
            total=self.config.timeout,
            sock_read=self.config.timeout,
        )

        accumulated_text = ""
        accumulated_tokens = 0

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        try:
                            error_text = await response.text()
                        except Exception:
                            error_text = f"无法读取错误响应 (状态码 {response.status})"
                        raise Exception(
                            f"自定义API错误 (状态码 {response.status}): {error_text}"
                        )

                    # 读取流式响应（SSE 格式）
                    buffer = ""
                    async for chunk in response.content.iter_any():
                        buffer += chunk.decode('utf-8', errors='ignore')
                        # 按行处理
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
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
        except asyncio.TimeoutError as e:
            raise Exception(f"请求超时 (超时时间: {self.config.timeout}秒): {e}")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP客户端错误: {e}")


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

    async def generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
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
