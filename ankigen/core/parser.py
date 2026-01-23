"""
文件解析器模块

支持解析文本文件和Markdown文件，提供批量处理和智能分块功能。
"""

import re
from pathlib import Path
from typing import List, Optional

import chardet
import frontmatter
import markdown
from loguru import logger
from tqdm import tqdm

from ankigen.utils.token_counter import TokenCounter


class TextParser:
    """
    文本文件解析器

    支持自动编码检测、段落分割和文本清理。
    """

    def __init__(self):
        """初始化文本解析器"""
        pass

    def parse(self, file_path: Path) -> str:
        """
        解析文本文件

        Args:
            file_path: 文件路径

        Returns:
            解析后的文本内容

        Raises:
            FileNotFoundError: 文件不存在
            UnicodeDecodeError: 编码错误
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        try:
            # 检测编码
            try:
                with open(file_path, "rb") as f:
                    raw_data = f.read()
                if not raw_data:
                    logger.warning(f"文件为空: {file_path}")
                    return ""
                detected = chardet.detect(raw_data)
                encoding = detected.get("encoding", "utf-8")
                confidence = detected.get("confidence", 0)
                logger.debug(f"检测到编码: {encoding} (置信度: {confidence:.2f})")
            except Exception as e:
                logger.warning(f"编码检测失败: {e}，使用UTF-8")
                encoding = "utf-8"

            # 读取文件
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
            except UnicodeDecodeError:
                # 如果检测的编码失败，尝试utf-8
                logger.warning(f"使用{encoding}解码失败，尝试UTF-8")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError as e:
                    logger.exception(f"UTF-8解码也失败: {e}")
                    raise Exception(f"无法解码文件 {file_path}，请检查文件编码")
            except PermissionError as e:
                logger.exception(f"文件权限错误: {e}")
                raise Exception(f"无法读取文件 {file_path}，请检查文件权限")

            # 清理文本
            try:
                content = self._clean_text(content)
            except Exception as e:
                logger.warning(f"文本清理失败: {e}，返回原始内容")
                # 即使清理失败，也返回原始内容
                pass
            
            return content
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.exception(f"解析文件失败 {file_path}: {e}")
            raise Exception(f"解析文件失败 {file_path}: {e}")

    def _clean_text(self, text: str) -> str:
        """
        清理文本内容

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # 去除BOM
        text = text.lstrip("\ufeff")

        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 去除多余空白行（保留最多两个连续换行）
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 去除行尾空白
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    def split_into_chunks(
        self, content: str, max_chars: Optional[int] = None
    ) -> List[str]:
        """
        将文本分割成块

        Args:
            content: 文本内容
            max_chars: 每块最大字符数，如果为None则不分割

        Returns:
            文本块列表
        """
        if max_chars is None:
            return [content]

        chunks = []
        paragraphs = content.split("\n\n")

        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para_length = len(para)

            if current_length + para_length > max_chars and current_chunk:
                # 保存当前块
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length + 2  # +2 for "\n\n"

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [content]


