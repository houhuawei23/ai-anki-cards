"""
CLI接口模块

使用Typer实现命令行界面。
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from ankigen.cli.config_handler import load_and_merge_config, validate_config
from ankigen.cli.export_coordinator import (
    determine_output_dir,
    export_all_formats,
    export_single_format,
)
from ankigen.cli.input_handler import parse_input, validate_input
from ankigen.cli.preview_handler import show_dry_run_preview, show_prompt_preview
from ankigen.core.card_generator import CardGenerator
from ankigen.core.card_reader import detect_format, read_cards
from ankigen.core.config_loader import load_config, save_config
from ankigen.core.exporter import export_api_responses, export_cards
from ankigen.exceptions import (
    CardGenerationError,
    ConfigurationError,
    ExportError,
    ParsingError,
)
from ankigen.models.card import CardType
from ankigen.models.config import AppConfig
from ankigen.utils.cache import FileCache
from ankigen.utils.logger import setup_logger

app = typer.Typer(
    name="ankigen",
    help="Anki卡片批量生成工具 - 从文本/Markdown文件生成Anki卡片",
    add_completion=False,
)


@app.command()
def generate(
    input: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="输入文件或目录路径",
        exists=True,
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="输出文件路径",
    ),
    card_type: str = typer.Option(
        "basic",
        "--card-type",
        "-t",
        help="卡片类型 (basic/cloze/mcq)",
    ),
    num_cards: Optional[int] = typer.Option(
        None,
        "--num-cards",
        "-n",
        help="卡片数量（如果不指定则自动估算）",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="LLM提供商 (openai/deepseek/ollama/custom)",
    ),
    model_name: Optional[str] = typer.Option(
        None,
        "--model-name",
        "-m",
        help="模型名称",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "-p",
        help="自定义提示词",
    ),
    export_format: str = typer.Option(
        "apkg",
        "--export-format",
        help="导出格式 (apkg/txt/csv/json/jsonl)",
    ),
    deck_name: Optional[str] = typer.Option(
        None,
        "--deck-name",
        help="牌组名称（仅用于apkg格式）",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="预览模式，不实际调用API",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="显示详细日志",
    ),
    all_formats: bool = typer.Option(
        False,
        "--all",
        help="导出所有格式（items.yml, items.txt, items.with_type.txt, apkg, csv）",
    ),
    tags_file: Optional[Path] = typer.Option(
        None,
        "--tags-file",
        help="标签文件路径（tags.yml），用于指定允许使用的标签",
        exists=False,
    ),
    show_prompt: bool = typer.Option(
        False,
        "--show-prompt",
        help="在命令行中打印使用 jinja 生成的提示词",
    ),
):
    """
    生成Anki卡片

    从输入文件或目录生成Anki卡片并导出为指定格式。
    """
    # 设置日志（自动创建日志文件）
    log_file_path = setup_logger(
        level="DEBUG" if verbose else "INFO",
        verbose=verbose,
        auto_log_file=True,
    )
    if log_file_path:
        typer.echo(f"日志文件: {log_file_path}", err=True)

    try:
        # 加载并合并配置
        app_config = load_and_merge_config(
            config_path=config,
            provider=provider,
            model_name=model_name,
            card_type=card_type,
            num_cards=num_cards,
            prompt=prompt,
            export_format=export_format,
            deck_name=deck_name,
            tags_file=tags_file,
            output=output,
        )

        # 验证配置
        validate_config(app_config)

        # 解析输入文件
        typer.echo(f"正在解析输入: {input}")
        content = parse_input(input)
        validate_input(content)
        typer.echo(f"已解析内容，长度: {len(content)} 字符")

        # 预览模式
        if dry_run:
            # 创建临时生成器用于估算（dry-run模式下不使用缓存）
            card_generator = CardGenerator.__new__(CardGenerator)
            card_count = show_dry_run_preview(
                input_path=input,
                output_path=output,
                content=content,
                app_config=app_config,
                card_generator=card_generator,
            )

            # 生成并显示提示词（如果指定）
            if show_prompt:
                # 创建实际的生成器实例以生成提示词
                card_generator = CardGenerator(
                    llm_config=app_config.llm,
                    cache=None,  # dry-run 模式下不使用缓存
                )
                show_prompt_preview(
                    content=content,
                    app_config=app_config,
                    card_count=card_count,
                    card_generator=card_generator,
                )
            return

        # 创建缓存
        cache = FileCache()

        # 创建卡片生成器
        card_generator = CardGenerator(
            llm_config=app_config.llm,
            cache=cache,
        )

        # 确定输出目录（用于立即保存 API 响应）
        output_dir = determine_output_dir(output, all_formats)

        # 生成卡片（加强错误处理）
        typer.echo("\n正在生成卡片...")
        try:
            result = asyncio.run(
                card_generator.generate_cards(content, app_config.generation, output_dir)
            )
        except CardGenerationError as e:
            logger.error(f"卡片生成错误: {e}")
            typer.echo(f"错误: 卡片生成失败: {e}", err=True)
            typer.echo("请检查日志以获取更多信息", err=True)
            raise typer.Exit(1)
        except Exception as e:
            logger.error(f"生成卡片时发生错误: {e}")
            import traceback

            logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            typer.echo(f"错误: 生成卡片失败: {e}", err=True)
            typer.echo("请检查日志以获取更多信息", err=True)
            raise typer.Exit(1)

        # 处理返回结果（tuple: cards, stats）
        try:
            cards, stats = result
        except (ValueError, TypeError) as e:
            logger.error(f"处理生成结果时发生错误: {e}")
            import traceback

            logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            typer.echo(
                f"错误: 生成结果格式错误，期望 (cards, stats) 元组: {e}",
                err=True,
            )
            raise typer.Exit(1)

        # 显示提示词（如果指定）
        if show_prompt and stats and stats.prompts:
            typer.echo("\n" + "=" * 60)
            typer.echo("生成的提示词:")
            typer.echo("=" * 60)
            for i, prompt in enumerate(stats.prompts, 1):
                if len(stats.prompts) > 1:
                    typer.echo(f"\n【提示词 {i}/{len(stats.prompts)}】")
                typer.echo(prompt)
                typer.echo("\n" + "-" * 60)

        # 即使没有卡片，也保存 API 响应以便调试
        if not cards:
            typer.echo("警告: 未能生成任何卡片", err=True)
            if stats and stats.api_responses:
                typer.echo("已保存 API 响应到输出目录，请检查以分析问题", err=True)
                # 尝试导出 API 响应
                try:
                    api_output_file = output_dir / "api_response_debug.json"
                    export_api_responses(
                        api_responses=stats.api_responses,
                        output_path=api_output_file,
                        add_type_count_suffix=False,
                    )
                    typer.echo(f"调试信息已保存到: {api_output_file}", err=True)
                except Exception as e:
                    logger.error(f"保存调试信息失败: {e}")
            typer.echo("请检查日志和 API 响应文件以分析问题", err=True)
            raise typer.Exit(1)

        # 导出卡片
        if all_formats:
            export_all_formats(
                cards=cards,
                output=output,
                input_path=input,
                app_config=app_config,
                stats=stats,
            )
        else:
            export_single_format(
                cards=cards,
                output=output,
                app_config=app_config,
                stats=stats,
            )

    except KeyboardInterrupt:
        logger.warning("用户中断操作")
        typer.echo("\n操作已取消", err=True)
        raise typer.Exit(130)
    except typer.Exit:
        # 重新抛出 typer.Exit，不要捕获
        raise
    except (CardGenerationError, ConfigurationError, ParsingError, ExportError) as e:
        logger.exception(f"{type(e).__name__}: {e}")
        typer.echo(f"错误: {e}", err=True)
        typer.echo("请查看日志文件以获取详细错误信息", err=True)
        if log_file_path:
            typer.echo(f"日志文件位置: {log_file_path}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("生成卡片失败")
        import traceback

        error_details = traceback.format_exc()
        logger.error(f"详细错误信息:\n{error_details}")
        typer.echo(f"错误: {e}", err=True)
        typer.echo("请查看日志文件以获取详细错误信息", err=True)
        if log_file_path:
            typer.echo(f"日志文件位置: {log_file_path}", err=True)
        raise typer.Exit(1)


@app.command()
def config(
    init: bool = typer.Option(
        False,
        "--init",
        help="初始化配置文件",
    ),
    show: bool = typer.Option(
        False,
        "--show",
        help="显示当前配置",
    ),
    config_path: Path = typer.Option(
        Path("config.yaml"),
        "--path",
        help="配置文件路径",
    ),
):
    """
    配置管理命令

    初始化或显示配置文件。
    """
    if init:
        # 初始化配置文件
        default_config = AppConfig()
        save_config(default_config, config_path)
        typer.echo(f"✓ 配置文件已创建: {config_path}")
        typer.echo("\n请编辑配置文件并设置API密钥。")

    elif show:
        # 显示当前配置
        try:
            app_config = load_config(config_path=config_path if config_path.exists() else None)
            typer.echo("\n=== 当前配置 ===")
            typer.echo("\nLLM配置:")
            typer.echo(f"  提供商: {app_config.llm.provider}")
            typer.echo(f"  模型: {app_config.llm.model_name}")
            typer.echo(f"  API密钥: {'已设置' if app_config.llm.get_api_key() else '未设置'}")
            typer.echo(f"  基础URL: {app_config.llm.base_url or '默认'}")
            typer.echo(f"  温度: {app_config.llm.temperature}")
            typer.echo(f"  最大Token: {app_config.llm.max_tokens}")

            typer.echo("\n生成配置:")
            typer.echo(f"  卡片类型: {app_config.generation.card_type}")
            typer.echo(f"  卡片数量: {app_config.generation.card_count or '自动'}")
            typer.echo(f"  难度: {app_config.generation.difficulty}")

            typer.echo("\n导出配置:")
            typer.echo(f"  格式: {app_config.export.format}")
            typer.echo(f"  牌组名称: {app_config.export.deck_name}")

        except Exception as e:
            typer.echo(f"错误: {e}", err=True)
            raise typer.Exit(1)

    else:
        typer.echo("请使用 --init 或 --show 选项")
        raise typer.Exit(1)


@app.command()
def inter():
    """
    交互式命令模式

    进入交互式界面，引导用户选择命令并输入参数。
    """
    from ankigen.cli.interactive import interactive_mode

    interactive_mode()


@app.command()
def convert(
    input: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="输入文件路径",
        exists=True,
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="输出文件路径",
    ),
    card_type: Optional[str] = typer.Option(
        None,
        "--card-type",
        "-t",
        help="卡片类型 (basic/cloze/mcq)，如果不指定则自动判定",
    ),
    template: Optional[str] = typer.Option(
        None,
        "--template",
        help="模板名称（可选，用于自动判定卡片类型）",
    ),
    deck_name: Optional[str] = typer.Option(
        None,
        "--deck-name",
        help="牌组名称（仅用于apkg格式）",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="显示详细日志",
    ),
):
    """
    转换卡片组格式

    支持在不同格式之间转换卡片组：
    - yml <-> txt <-> with_type.txt <-> csv <-> apkg

    文件格式通过文件扩展名自动检测。
    """
    # 设置日志
    setup_logger(level="DEBUG" if verbose else "INFO", verbose=verbose)

    try:
        # 检测输入格式
        input_format = detect_format(input)
        if not input_format:
            typer.echo(f"错误: 无法识别输入文件格式: {input}", err=True)
            typer.echo(
                "支持的格式: .yml, .yaml, .txt, .with_type.txt, .csv, .apkg",
                err=True,
            )
            raise typer.Exit(1)

        # 检测输出格式
        output_format = detect_format(output)
        if not output_format:
            typer.echo(f"错误: 无法识别输出文件格式: {output}", err=True)
            typer.echo(
                "支持的格式: .yml, .yaml, .txt, .with_type.txt, .csv, .apkg",
                err=True,
            )
            raise typer.Exit(1)

        typer.echo(f"输入格式: {input_format}")
        typer.echo(f"输出格式: {output_format}")

        # 确定卡片类型
        card_type_enum = None
        if card_type:
            try:
                card_type_enum = CardType(card_type.lower())
            except ValueError:
                typer.echo(f"警告: 无效的卡片类型 '{card_type}'，将自动判定", err=True)

        # 读取卡片
        typer.echo(f"\n正在读取 {input}...")
        cards = read_cards(input, card_type=card_type_enum)

        if not cards:
            typer.echo("错误: 未能读取到任何卡片", err=True)
            raise typer.Exit(1)

        typer.echo(f"成功读取 {len(cards)} 张卡片")

        # 显示卡片类型信息
        card_types = {}
        for card in cards:
            ct = card.card_type.value
            card_types[ct] = card_types.get(ct, 0) + 1

        typer.echo("卡片类型统计:")
        for ct, count in card_types.items():
            typer.echo(f"  {ct}: {count} 张")

        # 导出卡片
        typer.echo(f"\n正在导出到 {output}...")

        # 确定牌组名称
        deck_name_final = deck_name
        if not deck_name_final and output_format == "apkg":
            # 使用输入文件名作为默认牌组名称
            deck_name_final = input.stem

        export_cards(
            cards=cards,
            output_path=output,
            format=output_format,
            deck_name=deck_name_final,
            deck_description="",
        )

        typer.echo(f"\n✓ 成功转换 {len(cards)} 张卡片")
        typer.echo(f"  输入: {input} ({input_format})")
        typer.echo(f"  输出: {output} ({output_format})")

    except NotImplementedError as e:
        typer.echo(f"错误: {e}", err=True)
        typer.echo("提示: APKG格式读取尚未实现，请先转换为其他格式", err=True)
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("转换失败")
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(1)


def main():
    """主入口函数"""
    app()


if __name__ == "__main__":
    main()
