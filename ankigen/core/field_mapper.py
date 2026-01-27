"""
字段映射模块

将Card对象映射到Anki模板字段。
"""

import re
from typing import Dict, Optional

from loguru import logger

from ankigen.core.template_loader import TemplateMeta, get_template_meta
from ankigen.models.card import Card, CardType, MCQCard


def map_card_to_fields(card: Card, template_meta: Optional[TemplateMeta] = None) -> Dict[str, str]:
    """
    将Card对象映射到模板字段

    Args:
        card: 卡片对象
        template_meta: 模板元数据，如果为None则自动加载

    Returns:
        字段字典，键为字段名，值为字段内容
    """
    if template_meta is None:
        template_meta = get_template_meta(card.card_type)
        if not template_meta:
            logger.warning(f"无法加载模板元数据，使用默认映射")
            return _default_field_mapping(card)

    fields = {}

    if card.card_type == CardType.BASIC:
        # Basic Card: Front, Back
        for field_name in template_meta.fields:
            if field_name == "Front":
                fields["Front"] = card.front
            elif field_name == "Back":
                fields["Back"] = card.back
            else:
                fields[field_name] = ""  # 其他字段设为空

    elif card.card_type == CardType.CLOZE:
        # Cloze Card: Text
        for field_name in template_meta.fields:
            if field_name == "Text":
                # Cloze卡片的front包含cloze标记，back通常与front相同
                fields["Text"] = card.front
            else:
                fields[field_name] = ""

    elif card.card_type == CardType.MCQ:
        # MCQ Card: 映射到 MCQ 模板的所有字段
        if isinstance(card, MCQCard):
            # 找到所有正确答案的索引（用于生成 Answer 字母组合）
            correct_answer_indices = []
            correct_answer_text = ""
            for i, opt in enumerate(card.options):
                if opt.is_correct:
                    correct_answer_indices.append(i)
                    if not correct_answer_text:
                        correct_answer_text = opt.text
            
            # 映射所有字段
            for field_name in template_meta.fields:
                if field_name == "Question":
                    fields["Question"] = card.front
                elif field_name.startswith("Option") and len(field_name) == 7:  # OptionA-F
                    # OptionA, OptionB, OptionC, OptionD, OptionE, OptionF
                    option_index = ord(field_name[-1]) - ord('A')  # A=0, B=1, C=2, ...
                    if 0 <= option_index < len(card.options):
                        fields[field_name] = card.options[option_index].text
                    else:
                        fields[field_name] = ""
                elif field_name == "Answer":
                    # Answer 字段存储选项字母组合（A, AC, ACE等），支持多选题
                    if correct_answer_indices:
                        answer_letters = "".join([chr(ord('A') + idx) for idx in correct_answer_indices])
                        fields["Answer"] = answer_letters
                    else:
                        fields["Answer"] = ""
                elif field_name == "Note":
                    fields["Note"] = card.explanation or ""
                elif field_name.startswith("Note") and len(field_name) == 5:  # NoteA-F
                    # NoteA, NoteB, NoteC, NoteD, NoteE, NoteF
                    # 从 metadata 中读取，如果不存在则返回空字符串
                    fields[field_name] = card.metadata.get(field_name, "")
                elif field_name == "Front":
                    # 如果模板有 Front 字段，使用 Question 的值
                    fields["Front"] = card.front
                elif field_name == "Back":
                    # 如果模板有 Back 字段，格式化选项和答案
                    options_text = "\n".join(
                        [
                            f"{'✓' if opt.is_correct else '○'} {opt.text}"
                            for opt in card.options
                        ]
                    )
                    explanation = card.explanation or ""
                    # 生成正确答案字母组合
                    if correct_answer_indices:
                        answer_letters = "".join([chr(ord('A') + idx) for idx in correct_answer_indices])
                    else:
                        answer_letters = ""
                    back_content = f"{options_text}\n\n正确答案: {answer_letters}"
                    if explanation:
                        back_content += f"\n\n解释: {explanation}"
                    fields["Back"] = back_content
                else:
                    fields[field_name] = ""
        else:
            # 非MCQCard对象，使用默认映射
            return _default_field_mapping(card)
    else:
        # 未知卡片类型，使用默认映射
        return _default_field_mapping(card)

    # 添加Tags字段（Tags字段不在meta.yml的Fields中，但导出时需要）
    # 始终使用"Tags"作为字段名
    if card.tags:
        tags_str = " ".join(card.tags) if isinstance(card.tags, list) else str(card.tags)
        fields["Tags"] = tags_str
    else:
        # 即使没有标签，也添加空Tags字段
        fields["Tags"] = ""

    return fields


