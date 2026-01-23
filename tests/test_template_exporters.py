"""
模板导出器测试
"""

import tempfile
from pathlib import Path

import pytest

from ankigen.core.exporter import (
    ItemsTXTExporter,
    ItemsWithTypeTXTExporter,
    ItemsYAMLExporter,
)
from ankigen.models.card import BasicCard, CardType, ClozeCard


class TestItemsYAMLExporter:
    """Items YAML导出器测试"""

    def test_export_basic(self, tmp_path):
        """测试导出Basic卡片为YAML格式"""
        cards = [
            BasicCard(front="问题1", back="答案1", tags=["标签1"]),
            BasicCard(front="问题2", back="答案2", tags=["标签2"]),
        ]

        output_path = tmp_path / "items.yml"
        exporter = ItemsYAMLExporter()
        exporter.export(cards, output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "---" in content
        assert "Front: 问题1" in content
        assert "Back: 答案1" in content
        assert "Tags: 标签1" in content

    def test_export_cloze(self, tmp_path):
        """测试导出Cloze卡片为YAML格式"""
        cards = [
            ClozeCard(
                front="Python是一种{{c1::高级编程语言}}",
                back="Python是一种{{c1::高级编程语言}}",
                tags=["python"],
            ),
        ]

        output_path = tmp_path / "items.yml"
        exporter = ItemsYAMLExporter()
        exporter.export(cards, output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "Text:" in content
        assert "{{c1::" in content


class TestItemsTXTExporter:
    """Items TXT导出器测试"""

    def test_export_basic(self, tmp_path):
        """测试导出Basic卡片为items.txt格式"""
        cards = [
            BasicCard(front="问题1", back="答案1", tags=["标签1"]),
        ]

        output_path = tmp_path / "items.txt"
        exporter = ItemsTXTExporter()
        exporter.export(cards, output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        # 检查文件头
        assert "#separator:tab" in content
        assert "#html:true" in content
        assert "#columns:" in content
        assert "#guid column:1" in content
        assert "#tags column:" in content
        # 检查数据行（应该包含GUID和字段值）
        lines = content.strip().split("\n")
        data_line = lines[-1]  # 最后一行是数据
        assert "\t" in data_line  # 应该包含制表符


class TestItemsWithTypeTXTExporter:
    """Items With Type TXT导出器测试"""

    def test_export_basic(self, tmp_path):
        """测试导出Basic卡片为items.with_type.txt格式"""
        cards = [
            BasicCard(front="问题1", back="答案1", tags=["标签1"]),
        ]

        output_path = tmp_path / "items.with_type.txt"
        exporter = ItemsWithTypeTXTExporter()
        exporter.export(cards, output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        # 检查文件头
        assert "#separator:tab" in content
        assert "#columns:" in content
        assert "#guid column:1" in content
        assert "#notetype column:2" in content
        assert "#tags column:" in content
        # 检查数据行应该包含Notetype
        lines = content.strip().split("\n")
        data_line = lines[-1]
        parts = data_line.split("\t")
        assert len(parts) >= 2
        assert parts[1] == "Basic Card"  # Notetype列
