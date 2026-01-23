"""
卡片数据模型

定义Anki卡片的数据结构，支持多种卡片类型。
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CardType(str, Enum):
    """卡片类型枚举"""

    BASIC = "basic"
    CLOZE = "cloze"
    MCQ = "mcq"


class Difficulty(str, Enum):
    """难度级别枚举"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Card(BaseModel):
    """
    卡片基础模型

    Attributes:
        front: 卡片正面内容
        back: 卡片背面内容
        card_type: 卡片类型
        tags: 标签列表
        metadata: 元数据字典
    """

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "front": "什么是Python？",
                "back": "Python是一种高级编程语言",
                "card_type": "basic",
                "tags": ["编程", "Python"],
                "metadata": {},
            }
        },
    )

    front: str = Field(..., description="卡片正面内容")
    back: str = Field(..., description="卡片背面内容")
    card_type: CardType = Field(..., description="卡片类型")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class BasicCard(Card):
    """
    Basic卡片模型（正反面卡片）

    继承自Card，用于标准的前后卡片类型。
    """

    card_type: CardType = Field(default=CardType.BASIC, description="卡片类型")


class ClozeCard(Card):
    """
    Cloze填空卡片模型

    正面内容包含{{c1::答案}}格式的填空标记。
    """

    card_type: CardType = Field(default=CardType.CLOZE, description="卡片类型")
    front: str = Field(
        ...,
        description="包含{{c1::答案}}格式的填空内容",
        pattern=r".*\{\{c\d+::.*\}\}.*",
    )


class MCQOption(BaseModel):
    """选择题选项模型"""

    text: str = Field(..., description="选项文本")
    is_correct: bool = Field(default=False, description="是否为正确答案")


class MCQCard(Card):
    """
    多项选择题卡片模型

    包含多个选项，其中一个是正确答案。
    """

    card_type: CardType = Field(default=CardType.MCQ, description="卡片类型")
    options: List[MCQOption] = Field(..., description="选项列表", min_length=2)
    explanation: Optional[str] = Field(None, description="解释说明")

    def get_correct_answer(self) -> Optional[str]:
        """
        获取正确答案

        Returns:
            正确答案文本，如果没有正确答案则返回None
        """
        for option in self.options:
            if option.is_correct:
                return option.text
        return None

    def validate_options(self) -> bool:
        """
        验证选项有效性

        Returns:
            如果至少有一个正确答案则返回True
        """
        correct_count = sum(1 for opt in self.options if opt.is_correct)
        return correct_count == 1


class CardDeck(BaseModel):
    """
    卡片牌组模型

    包含一组卡片和牌组元数据。
    """

    name: str = Field(..., description="牌组名称")
    description: str = Field(default="", description="牌组描述")
    cards: List[Card] = Field(default_factory=list, description="卡片列表")
    creator: str = Field(default="ankigen", description="创建者")
    tags: List[str] = Field(default_factory=list, description="牌组标签")

    def add_card(self, card: Card) -> None:
        """
        添加卡片到牌组

        Args:
            card: 要添加的卡片
        """
        self.cards.append(card)

    def add_cards(self, cards: List[Card]) -> None:
        """
        批量添加卡片到牌组

        Args:
            cards: 要添加的卡片列表
        """
        self.cards.extend(cards)

    def get_card_count(self) -> int:
        """
        获取卡片数量

        Returns:
            卡片数量
        """
        return len(self.cards)

    def get_cards_by_type(self, card_type: CardType) -> List[Card]:
        """
        按类型获取卡片

        Args:
            card_type: 卡片类型

        Returns:
            指定类型的卡片列表
        """
        return [card for card in self.cards if card.card_type == card_type]
