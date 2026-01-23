"""
测试统计信息和 API 响应导出功能
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ankigen.core.card_generator import CardGenerator, GenerationStats
from ankigen.core.exporter import export_api_responses
from ankigen.models.card import BasicCard
from ankigen.models.config import GenerationConfig, LLMConfig, LLMProvider


class TestGenerationStats:
    """测试生成统计信息"""

    def test_stats_properties(self):
        """测试统计信息属性"""
        stats = GenerationStats(
            input_tokens=100,
            output_tokens=200,
            total_time=1.5,
        )

        assert stats.total_tokens == 300
        assert stats.avg_time_per_token == pytest.approx(0.005, rel=1e-2)
        assert stats.tokens_per_second == pytest.approx(133.33, rel=1e-2)

    def test_stats_empty(self):
        """测试空统计信息"""
        stats = GenerationStats()
        assert stats.total_tokens == 0
        assert stats.avg_time_per_token == 0.0
        assert stats.tokens_per_second == 0.0


class TestAPIResponseExport:
    """测试 API 响应导出"""

    def test_export_single_response(self, tmp_path):
        """测试导出单个响应"""
        api_responses = ['{"cards": [{"front": "问题", "back": "答案"}]}']
        output_path = tmp_path / "api_response.json"

        export_api_responses(
            api_responses=api_responses,
            output_path=output_path,
            add_type_count_suffix=False,
        )

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["response_count"] == 1
        assert "response" in data

    def test_export_multiple_responses(self, tmp_path):
        """测试导出多个响应"""
        api_responses = [
            '{"cards": [{"front": "问题1", "back": "答案1"}]}',
            '{"cards": [{"front": "问题2", "back": "答案2"}]}',
        ]
        output_path = tmp_path / "api_response.json"

        export_api_responses(
            api_responses=api_responses,
            output_path=output_path,
            add_type_count_suffix=False,
        )

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["response_count"] == 2
        assert "responses" in data
        assert len(data["responses"]) == 2

    def test_export_with_suffix(self, tmp_path):
        """测试导出时添加后缀"""
        api_responses = ['{"cards": []}']
        output_path = tmp_path / "output.json"

        export_api_responses(
            api_responses=api_responses,
            output_path=output_path,
            add_type_count_suffix=True,
            card_type="basic",
            card_count=5,
        )

        # 应该生成带后缀的文件名
        expected_path = tmp_path / "output.basic.5.api_response.json"
        assert expected_path.exists()


class TestCardGeneratorStats:
    """测试卡片生成器的统计功能"""

    @pytest.fixture
    def llm_config(self):
        """创建LLM配置"""
        return LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test_key",
        )

    @pytest.fixture
    def generator(self, llm_config):
        """创建卡片生成器"""
        return CardGenerator(llm_config)

    @pytest.mark.asyncio
    async def test_generate_cards_returns_stats(self, generator):
        """测试生成卡片返回统计信息"""
        mock_response = json.dumps(
            {
                "cards": [
                    {"front": "问题1", "back": "答案1"},
                    {"front": "问题2", "back": "答案2"},
                ]
            }
        )

        # Mock stream_generate 返回异步生成器
        async def mock_stream_generate_func(prompt, system_prompt=None):
            yield (mock_response, 100)

        with patch.object(
            generator.llm_engine, "generate", new_callable=AsyncMock
        ) as mock_generate, patch.object(
            generator.llm_engine, "stream_generate", side_effect=mock_stream_generate_func
        ):
            mock_generate.return_value = mock_response

            config = GenerationConfig(card_type="basic", card_count=2)
            result = await generator.generate_cards("测试内容", config)

            # 应该返回元组
            assert isinstance(result, tuple)
            assert len(result) == 2

            cards, stats = result

            # 验证卡片
            assert len(cards) == 2
            assert all(isinstance(card, BasicCard) for card in cards)

            # 验证统计信息
            assert isinstance(stats, GenerationStats)
            assert stats.input_tokens > 0
            assert stats.output_tokens > 0
            assert stats.total_time > 0
            assert len(stats.api_responses) > 0

    @pytest.mark.asyncio
    async def test_stats_display(self, generator, capsys):
        """测试统计信息显示"""
        mock_response = json.dumps({"cards": [{"front": "问题", "back": "答案"}]})

        async def mock_stream_generate_func(prompt, system_prompt=None):
            yield (mock_response, 50)

        with patch.object(
            generator.llm_engine, "generate", new_callable=AsyncMock
        ), patch.object(
            generator.llm_engine, "stream_generate", side_effect=mock_stream_generate_func
        ):
            config = GenerationConfig(card_type="basic", card_count=1)
            cards, stats = await generator.generate_cards("测试内容", config)

            # 验证统计信息被显示（通过日志）
            assert stats.input_tokens > 0
            assert stats.output_tokens > 0
