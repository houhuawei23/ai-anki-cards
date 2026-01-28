"""
配置处理模块

负责加载、合并和验证配置。
"""

from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from ankigen.core.config_loader import load_config
from ankigen.exceptions import ConfigurationError
from ankigen.models.config import AppConfig, LLMProvider


def load_and_merge_config(
    config_path: Optional[Path],
    provider: Optional[str],
    model_name: Optional[str],
    card_type: Optional[str],
    num_cards: Optional[int],
    prompt: Optional[str],
    export_format: Optional[str],
    deck_name: Optional[str],
    tags_file: Optional[Path],
    output: Path,
) -> AppConfig:
    """
    加载配置并合并命令行参数

    Args:
        config_path: 配置文件路径
        provider: LLM提供商
        model_name: 模型名称
        card_type: 卡片类型
        num_cards: 卡片数量
        prompt: 自定义提示词
        export_format: 导出格式
        deck_name: 牌组名称
        tags_file: 标签文件路径
        output: 输出路径（用于自动判断格式）

    Returns:
        合并后的配置对象

    Raises:
        typer.Exit: 如果配置加载或合并失败
    """
    # 加载配置
    try:
        app_config = load_config(config_path=config_path)
    except ConfigurationError as e:
        logger.exception(f"配置错误: {e}")
        typer.echo(f"错误: 配置错误: {e}", err=True)
        typer.echo("请检查配置文件格式是否正确", err=True)
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"加载配置失败: {e}")
        typer.echo(f"错误: 加载配置失败: {e}", err=True)
        typer.echo("请检查配置文件格式是否正确", err=True)
        raise typer.Exit(1)

    # 覆盖命令行参数
    try:
        if provider:
            app_config.llm.provider = LLMProvider(provider.lower())
        if model_name:
            app_config.llm.model_name = model_name
        if card_type:
            app_config.generation.card_type = card_type
        if num_cards:
            app_config.generation.card_count = num_cards
        if prompt:
            app_config.generation.custom_prompt = prompt
        if export_format:
            app_config.export.format = export_format
        elif not app_config.export.format or app_config.export.format == "apkg":
            # 如果未指定格式，根据输出文件扩展名自动判断
            ext = output.suffix.lower()
            format_map = {
                ".apkg": "apkg",
                ".txt": "txt",
                ".csv": "csv",
                ".json": "json",
                ".jsonl": "jsonl",
            }
            if ext in format_map:
                app_config.export.format = format_map[ext]
                logger.debug(f"根据文件扩展名自动判断格式: {ext} -> {app_config.export.format}")
        if deck_name:
            app_config.export.deck_name = deck_name
        if tags_file:
            app_config.generation.tags_file = str(tags_file)
    except (ConfigurationError, ValueError) as e:
        logger.exception(f"配置参数处理失败: {e}")
        typer.echo(f"错误: 配置参数处理失败: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"配置参数处理失败: {e}")
        typer.echo(f"错误: 配置参数处理失败: {e}", err=True)
        raise typer.Exit(1)

    return app_config


def validate_config(app_config: AppConfig) -> None:
    """
    验证配置有效性

    Args:
        app_config: 配置对象

    Raises:
        typer.Exit: 如果配置无效
    """
    if not app_config.llm.get_api_key():
        typer.echo(
            "错误: 未设置API密钥。请设置环境变量或使用配置文件。",
            err=True,
        )
        raise typer.Exit(1)
