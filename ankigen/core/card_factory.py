"""
卡片工厂模块

负责根据类型和数据创建卡片对象。
"""

from typing import Optional

from loguru import logger

from ankigen.models.card import (
    BasicCard,
    Card,
    CardType,
    ClozeCard,
    MCQCard,
    MCQOption,
)


class CardFactory:
    """
    卡片工厂类
    
    负责从数据字典创建不同类型的卡片对象。
    """

    def create_card_from_data(
        self, card_data: dict, card_type: str
    ) -> Optional[Card]:
        """
        从数据字典创建卡片对象
        
        支持从模板字段名称（如 "Front", "Back", "Text", "Tags"）映射到Card对象字段

        Args:
            card_data: 卡片数据字典（可能包含模板字段名称）
            card_type: 卡片类型

        Returns:
            卡片对象
        """
        card_type_enum = CardType(card_type)

        if card_type_enum == CardType.BASIC:
            return self._create_basic_card(card_data)
        elif card_type_enum == CardType.CLOZE:
            return self._create_cloze_card(card_data)
        elif card_type_enum == CardType.MCQ:
            return self._create_mcq_card(card_data)

        return None

    def _create_basic_card(self, card_data: dict) -> Optional[BasicCard]:
        """
        创建Basic卡片
        
        Args:
            card_data: 卡片数据字典
            
        Returns:
            BasicCard对象
        """
        # 支持 "Front"/"front" 和 "Back"/"back" 字段
        front = card_data.get("Front") or card_data.get("front", "")
        back = card_data.get("Back") or card_data.get("back", "")
        # 将换行符替换为 HTML <br>
        front = front.replace("\n", "<br>") if front else ""
        back = back.replace("\n", "<br>") if back else ""
        # 支持 "Tags"/"tags" 字段
        tags = card_data.get("Tags") or card_data.get("tags", [])
        
        return BasicCard(
            front=front,
            back=back,
            tags=tags if isinstance(tags, list) else [],
            metadata=card_data.get("metadata", {}),
        )

    def _create_cloze_card(self, card_data: dict) -> Optional[ClozeCard]:
        """
        创建Cloze卡片
        
        Args:
            card_data: 卡片数据字典
            
        Returns:
            ClozeCard对象，如果缺少必要字段则返回None
        """
        # Cloze卡片使用 "Text" 字段
        text = card_data.get("Text") or card_data.get("text") or card_data.get("front", "")
        # 将换行符替换为 HTML <br>
        text = text.replace("\n", "<br>") if text else ""
        # 验证是否包含cloze标记
        if "{{c" not in text:
            logger.warning("Cloze卡片缺少填空标记")
            return None

        # 支持 "Tags"/"tags" 字段
        tags = card_data.get("Tags") or card_data.get("tags", [])

        return ClozeCard(
            front=text,
            back=text,  # Cloze卡片back通常与front相同
            tags=tags if isinstance(tags, list) else [],
            metadata=card_data.get("metadata", {}),
        )

    def _create_mcq_card(self, card_data: dict) -> Optional[MCQCard]:
        """
        创建MCQ卡片
        
        Args:
            card_data: 卡片数据字典
            
        Returns:
            MCQCard对象，如果缺少必要字段则返回None
        """
        # MCQ卡片使用 "Question" 或 "Front" 字段
        front = card_data.get("Question") or card_data.get("Front") or card_data.get("front", "")
        # 将换行符替换为 HTML <br>
        front = front.replace("\n", "<br>") if front else ""
        
        # 支持新的格式：OptionA-F 字段
        options = self._parse_mcq_options(card_data)
        
        if not options:
            logger.warning("MCQ卡片缺少选项")
            return None

        # 验证是否有正确答案
        if not any(opt.is_correct for opt in options):
            logger.warning("MCQ卡片没有正确答案")
            return None

        # 支持 "Tags"/"tags" 字段
        tags = card_data.get("Tags") or card_data.get("tags", [])
        # 支持 "Note"/"Explanation"/"explanation" 字段
        explanation = (
            card_data.get("Note")
            or card_data.get("Explanation")
            or card_data.get("explanation")
        )
        # 将换行符替换为 HTML <br>
        if explanation:
            explanation = explanation.replace("\n", "<br>")
        
        # 提取 NoteA-F 字段并存储到 metadata 中
        metadata = card_data.get("metadata", {})
        option_letters = ["A", "B", "C", "D", "E", "F"]
        for letter in option_letters:
            note_key = f"Note{letter}"
            note_value = card_data.get(note_key, "").strip()
            if note_value:
                metadata[note_key] = note_value

        return MCQCard(
            front=front,
            back="",  # MCQ卡片不使用back字段
            card_type=CardType.MCQ,
            options=options,
            explanation=explanation,
            tags=tags if isinstance(tags, list) else [],
            metadata=metadata,
        )

    def _parse_mcq_options(self, card_data: dict) -> list[MCQOption]:
        """
        解析MCQ选项
        
        Args:
            card_data: 卡片数据字典
            
        Returns:
            MCQOption列表
        """
        options = []
        option_letters = ["A", "B", "C", "D", "E", "F"]
        
        # 首先尝试新格式（OptionA-F）
        has_new_format = False
        for letter in option_letters:
            option_key = f"Option{letter}"
            option_value = card_data.get(option_key, "").strip()
            if option_value:
                has_new_format = True
                # 将换行符替换为 HTML <br>
                option_value = option_value.replace("\n", "<br>")
                # 从 Answer 字段判断是否正确
                answer = card_data.get("Answer", "").strip().upper()
                is_correct = letter in answer
                options.append(MCQOption(text=option_value, is_correct=is_correct))
        
        # 如果没有新格式，尝试 Options 数组格式
        if not has_new_format:
            options_data = card_data.get("Options") or card_data.get("options", [])
            if options_data:
                for opt_data in options_data:
                    if isinstance(opt_data, dict):
                        opt_text = opt_data.get("text", "")
                        # 将换行符替换为 HTML <br>
                        opt_text = opt_text.replace("\n", "<br>")
                        options.append(
                            MCQOption(
                                text=opt_text,
                                is_correct=opt_data.get("is_correct", False),
                            )
                        )
                    elif isinstance(opt_data, str):
                        # 简单格式：字符串列表，第一个是正确答案
                        opt_text = opt_data.replace("\n", "<br>")
                        options.append(MCQOption(text=opt_text, is_correct=len(options) == 0))
        
        return options
