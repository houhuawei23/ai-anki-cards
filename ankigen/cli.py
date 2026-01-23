"""
CLI接口模块

使用Typer实现命令行界面。
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from ankigen.core.card_generator import CardGenerator
from ankigen.core.card_reader import detect_format, read_cards
from ankigen.core.config_loader import load_config, save_config
from ankigen.core.exporter import _add_type_count_suffix, export_api_responses, export_cards, export_parsed_cards_json
from ankigen.core.parser import BatchProcessor, parse_file
from ankigen.core.template_loader import get_template_dir, get_template_meta
from ankigen.models.card import CardType
from ankigen.models.config import AppConfig, LLMProvider
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
):
    """
    生成Anki卡片

    从输入文件或目录生成Anki卡片并导出为指定格式。
    """
    # 设置日志（自动创建日志文件）
    log_file_path = setup_logger(level="DEBUG" if verbose else "INFO", verbose=verbose, auto_log_file=True)
    if log_file_path:
        typer.echo(f"日志文件: {log_file_path}", err=True)

    try:
        # 加载配置
        try:
            app_config = load_config(config_path=config)
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
        except Exception as e:
            logger.exception(f"配置参数处理失败: {e}")
            typer.echo(f"错误: 配置参数处理失败: {e}", err=True)
            raise typer.Exit(1)

        # 验证配置
        if not app_config.llm.get_api_key():
            typer.echo(
                "错误: 未设置API密钥。请设置环境变量或使用配置文件。",
                err=True,
            )
            raise typer.Exit(1)

        # 解析输入文件
        typer.echo(f"正在解析输入: {input}")
        try:
            if input.is_file():
                content = parse_file(input)
            elif input.is_dir():
                processor = BatchProcessor(recursive=True)
                content = processor.parse_directory(input, merge=True)
                if isinstance(content, list):
                    content = "\n\n---\n\n".join(content)
            else:
                typer.echo(f"错误: 无效的输入路径: {input}", err=True)
                raise typer.Exit(1)
        except FileNotFoundError as e:
            logger.exception(f"文件不存在: {e}")
            typer.echo(f"错误: 文件不存在: {e}", err=True)
            raise typer.Exit(1)
        except PermissionError as e:
            logger.exception(f"文件权限错误: {e}")
            typer.echo(f"错误: 文件权限错误: {e}", err=True)
            raise typer.Exit(1)
        except Exception as e:
            logger.exception(f"解析输入文件失败: {e}")
            typer.echo(f"错误: 解析输入文件失败: {e}", err=True)
            typer.echo("请检查文件格式和编码是否正确", err=True)
            raise typer.Exit(1)

        if not content or len(content.strip()) == 0:
            logger.warning("输入文件为空")
            typer.echo("错误: 输入文件为空", err=True)
            raise typer.Exit(1)

        typer.echo(f"已解析内容，长度: {len(content)} 字符")

        # 预览模式
        if dry_run:
            typer.echo("\n" + "=" * 60)
            typer.echo("=== 预览模式（DRY RUN）===")
            typer.echo("=" * 60)
            
            # 输入信息
            typer.echo("\n【输入信息】")
            typer.echo(f"  输入路径: {input}")
            typer.echo(f"  输入类型: {'文件' if input.is_file() else '目录'}")
            if input.is_file():
                file_size = input.stat().st_size
                typer.echo(f"  文件大小: {file_size:,} 字节 ({file_size / 1024:.2f} KB)")
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
            generator = CardGenerator.__new__(CardGenerator)
            card_type_enum = CardType(app_config.generation.card_type)
            
            if app_config.generation.card_count:
                estimated_count = app_config.generation.card_count
                typer.echo(f"  卡片数量: {estimated_count} (用户指定)")
                card_count = estimated_count
            else:
                total_estimated = generator._estimate_total_card_count(content)
                single_estimated = generator._estimate_card_count(content)
                max_cards_per_request = app_config.generation.max_cards_per_request
                max_concurrent = app_config.generation.max_concurrent_requests
                typer.echo(f"  卡片数量: {total_estimated} (自动估算)")
                typer.echo(f"  单次限制: {single_estimated} 张 (最多{max_cards_per_request}张)")
                card_count = total_estimated
                if total_estimated > max_cards_per_request:
                    num_chunks = (total_estimated + max_cards_per_request - 1) // max_cards_per_request
                    typer.echo(f"  预计切分: {num_chunks} 个内容块")
                    typer.echo(f"  预计API调用: {num_chunks} 次 (并发执行，最大{max_concurrent}个并发)")
                else:
                    typer.echo("  预计API调用: 1 次")
            
            typer.echo(f"  难度级别: {app_config.generation.difficulty}")
            typer.echo(f"  启用去重: {'是' if app_config.generation.enable_deduplication else '否'}")
            typer.echo(f"  启用质量过滤: {'是' if app_config.generation.enable_quality_filter else '否'}")
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
            typer.echo(f"  API密钥: {'已设置' if app_config.llm.get_api_key() else '未设置'}")
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
            # 创建临时卡片列表用于计算文件名
            temp_cards = []
            if card_type_enum == CardType.BASIC:
                from ankigen.models.card import BasicCard
                temp_cards = [BasicCard(front="temp", back="temp")] * min(card_count, 1)
            elif card_type_enum == CardType.CLOZE:
                from ankigen.models.card import ClozeCard
                temp_cards = [ClozeCard(front="temp{{c1::test}}", back="temp")] * min(card_count, 1)
            elif card_type_enum == CardType.MCQ:
                from ankigen.models.card import MCQCard, MCQOption
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
                final_output_path = _add_type_count_suffix(output, temp_cards)
                # 更新卡片数量
                final_stem = final_output_path.stem
                final_suffix = final_output_path.suffix
                # 替换数量部分
                parts = final_stem.rsplit(".", 2)
                if len(parts) == 3 and parts[-1].isdigit():
                    final_stem = f"{parts[0]}.{parts[1]}.{card_count}"
                final_output_path = final_output_path.parent / f"{final_stem}{final_suffix}"
            else:
                final_output_path = output
            
            typer.echo(f"  输出路径: {output}")
            typer.echo(f"  最终文件名: {final_output_path.name}")
            typer.echo(f"  牌组名称: {app_config.export.deck_name}")
            if app_config.export.deck_description:
                typer.echo(f"  牌组描述: {app_config.export.deck_description[:50]}...")
            
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
            return

        # 创建缓存
        cache = FileCache()

        # 创建卡片生成器
        card_generator = CardGenerator(
            llm_config=app_config.llm,
            cache=cache,
        )

        # 确定输出目录（用于立即保存 API 响应）
        # 提前确定输出目录，以便在生成卡片时立即保存 API 响应
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

        # 生成卡片（加强错误处理）
        typer.echo("\n正在生成卡片...")
        try:
            result = asyncio.run(
                card_generator.generate_cards(content, app_config.generation, output_dir)
            )
        except Exception as e:
            logger.error(f"生成卡片时发生错误: {e}")
            import traceback
            logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            typer.echo(f"错误: 生成卡片失败: {e}", err=True)
            typer.echo("请检查日志以获取更多信息", err=True)
            raise typer.Exit(1)
        
        # 处理返回结果（可能是 tuple 或 list）
        try:
            if isinstance(result, tuple) and len(result) == 2:
                cards, stats = result
            else:
                # 兼容旧版本（直接返回 cards）
                cards = result
                stats = None
        except Exception as e:
            logger.error(f"处理生成结果时发生错误: {e}")
            import traceback
            logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            typer.echo(f"错误: 处理生成结果失败: {e}", err=True)
            raise typer.Exit(1)

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
            # 导出所有格式
            # 确定输出目录和文件名基础
            if output.is_dir():
                # 如果输出路径是已存在的目录
                output_dir = Path(output)
                # 使用输入文件名作为基础名，如果没有输入文件则使用默认名
                if input.is_file():
                    output_stem = input.stem
                else:
                    output_stem = "items"
            elif not output.suffix:
                # 如果输出路径没有扩展名（可能是目录名）
                output_dir = Path(output)
                output_dir.mkdir(parents=True, exist_ok=True)
                # 使用输入文件名作为基础名，如果没有输入文件则使用默认名
                if input.is_file():
                    output_stem = input.stem
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
                api_output_file = output_dir / f"{output_stem}.api_response.json"
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

            typer.echo(f"\n✓ 成功导出 {len(exported_files)} 种格式到 {output_dir}")
        else:
            # 单一格式导出
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
                api_output_file = output.parent / f"{output.stem}.api_response.json"
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

    except KeyboardInterrupt:
        logger.warning("用户中断操作")
        typer.echo("\n操作已取消", err=True)
        raise typer.Exit(130)
    except typer.Exit:
        # 重新抛出 typer.Exit，不要捕获
        raise
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
            typer.echo("支持的格式: .yml, .yaml, .txt, .with_type.txt, .csv, .apkg", err=True)
            raise typer.Exit(1)

        # 检测输出格式
        output_format = detect_format(output)
        if not output_format:
            typer.echo(f"错误: 无法识别输出文件格式: {output}", err=True)
            typer.echo("支持的格式: .yml, .yaml, .txt, .with_type.txt, .csv, .apkg", err=True)
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
