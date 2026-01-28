"""
提示词模板管理模块

负责加载和渲染卡片生成的提示词模板。
"""

from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from loguru import logger

from ankigen.core.template_loader import get_template_dir
from ankigen.exceptions import TemplateError
from ankigen.models.card import CardType


class PromptTemplate:
    """提示词模板管理器

    负责从模板文件加载和渲染提示词。
    """

    def __init__(self) -> None:
        """初始化模板管理器

        模板从 cards_templates 目录下的各个卡片类型目录中加载 prompt.j2。
        """
        self.base_dir = Path(__file__).parent.parent / "cards_templates"
        self.env = Environment(
            loader=FileSystemLoader(str(self.base_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        template_name: str,
        content: str,
        card_count: int,
        difficulty: str = "medium",
        custom_prompt: Optional[str] = None,
        basic_tags: Optional[List[str]] = None,
        optional_tags: Optional[List[str]] = None,
    ) -> str:
        """渲染模板

        Args:
            template_name: 卡片类型名称（basic/cloze/mcq）
            content: 要生成卡片的内容
            card_count: 卡片数量
            difficulty: 难度级别
            custom_prompt: 自定义提示词，如果提供则覆盖模板
            basic_tags: 基础标签列表
            optional_tags: 可选标签列表

        Returns:
            渲染后的提示词

        Raises:
            TemplateError: 当模板加载或渲染失败时
        """
        if custom_prompt:
            # 使用自定义提示词，但仍需要注入变量
            try:
                template = Template(custom_prompt)
                return template.render(
                    content=content,
                    card_count=card_count,
                    difficulty=difficulty,
                    basic_tags=basic_tags or [],
                    optional_tags=optional_tags or [],
                )
            except Exception as e:
                raise TemplateError(f"渲染自定义提示词失败: {e}") from e

        # 根据卡片类型确定模板目录
        try:
            card_type = CardType(template_name)
        except ValueError as e:
            raise TemplateError(f"无效的卡片类型: {template_name}") from e

        template_dir = get_template_dir(card_type)

        if not template_dir:
            raise TemplateError(
                f"未找到卡片类型 {template_name} 的模板目录。"
                f"请确保 cards_templates/{template_name}/prompt.j2 文件存在"
            )

        # 加载 prompt.j2 文件
        template_path = template_dir / "prompt.j2"
        if not template_path.exists():
            logger.warning(f"模板文件不存在: {template_path}")
            raise TemplateError(f"模板文件不存在: {template_path}")

        # 使用相对路径加载模板
        try:
            relative_path = template_path.relative_to(self.base_dir)
            template = self.env.get_template(str(relative_path))

            return template.render(
                content=content,
                card_count=card_count,
                difficulty=difficulty,
                basic_tags=basic_tags or [],
                optional_tags=optional_tags or [],
            )
        except Exception as e:
            raise TemplateError(f"渲染模板失败: {e}") from e
