"""
卡片去重器模块

负责去除重复的卡片。
"""

from typing import List

from loguru import logger

from ankigen.models.card import Card


class CardDeduplicator:
    """
    卡片去重器类
    
    负责去除重复的卡片（基于正面内容）。
    """

    def deduplicate(self, cards: List[Card]) -> List[Card]:
        """
        去重卡片（基于正面内容）

        Args:
            cards: 卡片列表

        Returns:
            去重后的卡片列表
        """
        seen = set()
        unique_cards = []

        for card in cards:
            # 使用front内容作为唯一标识
            front_normalized = card.front.lower().strip()
            if front_normalized not in seen:
                seen.add(front_normalized)
                unique_cards.append(card)

        logger.debug(f"去重: {len(cards)} -> {len(unique_cards)}")
        return unique_cards
