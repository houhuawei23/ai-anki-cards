"""
导出协调模块

负责协调导出操作，包括确定输出路径和导出多种格式。
"""

from pathlib import Path
from typing import List, Optional

import typer
from loguru import logger

from ankigen.core.exporter import (
    _add_type_count_suffix,
    export_api_responses,
    export_cards,
    export_parsed_cards_json,
)
from ankigen.core.card_generator import GenerationStats
from ankigen.models.card import Card
from ankigen.models.config import AppConfig


def determine_output_dir(output: Path, all_formats: bool) -> Path:
    """
    确定输出目录
    
    Args:
        output: 输出路径
        all_formats: 是否导出所有格式
        
    Returns:
        输出目录路径
    """
    if all_formats:
        # 导出所有格式时，确定输出目录
        if output.is_dir():
            output_dir = Path(output)
        elif not output.suffix:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = output.parent
            output_dir.mkdir(parents=True, exist_ok=True)
    else:
        # 单一格式导出时，使用输出路径的目录
        if output.is_dir():
            output_dir = Path(output)
        else:
            output_dir = output.parent
            output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir


def export_all_formats(
    cards: List[Card],
    output: Path,
    input_path: Path,
    app_config: AppConfig,
    stats: Optional[GenerationStats] = None,
) -> List[Path]:
    """
    导出所有格式
    
    Args:
        cards: 卡片列表
        output: 输出路径
        input_path: 输入路径（用于确定基础文件名）
        app_config: 应用配置
        stats: 生成统计信息（可选）
        
    Returns:
        已导出的文件路径列表
    """
    # 确定输出目录和文件名基础
    if output.is_dir():
        # 如果输出路径是已存在的目录
        output_dir = Path(output)
        # 使用输入文件名作为基础名，如果没有输入文件则使用默认名
        if input_path.is_file():
            output_stem = input_path.stem
        else:
            output_stem = "items"
    elif not output.suffix:
        # 如果输出路径没有扩展名（可能是目录名）
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        # 使用输入文件名作为基础名，如果没有输入文件则使用默认名
        if input_path.is_file():
            output_stem = input_path.stem
        else:
            output_stem = "items"
    else:
        # 如果输出路径有扩展名，使用输出路径的目录和基础名
        output_stem = output.stem
        output_dir = output.parent
        output_dir.mkdir(parents=True, exist_ok=True)

    export_formats = [
        ("items_yml", ".yml"),
        ("items_txt", ".txt"),
        ("items_with_type_txt", ".with_type.txt"),
        ("apkg", ".apkg"),
        ("csv", ".csv"),
    ]

    typer.echo(f"\n正在导出 {len(cards)} 张卡片到多种格式...")
    typer.echo(f"输出目录: {output_dir}")
    exported_files = []

    for format_name, ext in export_formats:
        output_file = output_dir / f"{output_stem}{ext}"
        try:
            export_cards(
                cards=cards,
                output_path=output_file,
                format=format_name,
                deck_name=app_config.export.deck_name,
                deck_description=app_config.export.deck_description,
            )
            exported_files.append(output_file)
            typer.echo(f"  ✓ {format_name}: {output_file}")
        except Exception as e:
            logger.error(f"导出 {format_name} 失败: {e}")
            typer.echo(f"  ✗ {format_name}: 导出失败 - {e}", err=True)

    # 导出 API 响应 JSON（如果存在）
    if stats and stats.api_responses:
        api_output_file = (
            output_dir / f"{output_stem}.api_response.json"
        )
        try:
            export_api_responses(
                api_responses=stats.api_responses,
                output_path=api_output_file,
                add_type_count_suffix=True,  # 添加类型和数量后缀
                card_type=app_config.generation.card_type,
                card_count=len(cards),
            )
            exported_files.append(api_output_file)
            typer.echo(f"  ✓ api_response: {api_output_file}")
        except Exception as e:
            logger.error(f"导出 API 响应失败: {e}")
            typer.echo(f"  ✗ api_response: 导出失败 - {e}", err=True)

    # 导出提示词文件（如果存在）
    if stats and stats.prompts:
        prompt_output_file = output_dir / f"{output_stem}.prompt.md"
        try:
            with open(prompt_output_file, "w", encoding="utf-8") as f:
                for i, prompt in enumerate(stats.prompts, 1):
                    if len(stats.prompts) > 1:
                        f.write(
                            f"# 提示词 {i}/{len(stats.prompts)}\n\n"
                        )
                    f.write("```\n")
                    f.write(prompt)
                    f.write("\n```\n")
                    if i < len(stats.prompts):
                        f.write("\n---\n\n")
            exported_files.append(prompt_output_file)
            typer.echo(f"  ✓ prompt: {prompt_output_file}")
        except Exception as e:
            logger.error(f"导出提示词文件失败: {e}")
            typer.echo(f"  ✗ prompt: 导出失败 - {e}", err=True)

    # 导出解析后的卡片 JSON
    parsed_output_file = output_dir / f"{output_stem}.parsed.json"
    try:
        export_parsed_cards_json(
            cards=cards,
            output_path=parsed_output_file,
            add_type_count_suffix=True,  # 添加类型和数量后缀
            card_type=app_config.generation.card_type,
            card_count=len(cards),
        )
        exported_files.append(parsed_output_file)
        typer.echo(f"  ✓ parsed_cards: {parsed_output_file}")
    except Exception as e:
        logger.error(f"导出解析后的卡片 JSON 失败: {e}")
        typer.echo(f"  ✗ parsed_cards: 导出失败 - {e}", err=True)

    typer.echo(
        f"\n✓ 成功导出 {len(exported_files)} 种格式到 {output_dir}"
    )
    return exported_files


def export_single_format(
    cards: List[Card],
    output: Path,
    app_config: AppConfig,
    stats: Optional[GenerationStats] = None,
) -> None:
    """
    导出单一格式
    
    Args:
        cards: 卡片列表
        output: 输出路径
        app_config: 应用配置
        stats: 生成统计信息（可选）
    """
    typer.echo(f"\n正在导出 {len(cards)} 张卡片到 {output}...")
    export_cards(
        cards=cards,
        output_path=output,
        format=app_config.export.format,
        deck_name=app_config.export.deck_name,
        deck_description=app_config.export.deck_description,
    )

    # 导出 API 响应 JSON（如果存在）
    if stats and stats.api_responses:
        # 使用输出路径的目录和基础名
        api_output_file = (
            output.parent / f"{output.stem}.api_response.json"
        )
        try:
            export_api_responses(
                api_responses=stats.api_responses,
                output_path=api_output_file,
                add_type_count_suffix=True,  # 添加类型和数量后缀
                card_type=app_config.generation.card_type,
                card_count=len(cards),
            )
            typer.echo(f"已导出 API 响应到: {api_output_file}")
        except Exception as e:
            logger.error(f"导出 API 响应失败: {e}")

    # 导出解析后的卡片 JSON
    parsed_output_file = output.parent / f"{output.stem}.parsed.json"
    try:
        export_parsed_cards_json(
            cards=cards,
            output_path=parsed_output_file,
            add_type_count_suffix=True,  # 添加类型和数量后缀
            card_type=app_config.generation.card_type,
            card_count=len(cards),
        )
        typer.echo(f"已导出解析后的卡片 JSON 到: {parsed_output_file}")
    except Exception as e:
        logger.error(f"导出解析后的卡片 JSON 失败: {e}")

    typer.echo(f"\n✓ 成功生成并导出 {len(cards)} 张卡片到 {output}")
