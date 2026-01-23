"""
卡片读取器模块

支持从各种格式读取卡片：yml, txt, with_type.txt, csv, apkg
"""

import csv
import re
from pathlib import Path
from typing import List, Optional

import yaml
from loguru import logger

from ankigen.core.field_mapper import map_fields_to_card
from ankigen.core.template_loader import get_template_meta
from ankigen.models.card import Card, CardType


def detect_format(file_path: Path) -> Optional[str]:
    """
    根据文件扩展名检测格式

    Args:
        file_path: 文件路径

    Returns:
        格式名称，如果无法识别则返回None
    """
    suffix = file_path.suffix.lower()
    name_lower = file_path.name.lower()

    if suffix == ".yml" or suffix == ".yaml":
        return "items_yml"
    elif suffix == ".txt":
        if ".with_type" in name_lower:
            return "items_with_type_txt"
        else:
            return "items_txt"
    elif suffix == ".csv":
        return "csv"
    elif suffix == ".apkg":
        return "apkg"
    else:
        return None


def read_cards(
    file_path: Path,
    card_type: Optional[CardType] = None,
    template_name: Optional[str] = None,
) -> List[Card]:
    """
    从文件读取卡片

    Args:
        file_path: 文件路径
        card_type: 卡片类型（可选，用于自动判定）
        template_name: 模板名称（可选，用于自动判定）

    Returns:
        卡片列表
    """
    format_type = detect_format(file_path)
    if not format_type:
        raise ValueError(f"无法识别文件格式: {file_path}")

    logger.info(f"检测到格式: {format_type}")

    if format_type == "items_yml":
        return read_items_yml(file_path, card_type)
    elif format_type == "items_txt":
        return read_items_txt(file_path, card_type)
    elif format_type == "items_with_type_txt":
        return read_items_with_type_txt(file_path)
    elif format_type == "csv":
        return read_csv(file_path, card_type)
    elif format_type == "apkg":
        return read_apkg(file_path)
    else:
        raise ValueError(f"不支持的格式: {format_type}")


def read_items_yml(file_path: Path, card_type: Optional[CardType] = None) -> List[Card]:
    """
    读取items.yml格式

    Args:
        file_path: 文件路径
        card_type: 卡片类型（可选）

    Returns:
        卡片列表
    """
    cards = []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 使用YAML解析器分割多个文档
    documents = []
    for doc in yaml.safe_load_all(content):
        if doc:
            documents.append(doc)

    if not documents:
        # 如果没有多个文档，尝试按---分割
        parts = re.split(r"^---$", content, flags=re.MULTILINE)
        for part in parts:
            part = part.strip()
            if part:
                try:
                    doc = yaml.safe_load(part)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    logger.warning(f"解析YAML文档失败: {e}")

    for doc in documents:
        try:
            # 尝试从字段推断卡片类型
            inferred_type = card_type
            if not inferred_type:
                inferred_type = infer_card_type_from_fields(doc)

            if inferred_type:
                card = map_fields_to_card(doc, inferred_type)
                if card:
                    cards.append(card)
        except Exception as e:
            logger.warning(f"解析卡片失败: {e}, 数据: {doc}")

    logger.info(f"从 {file_path} 读取了 {len(cards)} 张卡片")
    return cards


def read_items_txt(file_path: Path, card_type: Optional[CardType] = None) -> List[Card]:
    """
    读取items.txt格式（Anki纯文本格式）

    Args:
        file_path: 文件路径
        card_type: 卡片类型（可选）

    Returns:
        卡片列表
    """
    cards = []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 解析文件头
    columns = []
    guid_column = 1
    tags_column = None
    separator = "\t"

    for line in lines:
        line = line.strip()
        if line.startswith("#separator:"):
            sep_str = line.split(":", 1)[1].strip()
            # 处理 "tab" 字符串
            if sep_str.lower() == "tab":
                separator = "\t"
            else:
                separator = sep_str
        elif line.startswith("#columns:"):
            col_str = line.split(":", 1)[1].strip()
            # 处理制表符分隔的列名
            if "\t" in col_str:
                columns = col_str.split("\t")
            else:
                columns = col_str.split(separator)
        elif line.startswith("#guid column:"):
            guid_column = int(line.split(":", 1)[1].strip())
        elif line.startswith("#tags column:"):
            tags_column = int(line.split(":", 1)[1].strip())
        elif line and not line.startswith("#"):
            # 数据行
            values = line.split("\t" if separator == "\t" else separator)
            if len(values) < len(columns):
                continue

            # 构建字段字典
            fields = {}
            for i, col in enumerate(columns):
                if i < len(values):
                    fields[col] = values[i]

            # 移除GUID列（如果存在）
            if "GUID" in fields:
                del fields["GUID"]

            # 处理Tags字段
            tags = []
            if tags_column and tags_column <= len(values):
                tags_str = values[tags_column - 1].strip()
                if tags_str:
                    tags = [t.strip() for t in tags_str.split()]

            # 推断卡片类型
            inferred_type = card_type
            if not inferred_type:
                inferred_type = infer_card_type_from_fields(fields)

            if inferred_type:
                card = map_fields_to_card(fields, inferred_type)
                if card and tags:
                    card.tags = tags
                if card:
                    cards.append(card)

    logger.info(f"从 {file_path} 读取了 {len(cards)} 张卡片")
    return cards


