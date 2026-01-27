"""
内容切分器模块

负责根据目标卡片数量切分内容。
"""

import re
from typing import List

from loguru import logger


class ContentChunker:
    """
    内容切分器类
    
    负责根据目标卡片数量切分内容。
    """

    def chunk_for_cards(
        self, content: str, target_card_count: int, max_cards_per_chunk: int = 20
    ) -> List[str]:
        """
        根据目标卡片数量切分内容

        将内容切分成多个块，每个块最多生成max_cards_per_chunk张卡片。

        Args:
            content: 输入内容
            target_card_count: 目标卡片总数
            max_cards_per_chunk: 每个块最多生成的卡片数（默认20）

        Returns:
            内容块列表
        """
        if target_card_count <= max_cards_per_chunk:
            return [content]

        # 计算需要多少个块
        num_chunks = (target_card_count + max_cards_per_chunk - 1) // max_cards_per_chunk

        # 估算每个块应该包含多少字符
        # 假设每500字符生成1张卡片
        chars_per_card = 500
        chars_per_chunk = chars_per_card * max_cards_per_chunk

        # 按段落切分（保持语义完整性）
        chunks = self._chunk_by_paragraphs(content, num_chunks, chars_per_chunk)
        
        # 如果切分后块数不够，尝试更细粒度的切分
        if len(chunks) < num_chunks and len(chunks) > 0:
            chunks = self._chunk_by_sentences(content, num_chunks)

        # 确保至少有一个块
        return chunks if chunks else [content]

    def _chunk_by_paragraphs(
        self, content: str, num_chunks: int, chars_per_chunk: int
    ) -> List[str]:
        """
        按段落切分内容
        
        Args:
            content: 输入内容
            num_chunks: 目标块数
            chars_per_chunk: 每个块的字符数
            
        Returns:
            内容块列表
        """
        paragraphs = content.split("\n\n")
        if not paragraphs:
            # 如果没有段落分隔，按换行符切分
            paragraphs = [p for p in content.split("\n") if p.strip()]

        if not paragraphs:
            return [content]

        chunks = []
        current_chunk = []
        current_chars = 0

        for para in paragraphs:
            para_chars = len(para)

            # 如果当前块加上这个段落会超过限制，保存当前块
            if current_chars + para_chars > chars_per_chunk * 1.1 and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_chars = para_chars
            else:
                current_chunk.append(para)
                current_chars += para_chars

        # 添加最后一个块
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _chunk_by_sentences(self, content: str, num_chunks: int) -> List[str]:
        """
        按句子切分内容
        
        Args:
            content: 输入内容
            num_chunks: 目标块数
            
        Returns:
            内容块列表
        """
        # 重新计算每个块应该包含的字符数
        total_chars = len(content)
        chars_per_chunk = total_chars // num_chunks

        # 按句子切分
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return [content]

        chunks = []
        current_chunk = []
        current_chars = 0

        for sent in sentences:
            sent_chars = len(sent)

            if current_chars + sent_chars > chars_per_chunk * 1.1 and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sent]
                current_chars = sent_chars
            else:
                current_chunk.append(sent)
                current_chars += sent_chars

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks
