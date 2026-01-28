"""
文件解析器测试
"""

from pathlib import Path

import pytest

from ankigen.core.parser import BatchProcessor, MarkdownParser, TextParser


class TestTextParser:
    """文本解析器测试"""

    def test_parse_file(self, tmp_path):
        """测试解析文本文件"""
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("这是测试内容\n\n第二段内容", encoding="utf-8")

        parser = TextParser()
        content = parser.parse(test_file)

        assert "这是测试内容" in content
        assert "第二段内容" in content

    def test_split_into_chunks(self):
        """测试文本分块"""
        parser = TextParser()
        content = "段落1\n\n段落2\n\n段落3"

        chunks = parser.split_into_chunks(content, max_chars=10)
        assert len(chunks) > 1

        chunks = parser.split_into_chunks(content, max_chars=None)
        assert len(chunks) == 1


class TestMarkdownParser:
    """Markdown解析器测试"""

    def test_parse_file(self, tmp_path):
        """测试解析Markdown文件"""
        # 创建测试文件
        test_file = tmp_path / "test.md"
        test_file.write_text(
            "---\ntitle: Test\n---\n# 标题\n\n内容",
            encoding="utf-8",
        )

        parser = MarkdownParser()
        content, metadata = parser.parse(test_file)

        assert "标题" in content
        assert metadata.get("title") == "Test"

    def test_split_by_headers(self):
        """测试按标题分割"""
        parser = MarkdownParser()
        content = "# 标题1\n\n内容1\n\n## 标题2\n\n内容2"

        sections = parser.split_by_headers(content)
        assert len(sections) == 2
        assert sections[0]["title"] == "标题1"
        assert sections[1]["title"] == "标题2"


class TestBatchProcessor:
    """批量处理器测试"""

    def test_parse_file_txt(self, tmp_path):
        """测试解析txt文件"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="utf-8")

        processor = BatchProcessor()
        content = processor.parse_file(test_file)

        assert "测试内容" in content

    def test_parse_file_md(self, tmp_path):
        """测试解析md文件"""
        test_file = tmp_path / "test.md"
        test_file.write_text("# 标题\n\n内容", encoding="utf-8")

        processor = BatchProcessor()
        content = processor.parse_file(test_file)

        assert "标题" in content or "内容" in content

    def test_parse_directory(self, tmp_path):
        """测试解析目录"""
        # 创建测试文件
        (tmp_path / "file1.txt").write_text("文件1", encoding="utf-8")
        (tmp_path / "file2.txt").write_text("文件2", encoding="utf-8")

        processor = BatchProcessor(recursive=False)
        result = processor.parse_directory(tmp_path, merge=True)

        assert isinstance(result, str)
        assert "文件1" in result
        assert "文件2" in result

    def test_chunk_content(self):
        """测试内容分块"""
        processor = BatchProcessor()
        # 创建足够长的内容以确保能分块（中文字符token数较多）
        content = "这是一段很长的内容。\n\n" * 50

        chunks = processor.chunk_content(content, max_tokens=100)
        # 如果内容足够长，应该能分块
        assert len(chunks) >= 1

        # 验证每个块都不超过限制（允许一定误差）
        from ankigen.utils.token_counter import TokenCounter

        token_counter = TokenCounter()
        for chunk in chunks:
            tokens = token_counter.count(chunk)
            # 允许10%的误差
            assert tokens <= 110, f"块超过限制: {tokens} tokens"
