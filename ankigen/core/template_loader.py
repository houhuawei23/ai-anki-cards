"""
模板加载器模块

用于加载和解析Anki卡片模板的元信息。
"""

from pathlib import Path
from typing import List, Optional

import yaml
from loguru import logger

from ankigen.models.card import CardType


class TemplateMeta:
    """模板元数据模型"""

    def __init__(self, name: str, description: str, fields: List[str]):
        """
        初始化模板元数据

        Args:
            name: 模板名称
            description: 模板描述
            fields: 字段列表
        """
        self.name = name
        self.description = description
        self.fields = fields

    def __repr__(self) -> str:
        return f"TemplateMeta(name={self.name}, fields={self.fields})"


def get_template_base_dir() -> Path:
    """
    获取模板基础目录

    Returns:
        模板基础目录路径
    """
    return Path(__file__).parent.parent / "cards_templates"


def get_template_dir(card_type: CardType) -> Optional[Path]:
    """
    根据卡片类型获取模板目录

    Args:
        card_type: 卡片类型

    Returns:
        模板目录路径，如果不存在则返回None
    """
    base_dir = get_template_base_dir()

    # 卡片类型到模板目录的映射
    type_to_dir = {
        CardType.BASIC: "Basic-Card",
        CardType.CLOZE: "Cloze-Card",
        CardType.MCQ: "MCQ-Card",
    }

    dir_name = type_to_dir.get(card_type)
    if not dir_name:
        return None

    template_dir = base_dir / dir_name
    if template_dir.exists() and template_dir.is_dir():
        return template_dir

    return None


def load_template_meta(template_dir: Path) -> Optional[TemplateMeta]:
    """
    加载模板元信息

    Args:
        template_dir: 模板目录路径

    Returns:
        模板元数据对象，如果加载失败则返回None
    """
    meta_file = template_dir / "meta.yml"
    if not meta_file.exists():
        logger.warning(f"模板元信息文件不存在: {meta_file}")
        return None

    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning(f"模板元信息文件为空: {meta_file}")
            return None

        name = data.get("Name", "")
        description = data.get("Description", "")
        fields = data.get("Fields", [])

        if not name or not fields:
            logger.warning(f"模板元信息不完整: {meta_file}")
            return None

        return TemplateMeta(name=name, description=description, fields=fields)

    except Exception as e:
        logger.error(f"加载模板元信息失败: {meta_file}, 错误: {e}")
        return None


def get_template_meta(card_type: CardType) -> Optional[TemplateMeta]:
    """
    获取卡片类型对应的模板元信息

    Args:
        card_type: 卡片类型

    Returns:
        模板元数据对象，如果不存在则返回None
    """
    template_dir = get_template_dir(card_type)
    if not template_dir:
        logger.warning(f"未找到卡片类型 {card_type} 对应的模板目录")
        return None

    return load_template_meta(template_dir)
