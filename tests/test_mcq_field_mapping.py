"""
测试 MCQ 卡片字段映射
"""

from pathlib import Path

import pytest

from ankigen.core.exporter import ItemsTXTExporter, ItemsWithTypeTXTExporter, ItemsYAMLExporter
from ankigen.core.field_mapper import map_card_to_fields
from ankigen.models.card import MCQCard, MCQOption


class TestMCQFieldMapping:
    """测试 MCQ 卡片字段映射"""

    def test_map_mcq_card_to_fields(self):
        """测试 MCQ 卡片字段映射（单选题）"""
        card = MCQCard(
            front="测试问题？",
            back="",
            options=[
                MCQOption(text="选项A", is_correct=False),
                MCQOption(text="选项B", is_correct=True),
                MCQOption(text="选项C", is_correct=False),
                MCQOption(text="选项D", is_correct=False),
            ],
            explanation="这是解释",
        )

        fields = map_card_to_fields(card)

        # 验证关键字段
        assert fields["Question"] == "测试问题？"
        assert fields["OptionA"] == "选项A"
        assert fields["OptionB"] == "选项B"
        assert fields["OptionC"] == "选项C"
        assert fields["OptionD"] == "选项D"
        assert fields["Answer"] == "B"  # Answer 应该是选项字母（单选题）
        assert fields["Note"] == "这是解释"
        # NoteA-F 应该为空
        assert fields.get("NoteA", "") == ""
        assert fields.get("NoteB", "") == ""

    def test_map_mcq_card_to_fields_multiple_choice(self):
        """测试 MCQ 卡片字段映射（多选题）"""
        card = MCQCard(
            front="多选题测试？",
            back="",
            options=[
                MCQOption(text="选项A", is_correct=True),
                MCQOption(text="选项B", is_correct=False),
                MCQOption(text="选项C", is_correct=True),
                MCQOption(text="选项D", is_correct=False),
                MCQOption(text="选项E", is_correct=True),
            ],
            explanation="这是多选题解释",
        )

        fields = map_card_to_fields(card)

        # 验证关键字段
        assert fields["Question"] == "多选题测试？"
        assert fields["OptionA"] == "选项A"
        assert fields["OptionB"] == "选项B"
        assert fields["OptionC"] == "选项C"
        assert fields["OptionD"] == "选项D"
        assert fields["OptionE"] == "选项E"
        assert fields["Answer"] == "ACE"  # Answer 应该是所有正确答案的字母组合
        assert fields["Note"] == "这是多选题解释"

    def test_map_mcq_card_with_note_fields(self):
        """测试 MCQ 卡片字段映射（包含 NoteA-F 字段）"""
        card = MCQCard(
            front="测试问题？",
            back="",
            options=[
                MCQOption(text="选项A", is_correct=True),
                MCQOption(text="选项B", is_correct=False),
                MCQOption(text="选项C", is_correct=True),
            ],
            explanation="这是总说明",
            metadata={
                "NoteA": "这是选项A的说明",
                "NoteB": "这是选项B的说明",
                "NoteC": "这是选项C的说明",
            },
        )

        fields = map_card_to_fields(card)

        # 验证 NoteA-F 字段
        assert fields["Note"] == "这是总说明"
        assert fields["NoteA"] == "这是选项A的说明"
        assert fields["NoteB"] == "这是选项B的说明"
        assert fields["NoteC"] == "这是选项C的说明"
        assert fields.get("NoteD", "") == ""  # 不存在的字段应该为空

    def test_export_mcq_to_yaml(self, tmp_path):
        """测试导出 MCQ 卡片到 YAML"""
        card = MCQCard(
            front="测试问题？",
            back="",
            options=[
                MCQOption(text="选项A", is_correct=False),
                MCQOption(text="选项B", is_correct=True),
            ],
            explanation="解释",
            tags=["标签1"],
        )

        exporter = ItemsYAMLExporter()
        output_path = tmp_path / "test.yml"
        exporter.export([card], output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")

        # 验证关键字段存在且不为空
        assert "Question:" in content
        assert "测试问题？" in content
        assert "OptionA:" in content
        assert "选项A" in content
        assert "OptionB:" in content
        assert "选项B" in content
        assert "Answer:" in content
        assert "选项B" in content  # 正确答案
        assert "Note:" in content
        assert "解释" in content

    def test_export_mcq_to_txt(self, tmp_path):
        """测试导出 MCQ 卡片到 TXT"""
        card = MCQCard(
            front="测试问题？",
            back="",
            options=[
                MCQOption(text="选项A", is_correct=False),
                MCQOption(text="选项B", is_correct=True),
                MCQOption(text="选项C", is_correct=False),
            ],
            explanation="解释",
            tags=["标签1"],
        )

        exporter = ItemsTXTExporter()
        output_path = tmp_path / "test.txt"
        exporter.export([card], output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")

        # 验证列名包含所有 MCQ 字段
        assert "Question" in content
        assert "OptionA" in content
        assert "OptionB" in content
        assert "OptionC" in content
        assert "Answer" in content
        assert "Note" in content

        # 验证数据行包含内容（不是全空）
        lines = content.split("\n")
        data_lines = [line for line in lines if line and not line.startswith("#")]
        assert len(data_lines) > 0
        # 检查数据行是否包含实际内容（不是只有制表符）
        data_line = data_lines[0]
        assert len(data_line.split("\t")) > 3  # 至少有几个字段有内容

    def test_export_mcq_to_with_type_txt(self, tmp_path):
        """测试导出 MCQ 卡片到 with_type.txt"""
        card = MCQCard(
            front="测试问题？",
            back="",
            options=[
                MCQOption(text="选项A", is_correct=False),
                MCQOption(text="选项B", is_correct=True),
            ],
            explanation="解释",
            tags=["标签1"],
        )

        exporter = ItemsWithTypeTXTExporter()
        output_path = tmp_path / "test.with_type.txt"
        exporter.export([card], output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")

        # 验证列名包含所有 MCQ 字段
        assert "Question" in content
        assert "OptionA" in content
        assert "OptionB" in content
        assert "Answer" in content
        assert "Note" in content

        # 验证数据行包含内容
        lines = content.split("\n")
        data_lines = [line for line in lines if line and not line.startswith("#")]
        assert len(data_lines) > 0