def _default_field_mapping(card: Card) -> Dict[str, str]:
    """
    默认字段映射（当无法加载模板时使用）

    Args:
        card: 卡片对象

    Returns:
        字段字典
    """
    fields = {}

    if card.card_type == CardType.BASIC:
        fields["Front"] = card.front
        fields["Back"] = card.back
    elif card.card_type == CardType.CLOZE:
        fields["Text"] = card.front
    elif card.card_type == CardType.MCQ and isinstance(card, MCQCard):
        fields["Front"] = card.front
        options_text = "\n".join(
            [f"{'✓' if opt.is_correct else '○'} {opt.text}" for opt in card.options]
        )
        answer = card.get_correct_answer() or ""
        fields["Back"] = f"{options_text}\n\n正确答案: {answer}"

    # 添加Tags
    if card.tags:
        fields["Tags"] = " ".join(card.tags)
    else:
        fields["Tags"] = ""

    return fields


def get_template_name(card_type: CardType) -> str:
    """
    获取模板名称

    Args:
        card_type: 卡片类型

    Returns:
        模板名称
    """
    template_meta = get_template_meta(card_type)
    if template_meta:
        return template_meta.name

    # 默认模板名称
    type_to_name = {
        CardType.BASIC: "Basic Card",
        CardType.CLOZE: "Cloze Card",
        CardType.MCQ: "Basic Card",
    }
    return type_to_name.get(card_type, "Basic Card")


def map_fields_to_card(fields: Dict[str, str], card_type: CardType) -> Optional[Card]:
    """
    将字段字典映射到Card对象（反向映射）

    Args:
        fields: 字段字典
        card_type: 卡片类型

    Returns:
        Card对象，如果映射失败则返回None
    """
    from ankigen.models.card import BasicCard, ClozeCard, MCQCard, MCQOption

    try:
        if card_type == CardType.BASIC:
            front = fields.get("Front") or fields.get("front", "")
            back = fields.get("Back") or fields.get("back", "")
            tags = _parse_tags(fields.get("Tags") or fields.get("tags", ""))
            return BasicCard(front=front, back=back, tags=tags)

        elif card_type == CardType.CLOZE:
            text = fields.get("Text") or fields.get("text") or fields.get("Front") or fields.get("front", "")
            tags = _parse_tags(fields.get("Tags") or fields.get("tags", ""))
            if not text:
                return None
            return ClozeCard(front=text, back=text, tags=tags)

        elif card_type == CardType.MCQ:
            question = fields.get("Question") or fields.get("Front") or fields.get("front", "")
            options_str = fields.get("Options") or fields.get("options", "")
            explanation = fields.get("Explanation") or fields.get("explanation", "")
            tags = _parse_tags(fields.get("Tags") or fields.get("tags", ""))

            # 解析选项
            options = []
            if options_str:
                # 尝试解析选项文本
                option_lines = [line.strip() for line in options_str.split("\n") if line.strip()]
                for line in option_lines:
                    # 移除标记符号（✓, ○等）
                    clean_line = re.sub(r"^[✓○•]\s*", "", line)
                    if clean_line:
                        is_correct = "✓" in line or line.startswith("正确答案")
                        options.append(MCQOption(text=clean_line, is_correct=is_correct))

            # 如果没有解析到选项，尝试从Answer字段获取
            if not options:
                answer = fields.get("Answer") or fields.get("answer", "")
                if answer:
                    options.append(MCQOption(text=answer, is_correct=True))

            if not options:
                logger.warning("MCQ卡片缺少选项")
                return None

            return MCQCard(
                front=question,
                back="",
                card_type=CardType.MCQ,
                options=options,
                explanation=explanation,
                tags=tags,
            )

    except Exception as e:
        logger.warning(f"映射字段到卡片失败: {e}, 字段: {fields}")
        return None

    return None


def _parse_tags(tags_str: str) -> list:
    """
    解析标签字符串

    Args:
        tags_str: 标签字符串（可能是空格、分号或逗号分隔）

    Returns:
        标签列表
    """
    if not tags_str:
        return []

    # 尝试不同的分隔符
    if ";" in tags_str:
        return [t.strip() for t in tags_str.split(";") if t.strip()]
    elif "," in tags_str:
        return [t.strip() for t in tags_str.split(",") if t.strip()]
    else:
        # 空格分隔
        return [t.strip() for t in tags_str.split() if t.strip()]

