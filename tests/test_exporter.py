"""
导出模块测试
"""

import tempfile
from pathlib import Path

import pytest

from ankigen.core.exporter import (
    APKGExporter,
    CSVExporter,
    JSONExporter,
    TextExporter,
    export_cards,
)
from ankigen.models.card import BasicCard, CardType, MCQCard, MCQOption


class TestTextExporter:
    """文本导出器测试"""

    def test_export(self, tmp_path):
        """测试导出为文本格式"""
        cards = [
            BasicCard(front="问题1", back="答案1"),
            BasicCard(front="问题2", back="答案2"),
        ]

        output_path = tmp_path / "output.txt"
        exporter = TextExporter()
        exporter.export(cards, output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "问题1" in content
        assert "答案1" in content


class TestCSVExporter:
    """CSV导出器测试"""

    def test_export(self, tmp_path):
        """测试导出为CSV格式"""
        cards = [
            BasicCard(front="问题1", back="答案1", tags=["标签1"]),
        ]

        output_path = tmp_path / "output.csv"
        exporter = CSVExporter()
        exporter.export(cards, output_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "问题1" in content
        assert "答案1" in content


class TestJSONExporter:
    """JSON导出器测试"""

    def test_export_json(self, tmp_path):
        """测试导出为JSON格式"""
        cards = [
            BasicCard(front="问题1", back="答案1"),
        ]

        output_path = tmp_path / "output.json"
        exporter = JSONExporter()
        exporter.export(cards, output_path, format="json")

        assert output_path.exists()
        import json

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["front"] == "问题1"

    def test_export_jsonl(self, tmp_path):
        """测试导出为JSONL格式"""
        cards = [
            BasicCard(front="问题1", back="答案1"),
        ]

        output_path = tmp_path / "output.jsonl"
        exporter = JSONExporter()
        exporter.export(cards, output_path, export_format="jsonl")

        assert output_path.exists()
        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1


class TestAPKGExporter:
    """APKG导出器测试"""

    def test_export(self, tmp_path):
        """测试导出为APKG格式"""
        cards = [
            BasicCard(front="问题1", back="答案1"),
        ]

        output_path = tmp_path / "output.apkg"
        exporter = APKGExporter(deck_name="Test Deck")
        exporter.export(cards, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestExportCards:
    """导出便捷函数测试"""

    def test_export_txt(self, tmp_path):
        """测试导出为txt格式"""
        cards = [BasicCard(front="问题", back="答案")]
        output_path = tmp_path / "output.txt"

        export_cards(cards, output_path, format="txt", add_type_count_suffix=False)
        assert output_path.exists()

    def test_export_csv(self, tmp_path):
        """测试导出为csv格式"""
        cards = [BasicCard(front="问题", back="答案")]
        output_path = tmp_path / "output.csv"

        export_cards(cards, output_path, format="csv", add_type_count_suffix=False)
        assert output_path.exists()

    def test_export_json(self, tmp_path):
        """测试导出为json格式"""
        cards = [BasicCard(front="问题", back="答案")]
        output_path = tmp_path / "output.json"

        export_cards(cards, output_path, format="json", add_type_count_suffix=False)
        assert output_path.exists()

    def test_export_apkg(self, tmp_path):
        """测试导出为apkg格式"""
        cards = [BasicCard(front="问题", back="答案")]
        output_path = tmp_path / "output.apkg"

        export_cards(
            cards, output_path, format="apkg", deck_name="Test", add_type_count_suffix=False
        )
        assert output_path.exists()
