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

    @pytest.fixture()
    def config(self):
        """创建配置"""
        return LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="test_key",
        )

    @pytest.mark.asyncio()
    async def test_generate(self, config):
        """测试生成文本（mock）"""
        provider = OpenAIProvider(config)

        # Mock LiteLLM 响应对象
        mock_message = MagicMock()
        mock_message.content = "生成的文本"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response
            result = await provider.generate("测试提示词")
            assert result == "生成的文本"
            mock_acompletion.assert_called_once()


class TestDeepSeekProvider:
    """DeepSeek提供商测试"""

    @pytest.fixture()
    def config(self):
        """创建配置"""
        return LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test_key",
        )

    @pytest.mark.asyncio()
    async def test_generate(self, config):
        """测试生成文本（mock）"""
        provider = DeepSeekProvider(config)

        # Mock LiteLLM 响应对象
        mock_message = MagicMock()
        mock_message.content = "生成的文本"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_acompletion:
            mock_acompletion.return_value = mock_response
            result = await provider.generate("测试提示词")
            assert result == "生成的文本"
            mock_acompletion.assert_called_once()


class TestLLMEngine:
    """LLM引擎测试"""

    @pytest.fixture()
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

    @pytest.mark.asyncio()
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