def read_items_with_type_txt(file_path: Path) -> List[Card]:
    """
    读取items.with_type.txt格式（包含Notetype列）

    Args:
        file_path: 文件路径

    Returns:
        卡片列表
    """
    cards = []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 解析文件头
    columns = []
    guid_column = 1
    notetype_column = None
    tags_column = None
    separator = "\t"

    for line in lines:
        line = line.strip()
        if line.startswith("#separator:"):
            sep_str = line.split(":", 1)[1].strip()
            # 处理 "tab" 字符串
            if sep_str.lower() == "tab":
                separator = "\t"
            else:
                separator = sep_str
        elif line.startswith("#columns:"):
            col_str = line.split(":", 1)[1].strip()
            # 处理制表符分隔的列名
            if "\t" in col_str:
                columns = col_str.split("\t")
            else:
                columns = col_str.split(separator)
        elif line.startswith("#guid column:"):
            guid_column = int(line.split(":", 1)[1].strip())
        elif line.startswith("#notetype column:"):
            notetype_column = int(line.split(":", 1)[1].strip())
        elif line.startswith("#tags column:"):
            tags_column = int(line.split(":", 1)[1].strip())
        elif line and not line.startswith("#"):
            # 数据行
            values = line.split("\t" if separator == "\t" else separator)
            if len(values) < len(columns):
                continue

            # 获取Notetype
            card_type_str = None
            if notetype_column and notetype_column <= len(values):
                notetype_value = values[notetype_column - 1].strip()
                # 映射Notetype到CardType
                card_type_str = map_notetype_to_card_type(notetype_value)

            # 构建字段字典
            fields = {}
            for i, col in enumerate(columns):
                if i < len(values) and col not in ("GUID", "Notetype"):
                    fields[col] = values[i]

            # 处理Tags字段
            tags = []
            if tags_column and tags_column <= len(values):
                tags_str = values[tags_column - 1].strip()
                if tags_str:
                    tags = [t.strip() for t in tags_str.split()]

            # 确定卡片类型
            card_type = None
            if card_type_str:
                try:
                    card_type = CardType(card_type_str)
                except ValueError:
                    pass

            if not card_type:
                card_type = infer_card_type_from_fields(fields)

            if card_type:
                card = map_fields_to_card(fields, card_type)
                if card and tags:
                    card.tags = tags
                if card:
                    cards.append(card)

    logger.info(f"从 {file_path} 读取了 {len(cards)} 张卡片")
    return cards


def read_csv(file_path: Path, card_type: Optional[CardType] = None) -> List[Card]:
    """
    读取CSV格式

    Args:
        file_path: 文件路径
        card_type: 卡片类型（可选）

    Returns:
        卡片列表
    """
    cards = []

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 处理Tags字段（可能是分号或逗号分隔）
            tags = []
            if "Tags" in row and row["Tags"]:
                tags_str = row["Tags"]
                if ";" in tags_str:
                    tags = [t.strip() for t in tags_str.split(";")]
                elif "," in tags_str:
                    tags = [t.strip() for t in tags_str.split(",")]
                else:
                    tags = [tags_str.strip()]

            # 移除Type列（如果存在）
            fields = {k: v for k, v in row.items() if k != "Type"}

            # 推断卡片类型
            inferred_type = card_type
            if not inferred_type and "Type" in row:
                try:
                    inferred_type = CardType(row["Type"].lower())
                except ValueError:
                    pass

            if not inferred_type:
                inferred_type = infer_card_type_from_fields(fields)

            if inferred_type:
                card = map_fields_to_card(fields, inferred_type)
                if card and tags:
                    card.tags = tags
                if card:
                    cards.append(card)

    logger.info(f"从 {file_path} 读取了 {len(cards)} 张卡片")
    return cards


def read_apkg(file_path: Path) -> List[Card]:
    """
    读取APKG格式（Anki包文件）

    Args:
        file_path: 文件路径

    Returns:
        卡片列表
    """
    # TODO: 实现APKG读取
    # 可以使用 genanki 或 pyanki 库
    # 或者使用现有的 parse_apkg.py
    raise NotImplementedError("APKG格式读取尚未实现，请先转换为其他格式")


def infer_card_type_from_fields(fields: dict) -> Optional[CardType]:
    """
    从字段推断卡片类型

    Args:
        fields: 字段字典

    Returns:
        卡片类型，如果无法推断则返回None
    """
    # 检查是否有Cloze标记
    for value in fields.values():
        if isinstance(value, str) and "{{c" in value:
            return CardType.CLOZE

    # 检查字段名称
    field_names = [k.lower() for k in fields.keys()]

    if "text" in field_names:
        return CardType.CLOZE
    elif "front" in field_names and "back" in field_names:
        if "options" in field_names:
            return CardType.MCQ
        else:
            return CardType.BASIC
    elif "question" in field_names and "options" in field_names:
        return CardType.MCQ

    # 默认返回Basic
    return CardType.BASIC


def map_notetype_to_card_type(notetype: str) -> Optional[str]:
    """
    将Notetype字符串映射到CardType枚举值

    Args:
        notetype: Notetype字符串（如 "Basic Card", "Cloze Card"）

    Returns:
        CardType枚举值字符串（如 "basic", "cloze"）
    """
    notetype_lower = notetype.lower()
    if "basic" in notetype_lower:
        return "basic"
    elif "cloze" in notetype_lower:
        return "cloze"
    elif "mcq" in notetype_lower or "multiple" in notetype_lower:
        return "mcq"
    return None
