"""
导出器工具函数模块

包含导出器使用的公共工具函数。
"""

from pathlib import Path
from typing import List

from loguru import logger

from ankigen.models.card import Card


def get_card_type_string(card_type) -> str:
    """
    安全地获取卡片类型的字符串值

    由于 Pydantic 的 use_enum_values=True 配置，card_type 可能是枚举对象或字符串。

    Args:
        card_type: 卡片类型（可能是 CardType 枚举或字符串）

    Returns:
        卡片类型的字符串值
    """
    if hasattr(card_type, "value"):
        # 如果是枚举对象，获取其值
        return card_type.value
    else:
        # 如果已经是字符串，直接返回
        return str(card_type)


def ensure_output_dir(output_path: Path) -> None:
    """
    确保输出目录存在

    Args:
        output_path: 输出文件路径
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)


def format_tags(tags) -> str:
    """
    格式化标签为字符串

    支持列表、字符串等多种格式。

    Args:
        tags: 标签（可能是列表、字符串或其他格式）

    Returns:
        格式化后的标签字符串（分号分隔）
    """
    if isinstance(tags, list):
        return "; ".join(str(tag) for tag in tags if tag)
    elif isinstance(tags, str):
        return tags
    else:
        return ""


def parse_tags_string(tags_str: str) -> List[str]:
    """
    解析标签字符串为列表

    支持空格、分号、逗号分隔。

    Args:
        tags_str: 标签字符串

    Returns:
        标签列表
    """
    if not tags_str:
        return []

    if ";" in tags_str:
        tags = [t.strip() for t in tags_str.split(";") if t.strip()]
    elif "," in tags_str:
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    else:
        tags = [t.strip() for t in tags_str.split() if t.strip()]

    return tags


def validate_cards(cards: List[Card]) -> bool:
    """
    验证卡片列表是否有效

    Args:
        cards: 卡片列表

    Returns:
        如果卡片列表有效则返回True，否则返回False
    """
    if not cards:
        logger.warning("没有卡片可导出")
        return False
    return True
