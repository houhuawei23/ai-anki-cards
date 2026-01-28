"""
卡片生成器测试
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ankigen.core.card_deduplicator import CardDeduplicator
from ankigen.core.card_factory import CardFactory
from ankigen.core.card_filter import CardFilter
from ankigen.core.card_generator import CardGenerator, PromptTemplate
from ankigen.core.response_parser import ResponseParser
from ankigen.models.card import BasicCard, CardType, MCQCard
from ankigen.models.config import GenerationConfig, LLMConfig, LLMProvider


class TestPromptTemplate:
    """提示词模板测试"""

    def test_render_basic(self):
        """测试渲染Basic模板"""
        template = PromptTemplate()
        result = template.render(
            "basic",
            content="测试内容",
            card_count=5,
            difficulty="medium",
        )

        assert "测试内容" in result
        assert "5" in result
        assert "medium" in result

    def test_render_custom_prompt(self):
        """测试自定义提示词"""
        template = PromptTemplate()
        custom = "自定义提示词: {{content}}"
        result = template.render(
            "basic",
            content="测试",
            card_count=1,
            custom_prompt=custom,
        )

        assert "自定义提示词" in result
        assert "测试" in result


class TestCardGenerator:
    """卡片生成器测试"""

    @pytest.fixture()
    def llm_config(self):
        """创建LLM配置"""
        return LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test_key",
        )

    @pytest.fixture()
    def generator(self, llm_config):
        """创建卡片生成器"""
        return CardGenerator(llm_config)

    def test_parse_response_basic(self, generator):
        """测试解析Basic卡片响应"""
        response_new = json.dumps(
            {
                "cards": [
                    {
                        "Front": "问题1",
                        "Back": "答案1",
                        "Tags": ["标签1"],
                    }
                ]
            }
        )
        cards = generator.response_parser.parse_response(
            response_new, "basic", generator.card_factory
        )
        assert len(cards) == 1
        assert isinstance(cards[0], BasicCard)
        assert cards[0].front == "问题1"
        assert cards[0].back == "答案1"

    def test_filter_cards(self, generator):
        """测试卡片过滤"""
        cards = [
            BasicCard(front="有效卡片", back="答案"),
            BasicCard(front="", back="答案"),  # 无效：front为空
            BasicCard(front="有效卡片2", back=""),  # 无效：back为空
        ]

        filtered = generator.card_filter.filter_cards(cards, "basic")
        assert len(filtered) == 1
        assert filtered[0].front == "有效卡片"

    def test_deduplicate_cards(self, generator):
        """测试卡片去重"""
        cards = [
            BasicCard(front="重复", back="答案1"),
            BasicCard(front="重复", back="答案2"),  # 重复
            BasicCard(front="不重复", back="答案3"),
        ]

        unique = generator.card_deduplicator.deduplicate(cards)
        assert len(unique) == 2

    def test_estimate_card_count(self, generator):
        """测试卡片数量估算"""
        short_content = "短内容"
        long_content = "内容 " * 1000
        very_long_content = "内容 " * 5000

        count_short = generator._estimate_card_count(short_content)
        count_long = generator._estimate_card_count(long_content)
        count_very_long = generator._estimate_card_count(very_long_content)

        # 单次估算应该最多20张
        assert count_short >= 5
        assert count_long > count_short
        assert count_long <= 20
        assert count_very_long <= 20  # 单次最多20张

        # 测试总估算
        total_short = generator._estimate_total_card_count(short_content)
        total_long = generator._estimate_total_card_count(long_content)
        total_very_long = generator._estimate_total_card_count(very_long_content)

        assert total_short >= 5
        assert total_long > total_short
        assert total_very_long > 20  # 总估算可以超过20

        # 测试切分逻辑
        chunks = generator._chunk_content_for_cards(very_long_content, total_very_long)
        assert len(chunks) >= 1

    @pytest.mark.asyncio()
    async def test_generate_cards(self, generator):
        """测试生成卡片（使用mock）"""
        # Mock LLM响应
        mock_response = json.dumps(
            {
                "cards": [
                    {
                        "front": "问题1",
                        "back": "答案1",
                        "tags": ["标签1"],
                    },
                    {
                        "front": "问题2",
                        "back": "答案2",
                        "tags": ["标签2"],
                    },
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

            # 现在返回 (cards, stats) 元组
            if isinstance(result, tuple):
                cards, stats = result
            else:
                cards = result

            assert len(cards) == 2
            assert all(isinstance(card, BasicCard) for card in cards)
