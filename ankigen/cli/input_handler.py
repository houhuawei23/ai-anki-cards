"""
输入处理模块

负责解析和验证输入文件或目录。
"""

from pathlib import Path

import typer
from loguru import logger

from ankigen.core.parser import BatchProcessor, parse_file
from ankigen.exceptions import ParsingError


def parse_input(input_path: Path) -> str:
    """
    解析输入文件或目录

    Args:
        input_path: 输入文件或目录路径

    Returns:
        解析后的内容字符串

    Raises:
        typer.Exit: 如果解析失败
    """
    try:
        if input_path.is_file():
            content = parse_file(input_path)
        elif input_path.is_dir():
            processor = BatchProcessor(recursive=True)
            content = processor.parse_directory(input_path, merge=True)
            if isinstance(content, list):
                content = "\n\n---\n\n".join(content)
        else:
            typer.echo(f"错误: 无效的输入路径: {input_path}", err=True)
            raise typer.Exit(1)
    except FileNotFoundError as e:
        logger.exception(f"文件不存在: {e}")
        typer.echo(f"错误: 文件不存在: {e}", err=True)
        raise typer.Exit(1)
    except PermissionError as e:
        logger.exception(f"文件权限错误: {e}")
        typer.echo(f"错误: 文件权限错误: {e}", err=True)
        raise typer.Exit(1)
    except ParsingError as e:
        logger.exception(f"解析错误: {e}")
        typer.echo(f"错误: 解析错误: {e}", err=True)
        typer.echo("请检查文件格式和编码是否正确", err=True)
        raise typer.Exit(1)
    except Exception as e:
        logger.exception(f"解析输入文件失败: {e}")
        typer.echo(f"错误: 解析输入文件失败: {e}", err=True)
        typer.echo("请检查文件格式和编码是否正确", err=True)
        raise typer.Exit(1)

    return content


def validate_input(content: str) -> None:
    """
    验证输入内容

    Args:
        content: 输入内容

    Raises:
        typer.Exit: 如果内容无效
    """
    if not content or len(content.strip()) == 0:
        logger.warning("输入文件为空")
        typer.echo("错误: 输入文件为空", err=True)
        raise typer.Exit(1)
