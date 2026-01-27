"""
预览处理模块

负责显示预览信息和提示词预览。
"""

from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from ankigen.core.card_generator import CardGenerator
from ankigen.core.exporter import _add_type_count_suffix
from ankigen.core.template_loader import get_template_dir, get_template_meta
from ankigen.core.tags_loader import load_tags_file
from ankigen.models.card import BasicCard, CardType, ClozeCard, MCQCard, MCQOption
from ankigen.models.config import AppConfig


def show_dry_run_preview(
    input_path: Path,
    output_path: Path,
    content: str,
    app_config: AppConfig,
    card_generator: Optional[CardGenerator] = None,
) -> int:
    """
    显示预览信息
    
    Args:
        input_path: 输入路径
        output_path: 输出路径
        content: 输入内容
        app_config: 应用配置
        card_generator: 卡片生成器（可选，用于估算）
        
    Returns:
        估算的卡片数量
    """
    typer.echo("\n" + "=" * 60)
    typer.echo("=== 预览模式（DRY RUN）===")
    typer.echo("=" * 60)

    # 输入信息
    typer.echo("\n【输入信息】")
    typer.echo(f"  输入路径: {input_path}")
    typer.echo(f"  输入类型: {'文件' if input_path.is_file() else '目录'}")
    if input_path.is_file():
        file_size = input_path.stat().st_size
        typer.echo(
            f"  文件大小: {file_size:,} 字节 ({file_size / 1024:.2f} KB)"
        )
    typer.echo(f"  内容长度: {len(content):,} 字符")
    typer.echo(f"  内容行数: {len(content.splitlines()):,} 行")

    # 内容预览
    content_preview = content[:200].replace("\n", "\\n")
    if len(content) > 200:
        content_preview += "..."
    typer.echo(f"  内容预览: {content_preview}")

    # 生成配置
    typer.echo("\n【生成配置】")
    typer.echo(f"  卡片类型: {app_config.generation.card_type}")

    # 估算卡片数量
    card_type_enum = CardType(app_config.generation.card_type)
    card_count = 0

    if app_config.generation.card_count:
        estimated_count = app_config.generation.card_count
        typer.echo(f"  卡片数量: {estimated_count} (用户指定)")
        card_count = estimated_count
    else:
        if card_generator:
            total_estimated = card_generator._estimate_total_card_count(content)
            single_estimated = card_generator._estimate_card_count(content)
            max_cards_per_request = (
                app_config.generation.max_cards_per_request
            )
            max_concurrent = app_config.generation.max_concurrent_requests
            typer.echo(f"  卡片数量: {total_estimated} (自动估算)")
            typer.echo(
                f"  单次限制: {single_estimated} 张 (最多{max_cards_per_request}张)"
            )
            card_count = total_estimated
            if total_estimated > max_cards_per_request:
                num_chunks = (
                    total_estimated + max_cards_per_request - 1
                ) // max_cards_per_request
                typer.echo(f"  预计切分: {num_chunks} 个内容块")
                typer.echo(
                    f"  预计API调用: {num_chunks} 次 (并发执行，最大{max_concurrent}个并发)"
                )
            else:
                typer.echo("  预计API调用: 1 次")
        else:
            # 如果没有生成器，使用简单估算
            char_count = len(content)
            estimated = max(5, char_count // 500)
            typer.echo(f"  卡片数量: {estimated} (简单估算)")
            card_count = estimated

    typer.echo(f"  难度级别: {app_config.generation.difficulty}")
    typer.echo(
        f"  启用去重: {'是' if app_config.generation.enable_deduplication else '否'}"
    )
    typer.echo(
        f"  启用质量过滤: {'是' if app_config.generation.enable_quality_filter else '否'}"
    )
    if app_config.generation.custom_prompt:
        prompt_preview = app_config.generation.custom_prompt[:100]
        if len(app_config.generation.custom_prompt) > 100:
            prompt_preview += "..."
        typer.echo(f"  自定义提示词: {prompt_preview}")
    else:
        typer.echo("  自定义提示词: 否 (使用模板)")

    # LLM配置
    typer.echo("\n【LLM配置】")
    typer.echo(f"  提供商: {app_config.llm.provider.value}")
    typer.echo(f"  模型名称: {app_config.llm.model_name}")
    typer.echo(
        f"  API密钥: {'已设置' if app_config.llm.get_api_key() else '未设置'}"
    )
    if app_config.llm.base_url:
        typer.echo(f"  基础URL: {app_config.llm.base_url}")
    else:
        typer.echo("  基础URL: 默认")
    typer.echo(f"  温度参数: {app_config.llm.temperature}")
    typer.echo(f"  最大Token: {app_config.llm.max_tokens:,}")
    typer.echo(f"  Top-p: {app_config.llm.top_p}")
    typer.echo(f"  超时时间: {app_config.llm.timeout} 秒")
    typer.echo(f"  最大重试: {app_config.llm.max_retries} 次")

    # 导出配置
    typer.echo("\n【导出配置】")
    typer.echo(f"  导出格式: {app_config.export.format}")

    # 计算最终输出文件名（包括类型和数量后缀）
    final_output_path = _calculate_final_output_path(
        output_path, card_type_enum, card_count
    )

    typer.echo(f"  输出路径: {output_path}")
    typer.echo(f"  最终文件名: {final_output_path.name}")
    typer.echo(f"  牌组名称: {app_config.export.deck_name}")
    if app_config.export.deck_description:
        typer.echo(
            f"  牌组描述: {app_config.export.deck_description[:50]}..."
        )

    # 模板信息
    typer.echo("\n【模板信息】")
    template_dir = get_template_dir(card_type_enum)
    template_meta = get_template_meta(card_type_enum)
    if template_dir:
        typer.echo(f"  模板目录: {template_dir}")
    if template_meta:
        typer.echo(f"  模板名称: {template_meta.name}")
        typer.echo(f"  模板字段数: {len(template_meta.fields)}")
        fields_preview = ", ".join(template_meta.fields[:5])
        if len(template_meta.fields) > 5:
            fields_preview += "..."
        typer.echo(f"  模板字段: {fields_preview}")

    # 缓存信息
    typer.echo("\n【缓存信息】")
    typer.echo("  缓存状态: 启用")

    # 总结
    typer.echo("\n" + "=" * 60)
    typer.echo("预览完成，未实际调用API")
    typer.echo("=" * 60 + "\n")

    return card_count


def show_prompt_preview(
    content: str,
    app_config: AppConfig,
    card_count: int,
    card_generator: CardGenerator,
) -> None:
    """
    显示提示词预览
    
    Args:
        content: 输入内容
        app_config: 应用配置
        card_count: 卡片数量
        card_generator: 卡片生成器
    """
    typer.echo("\n【生成的提示词】")
    try:
        # 加载标签文件（如果指定）
        basic_tags = []
        optional_tags = []
        if app_config.generation.tags_file:
            try:
                tags_path = Path(app_config.generation.tags_file)
                tags_data = load_tags_file(tags_path)
                basic_tags = tags_data.get("basic_tags", [])
                optional_tags = tags_data.get("optional_tags", [])
            except Exception as e:
                logger.warning(f"加载标签文件失败: {e}")

        # 生成提示词
        prompt = card_generator.template_manager.render(
            template_name=app_config.generation.card_type,
            content=content,
            card_count=card_count,
            difficulty=app_config.generation.difficulty,
            custom_prompt=app_config.generation.custom_prompt,
            basic_tags=basic_tags,
            optional_tags=optional_tags,
        )

        typer.echo("=" * 60)
        typer.echo(prompt)
        typer.echo("=" * 60)
    except Exception as e:
        logger.exception(f"生成提示词失败: {e}")
        typer.echo(f"  错误: 无法生成提示词 - {e}", err=True)


def _calculate_final_output_path(
    output_path: Path, card_type_enum: CardType, card_count: int
) -> Path:
    """
    计算最终输出路径（包括类型和数量后缀）
    
    Args:
        output_path: 原始输出路径
        card_type_enum: 卡片类型枚举
        card_count: 卡片数量
        
    Returns:
        最终输出路径
    """
    # 创建临时卡片列表用于计算文件名
    temp_cards = []
    if card_type_enum == CardType.BASIC:
        temp_cards = [BasicCard(front="temp", back="temp")] * min(
            card_count, 1
        )
    elif card_type_enum == CardType.CLOZE:
        temp_cards = [
            ClozeCard(front="temp{{c1::test}}", back="temp")
        ] * min(card_count, 1)
    elif card_type_enum == CardType.MCQ:
        temp_cards = [
            MCQCard(
                front="temp",
                back="",
                options=[
                    MCQOption(text="A", is_correct=True),
                    MCQOption(text="B", is_correct=False),
                ],
            )
        ] * min(card_count, 1)

    if temp_cards:
        final_output_path = _add_type_count_suffix(output_path, temp_cards)
        # 更新卡片数量
        final_stem = final_output_path.stem
        final_suffix = final_output_path.suffix
        # 替换数量部分
        parts = final_stem.rsplit(".", 2)
        if len(parts) == 3 and parts[-1].isdigit():
            final_stem = f"{parts[0]}.{parts[1]}.{card_count}"
        final_output_path = (
            final_output_path.parent / f"{final_stem}{final_suffix}"
        )
    else:
        final_output_path = output_path

    return final_output_path
