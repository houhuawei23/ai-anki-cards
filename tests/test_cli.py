"""
CLI集成测试

端到端测试，mock LLM API。
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ankigen.cli import generate
from ankigen.core.card_generator import CardGenerator
from ankigen.models.config import LLMConfig, LLMProvider


@pytest.fixture
def sample_txt_file(tmp_path):
    """创建示例txt文件"""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("Python是一种编程语言。", encoding="utf-8")
    return file_path


@pytest.fixture
def mock_llm_response():
    """Mock LLM响应"""
    return json.dumps(
        {
            "cards": [
                {
                    "front": "Python是什么？",
                    "back": "Python是一种编程语言",
                    "tags": ["编程", "Python"],
                }
            ]
        }
    )


class TestCLI:
    """CLI集成测试"""

    @pytest.mark.asyncio
    async def test_generate_basic_flow(self, sample_txt_file, tmp_path, mock_llm_response):
        """测试基本生成流程"""
        output_path = tmp_path / "output.apkg"

        # 直接测试核心功能，不依赖CLI
        from ankigen.core.card_generator import CardGenerator
        from ankigen.core.parser import parse_file
        from ankigen.core.exporter import export_cards
        from ankigen.models.config import GenerationConfig, LLMConfig, LLMProvider

        # 解析文件
        content = parse_file(sample_txt_file)
        assert len(content) > 0

        # 生成卡片（使用mock）
        llm_config = LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test_key",
        )
        generator = CardGenerator(llm_config)

        # Mock stream_generate 返回异步生成器
        async def mock_stream_generate_func(prompt, system_prompt=None):
            yield (mock_llm_response, 100)

        with patch.object(
            generator.llm_engine, "generate", new_callable=AsyncMock
        ) as mock_generate, patch.object(
            generator.llm_engine, "stream_generate", side_effect=mock_stream_generate_func
        ):
            mock_generate.return_value = mock_llm_response

            config = GenerationConfig(card_type="basic", card_count=1)
            result = await generator.generate_cards(content, config)
            
            # 现在返回 (cards, stats) 元组
            if isinstance(result, tuple):
                cards, stats = result
            else:
                cards = result

            assert len(cards) > 0

            # 导出卡片（文件名会被修改，添加类型和数量后缀）
            export_cards(cards, output_path, format="apkg", add_type_count_suffix=False)
            assert output_path.exists()