class MarkdownParser:
    """
    Markdown文件解析器

    支持YAML front matter提取、标题层级分析和结构保留。
    """

    def __init__(self):
        """初始化Markdown解析器"""
        self.md = markdown.Markdown(extensions=["extra", "codehilite"])

    def parse(self, file_path: Path) -> tuple[str, dict]:
        """
        解析Markdown文件

        Args:
            file_path: 文件路径

        Returns:
            (内容文本, front matter字典)的元组

        Raises:
            FileNotFoundError: 文件不存在
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 读取文件
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)
        except PermissionError as e:
            logger.exception(f"文件权限错误: {e}")
            raise Exception(f"无法读取文件 {file_path}，请检查文件权限")
        except UnicodeDecodeError as e:
            logger.exception(f"文件编码错误: {e}")
            raise Exception(f"无法解码文件 {file_path}，请检查文件编码")
        except Exception as e:
            logger.exception(f"读取Markdown文件失败: {e}")
            raise Exception(f"读取Markdown文件失败 {file_path}: {e}")

        # 提取front matter
        try:
            metadata = post.metadata if hasattr(post, "metadata") else {}
            # 获取内容
            content = post.content
        except Exception as e:
            logger.warning(f"提取front matter失败: {e}，使用空内容")
            metadata = {}
            content = ""

        return content, metadata

    def split_by_headers(self, content: str) -> List[dict]:
        """
        按标题层级分割内容

        Args:
            content: Markdown内容

        Returns:
            包含标题和内容的字典列表
        """
        sections = []
        lines = content.split("\n")
        current_section = {"title": "", "level": 0, "content": []}

        for line in lines:
            # 检测标题
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                # 保存当前section
                if current_section["content"]:
                    sections.append(current_section)

                # 开始新section
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                current_section = {
                    "title": title,
                    "level": level,
                    "content": [],
                }
            else:
                current_section["content"].append(line)

        # 保存最后一个section
        if current_section["content"]:
            sections.append(current_section)

        # 转换为文本
        result = []
        for section in sections:
            content_text = "\n".join(section["content"]).strip()
            if content_text:
                result.append(
                    {
                        "title": section["title"],
                        "level": section["level"],
                        "content": content_text,
                    }
                )

        return result


class BatchProcessor:
    """
    批量文件处理器

    支持批量处理多个文件，递归遍历目录。
    """

    def __init__(self, recursive: bool = True):
        """
        初始化批量处理器

        Args:
            recursive: 是否递归遍历子目录
        """
        self.recursive = recursive
        self.text_parser = TextParser()
        self.md_parser = MarkdownParser()

    def parse_file(self, file_path: Path) -> str:
        """
        解析单个文件

        Args:
            file_path: 文件路径

        Returns:
            解析后的文本内容
        """
        suffix = file_path.suffix.lower()

        if suffix == ".md" or suffix == ".markdown":
            content, metadata = self.md_parser.parse(file_path)
            # 如果有front matter，可以添加到内容中
            if metadata:
                logger.debug(f"提取到front matter: {metadata}")
            return content
        elif suffix == ".txt":
            return self.text_parser.parse(file_path)
        else:
            # 默认按文本文件处理
            logger.warning(f"未知文件类型 {suffix}，按文本文件处理")
            return self.text_parser.parse(file_path)

    def parse_directory(
        self, directory: Path, merge: bool = True
    ) -> List[str] | str:
        """
        解析目录中的所有文件

        Args:
            directory: 目录路径
            merge: 是否合并所有文件内容

        Returns:
            如果merge=True，返回合并后的字符串；否则返回文件内容列表
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"不是目录: {directory}")

        # 收集文件
        files = []
        pattern = "**/*" if self.recursive else "*"
        for ext in [".txt", ".md", ".markdown"]:
            files.extend(directory.glob(f"{pattern}{ext}"))

        if not files:
            logger.warning(f"目录中没有找到可解析的文件: {directory}")
            return "" if merge else []

        logger.info(f"找到 {len(files)} 个文件")

        # 解析文件
        contents = []
        failed_files = []
        for file_path in tqdm(files, desc="解析文件"):
            try:
                content = self.parse_file(file_path)
                if content:  # 只添加非空内容
                    contents.append(content)
            except FileNotFoundError as e:
                logger.error(f"文件不存在: {e}")
                failed_files.append(str(file_path))
            except PermissionError as e:
                logger.error(f"文件权限错误 {file_path}: {e}")
                failed_files.append(str(file_path))
            except Exception as e:
                logger.exception(f"解析文件失败 {file_path}: {e}")
                failed_files.append(str(file_path))
        
        if failed_files:
            logger.warning(f"有 {len(failed_files)} 个文件解析失败: {', '.join(failed_files)}")
        
        if not contents and failed_files:
            raise Exception(f"所有文件解析失败，共 {len(failed_files)} 个文件")

        if merge:
            return "\n\n---\n\n".join(contents)
        return contents

    def chunk_content(
        self, content: str, max_tokens: int, model_name: str = "default"
    ) -> List[str]:
        """
        智能分块内容

        根据token数量将内容分割成多个块。

        Args:
            content: 要分割的内容
            max_tokens: 每块最大token数
            model_name: 模型名称（用于token计算）

        Returns:
            内容块列表
        """
        token_counter = TokenCounter(model_name)
        current_tokens = token_counter.count(content)

        if current_tokens <= max_tokens:
            return [content]

        # 按段落分割
        paragraphs = content.split("\n\n")
        if not paragraphs:
            return [content]

        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = token_counter.count(para)
            
            # 如果单个段落就超过限制，需要进一步分割
            if para_tokens > max_tokens:
                # 先保存当前块
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # 按句子分割长段落
                sentences = re.split(r'[。！？\n]', para)
                for sentence in sentences:
                    if not sentence.strip():
                        continue
                    sent_tokens = token_counter.count(sentence)
                    if current_tokens + sent_tokens > max_tokens and current_chunk:
                        chunks.append("\n\n".join(current_chunk))
                        current_chunk = [sentence]
                        current_tokens = sent_tokens
                    else:
                        current_chunk.append(sentence)
                        current_tokens += sent_tokens
            elif current_tokens + para_tokens > max_tokens and current_chunk:
                # 保存当前块
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
                # 添加段落分隔符的token估算（每个\n\n约2个token）
                if len(current_chunk) > 1:
                    current_tokens += 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [content]


def parse_file(file_path: Path) -> str:
    """
    解析单个文件的便捷函数

    Args:
        file_path: 文件路径

    Returns:
        解析后的文本内容
    """
    processor = BatchProcessor()
    return processor.parse_file(file_path)


def parse_directory(
    directory: Path, recursive: bool = True, merge: bool = True
) -> str | List[str]:
    """
    解析目录的便捷函数

    Args:
        directory: 目录路径
        recursive: 是否递归遍历
        merge: 是否合并内容

    Returns:
        解析后的内容
    """
    processor = BatchProcessor(recursive=recursive)
    return processor.parse_directory(directory, merge=merge)
