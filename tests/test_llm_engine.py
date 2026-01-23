"""
LLM引擎测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ankigen.core.llm_engine import (
    DeepSeekProvider,
    LLMEngine,
    OllamaProvider,
    OpenAIProvider,
)
from ankigen.models.config import LLMConfig, LLMProvider


class TestOpenAIProvider:
    """OpenAI提供商测试"""

    @pytest.fixture
    def config(self):
        """创建配置"""
        return LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="test_key",
        )

    @pytest.mark.asyncio
    async def test_generate(self, config):
        """测试生成文本（mock）"""
        provider = OpenAIProvider(config)

        mock_response = {
            "choices": [{"message": {"content": "生成的文本"}}]
        }

        # Mock响应对象（异步上下文管理器）
        mock_response_obj = MagicMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.__aenter__ = AsyncMock(return_value=mock_response_obj)
        mock_response_obj.__aexit__ = AsyncMock(return_value=False)

        # Mock post方法，返回异步上下文管理器
        mock_post = MagicMock(return_value=mock_response_obj)
        
        # Mock session（异步上下文管理器）
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.generate("测试提示词")
            assert result == "生成的文本"


class TestDeepSeekProvider:
    """DeepSeek提供商测试"""

    @pytest.fixture
    def config(self):
        """创建配置"""
        return LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test_key",
        )

    @pytest.mark.asyncio
    async def test_generate(self, config):
        """测试生成文本（mock）"""
        provider = DeepSeekProvider(config)

        mock_response = {
            "choices": [{"message": {"content": "生成的文本"}}]
        }

        # Mock响应对象（异步上下文管理器）
        mock_response_obj = MagicMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.__aenter__ = AsyncMock(return_value=mock_response_obj)
        mock_response_obj.__aexit__ = AsyncMock(return_value=False)

        # Mock post方法，返回异步上下文管理器
        mock_post = MagicMock(return_value=mock_response_obj)
        
        # Mock session（异步上下文管理器）
        mock_session = MagicMock()
        mock_session.post = mock_post
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.generate("测试提示词")
            assert result == "生成的文本"


class TestLLMEngine:
    """LLM引擎测试"""

    @pytest.fixture
    def config(self):
        """创建配置"""
        return LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test_key",
        )

    def test_create_provider(self, config):
        """测试创建提供商"""
        engine = LLMEngine(config)
        assert engine.provider is not None

    @pytest.mark.asyncio
    async def test_generate(self, config):
        """测试生成文本（mock）"""
        engine = LLMEngine(config)

        with patch.object(
            engine.provider, "generate_with_retry", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = "生成的文本"

            result = await engine.generate("测试提示词")
            assert result == "生成的文本"
            mock_generate.assert_called_once()
