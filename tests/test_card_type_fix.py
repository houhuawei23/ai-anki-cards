"""
测试 card_type 值获取的修复
"""

from pathlib import Path

import pytest

from ankigen.core.exporter import _add_type_count_suffix, _get_card_type_value, export_cards
from ankigen.models.card import BasicCard, CardType, MCQCard


class TestCardTypeValue:
    """测试卡片类型值获取"""

    def test_get_card_type_value_enum(self):
        """测试从枚举获取值"""
        assert _get_card_type_value(CardType.BASIC) == "basic"
        assert _get_card_type_value(CardType.CLOZE) == "cloze"
        assert _get_card_type_value(CardType.MCQ) == "mcq"

    def test_get_card_type_value_string(self):
        """测试从字符串获取值"""
        assert _get_card_type_value("basic") == "basic"
        assert _get_card_type_value("cloze") == "cloze"
        assert _get_card_type_value("mcq") == "mcq"

    def test_add_type_count_suffix_with_enum(self, tmp_path):
        """测试添加类型后缀（枚举类型）"""
        cards = [BasicCard(front="问题", back="答案")]
        output_path = tmp_path / "test.txt"
        
        result_path = _add_type_count_suffix(output_path, cards)
        
        assert result_path.name == "test.basic.1.txt"

    def test_add_type_count_suffix_with_string(self, tmp_path):
        """测试添加类型后缀（字符串类型）"""
        # 创建一个 card_type 为字符串的卡片（模拟 Pydantic 序列化后的情况）
        card = BasicCard(front="问题", back="答案")
        # 模拟 Pydantic 的 use_enum_values=True 行为
        card.card_type = "basic"  # type: ignore
        
        cards = [card]
        output_path = tmp_path / "test.txt"
        
        result_path = _add_type_count_suffix(output_path, cards)
        
        assert result_path.name == "test.basic.1.txt"

    def test_export_with_string_card_type(self, tmp_path):
        """测试导出时 card_type 为字符串的情况"""
        card = BasicCard(front="问题", back="答案")
        # 模拟 Pydantic 的 use_enum_values=True 行为
        card.card_type = "basic"  # type: ignore
        
        cards = [card]
        output_path = tmp_path / "test.csv"
        
        # 应该不会抛出 AttributeError
        export_cards(cards, output_path, format="csv", add_type_count_suffix=False)
        assert output_path.exists()
