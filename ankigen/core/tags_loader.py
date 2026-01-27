"""
标签加载模块

用于解析 tags.yml 文件，提取基础标签和可选标签。
"""

from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from loguru import logger

from ankigen.core.config_loader import load_yaml_config


def flatten_tags(tags: Any, prefix: str = "") -> List[str]:
    """
    展平嵌套的标签结构
    
    Args:
        tags: 标签数据（可能是字典、列表或字符串）
        prefix: 前缀（用于构建层级标签）
        
    Returns:
        展平后的标签列表
    """
    result = []
    
    if isinstance(tags, dict):
        for key, value in tags.items():
            # 构建当前标签
            current_tag = f"{prefix}{key}" if prefix else key
            result.append(current_tag)
            
            # 递归处理子标签
            if isinstance(value, (dict, list)):
                result.extend(flatten_tags(value, f"{current_tag}::"))
    elif isinstance(tags, list):
        for item in tags:
            result.extend(flatten_tags(item, prefix))
    elif isinstance(tags, str):
        # 字符串标签
        tag = f"{prefix}{tags}" if prefix else tags
        result.append(tag)
    
    return result


def load_tags_file(tags_file: Path) -> Dict[str, Any]:
    """
    加载并解析 tags.yml 文件
    
    Args:
        tags_file: tags.yml 文件路径
        
    Returns:
        包含以下键的字典：
        - basic_tags: 基础标签列表（必须包含）
        - optional_tags: 可选标签列表（展平后的所有标签）
        
    Raises:
        FileNotFoundError: 文件不存在
        yaml.YAMLError: YAML解析错误
    """
    if not tags_file.exists():
        raise FileNotFoundError(f"标签文件不存在: {tags_file}")
    
    try:
        tags_data = load_yaml_config(tags_file)
    except Exception as e:
        logger.error(f"加载标签文件失败: {e}")
        raise
    
    # 提取基础标签
    basic_tags = []
    if "BasicTags" in tags_data:
        basic_tag_value = tags_data["BasicTags"]
        if isinstance(basic_tag_value, str):
            basic_tags = [basic_tag_value]
        elif isinstance(basic_tag_value, list):
            basic_tags = basic_tag_value
        else:
            logger.warning(f"BasicTags 格式不正确，期望字符串或列表，得到: {type(basic_tag_value)}")
    
    # 提取并展平可选标签
    optional_tags = []
    if "Tags" in tags_data:
        tags_structure = tags_data["Tags"]
        optional_tags = flatten_tags(tags_structure)
    
    logger.info(f"已加载标签文件: {tags_file}")
    logger.info(f"  基础标签: {basic_tags}")
    logger.info(f"  可选标签数量: {len(optional_tags)}")
    
    return {
        "basic_tags": basic_tags,
        "optional_tags": optional_tags,
    }
