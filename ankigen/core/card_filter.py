"""
卡片过滤器模块

负责过滤低质量卡片。
"""

from typing import List

from loguru import logger

from ankigen.models.card import Card, CardType, MCQCard


class CardFilter:
    """
    卡片过滤器类
    
    负责过滤低质量的卡片。
    """

    def filter_cards(self, cards: List[Card], card_type: str) -> List[Card]:
        """
        过滤低质量卡片

        Args:
            cards: 卡片列表
            card_type: 卡片类型

        Returns:
            过滤后的卡片列表
        """
        filtered = []

        for card in cards:
            # 基本验证
            if not card.front or len(card.front.strip()) == 0:
                continue

            if card.card_type == CardType.BASIC:
                if not self._validate_basic_card(card):
                    continue

            elif card.card_type == CardType.CLOZE:
                if not self._validate_cloze_card(card):
                    continue

            elif card.card_type == CardType.MCQ:
                if not self._validate_mcq_card(card):
                    continue

            filtered.append(card)

        logger.debug(f"质量过滤: {len(cards)} -> {len(filtered)}")
        return filtered

    def _validate_basic_card(self, card: Card) -> bool:
        """
        验证Basic卡片
        
        Args:
            card: 卡片对象
            
        Returns:
            如果卡片有效则返回True
        """
        if not card.back or len(card.back.strip()) == 0:
            return False
        return True

    def _validate_cloze_card(self, card: Card) -> bool:
        """
        验证Cloze卡片
        
        Args:
            card: 卡片对象
            
        Returns:
            如果卡片有效则返回True
        """
        # 验证cloze标记
        if "{{c" not in card.front:
            return False
        return True

    def _validate_mcq_card(self, card: Card) -> bool:
        """
        验证MCQ卡片
        
        Args:
            card: 卡片对象
            
        Returns:
            如果卡片有效则返回True
        """
        if not isinstance(card, MCQCard):
            return False
        
        if len(card.options) < 2:
            return False
        
        if not card.validate_options():
            return False
        
        return True
