"""
测试解析后的卡片 JSON 导出功能
"""

from pathlib import Path

import pytest

from ankigen.core.exporter import ParsedCardsJSONExporter, export_parsed_cards_json
from ankigen.models.card import BasicCard, MCQCard, MCQOption


class TestParsedCardsJSONExporter:
    """测试解析后的卡片 JSON 导出器"""

    def test_export_basic_card(self, tmp_path):
        """测试导出 Basic 卡片"""
        cards = [
            BasicCard(front="问题1", back="答案1", tags=["标签1", "标签2"]),
            BasicCard(front="问题2", back="答案2", tags=["标签3"]),
        ]

        exporter = ParsedCardsJSONExporter()
        output_path = tmp_path / "test.json"
        exporter.export(cards, output_path)

        assert output_path.exists()
        import json

        data = json.loads(output_path.read_text(encoding="utf-8"))

        assert "cards" in data
        assert data["card_count"] == 2
        assert len(data["cards"]) == 2

        # 验证第一张卡片
        card1 = data["cards"][0]
        assert card1["Front"] == "问题1"
        assert card1["Back"] == "答案1"
        assert isinstance(card1["Tags"], list)
        assert "标签1" in card1["Tags"]
        assert "标签2" in card1["Tags"]

    def test_export_mcq_card(self, tmp_path):
        """测试导出 MCQ 卡片"""
        cards = [
            MCQCard(
                front="测试问题？",
                back="",
                options=[
                    MCQOption(text="选项A", is_correct=False),
                    MCQOption(text="选项B", is_correct=True),
                    MCQOption(text="选项C", is_correct=False),
                ],
                explanation="这是解释",
                tags=["标签1", "标签2"],
            )
        ]

        exporter = ParsedCardsJSONExporter()
        output_path = tmp_path / "test.json"
        exporter.export(cards, output_path)

        assert output_path.exists()
        import json

        data = json.loads(output_path.read_text(encoding="utf-8"))

        assert "cards" in data
        assert data["card_count"] == 1

        card = data["cards"][0]
        assert card["Question"] == "测试问题？"
        assert card["OptionA"] == "选项A"
        assert card["OptionB"] == "选项B"
        assert card["OptionC"] == "选项C"
        assert card["Answer"] == "B"  # Answer 应该是选项字母
        assert card["Note"] == "这是解释"
        assert isinstance(card["Tags"], list)
        assert "标签1" in card["Tags"]
        assert "标签2" in card["Tags"]

    def test_export_with_suffix(self, tmp_path):
        """测试导出时添加后缀"""
        cards = [BasicCard(front="问题", back="答案")]

        export_parsed_cards_json(
            cards=cards,
            output_path=tmp_path / "output.json",
            add_type_count_suffix=True,
            card_type="basic",
            card_count=1,
        )

        # 应该生成带后缀的文件名
        expected_path = tmp_path / "output.basic.1.parsed.json"
        assert expected_path.exists()

    def test_tags_parsing(self, tmp_path):
        """测试 Tags 字段解析"""
        # 测试空格分隔的标签
        cards = [BasicCard(front="问题", back="答案", tags=["标签1", "标签2"])]

        exporter = ParsedCardsJSONExporter()
        output_path = tmp_path / "test.json"
        exporter.export(cards, output_path)

        import json

        data = json.loads(output_path.read_text(encoding="utf-8"))
        card = data["cards"][0]

        assert isinstance(card["Tags"], list)
        assert len(card["Tags"]) == 2
        assert "标签1" in card["Tags"]
        assert "标签2" in card["Tags"]
