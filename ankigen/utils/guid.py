"""
GUID生成工具模块

用于根据卡片字段内容生成唯一标识符（GUID）。
"""

import hashlib
from typing import Dict


def generate_guid(fields: Dict[str, str], template_name: str, exclude_tags: bool = True) -> str:
    """
    生成GUID（全局唯一标识符）

    根据模板名称和字段内容生成MD5哈希值作为GUID。
    相同的内容会生成相同的GUID，用于去重和唯一标识。

    Args:
        fields: 字段字典，键为字段名，值为字段内容
        template_name: 模板名称
        exclude_tags: 是否排除Tags字段（默认True）

    Returns:
        GUID字符串（MD5哈希的前8位）
    """
    # 构建哈希内容：模板名称 + 所有字段值（排除Tags）
    content_parts = [template_name]

    # 按字段名排序，确保相同内容生成相同GUID
    for key in sorted(fields.keys()):
        if exclude_tags and key.lower() in ("tags", "标签"):
            continue
        value = str(fields.get(key, ""))
        content_parts.append(f"{key}:{value}")

    # 合并所有内容
    content = "|".join(content_parts)

    # 生成MD5哈希
    hash_obj = hashlib.md5(content.encode("utf-8"))
    guid = hash_obj.hexdigest()[:8]  # 使用前8位作为GUID

    return guid


def generate_guid_from_card_fields(
    fields: Dict[str, str], card_type: str, exclude_tags: bool = True
) -> str:
    """
    从卡片字段生成GUID（便捷函数）

    Args:
        fields: 字段字典
        card_type: 卡片类型（用于确定模板名称）
        exclude_tags: 是否排除Tags字段

    Returns:
        GUID字符串
    """
    # 卡片类型到模板名称的映射
    type_to_template = {
        "basic": "Basic Card",
        "cloze": "Cloze Card",
        "mcq": "Basic Card",  # MCQ暂时使用Basic Card模板
    }

    template_name = type_to_template.get(card_type.lower(), "Basic Card")
    return generate_guid(fields, template_name, exclude_tags)
