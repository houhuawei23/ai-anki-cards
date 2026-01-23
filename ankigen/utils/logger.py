"""
日志配置模块

使用loguru配置日志系统，支持彩色输出和文件日志。
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
    verbose: bool = False,
    auto_log_file: bool = True,
) -> Optional[Path]:
    """
    配置loguru日志系统

    Args:
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: 日志文件路径，如果为None且auto_log_file=True则自动创建
        rotation: 日志文件轮转大小
        retention: 日志文件保留时间
        verbose: 是否显示详细日志（DEBUG级别）
        auto_log_file: 如果log_file为None，是否自动创建日志文件

    Returns:
        实际使用的日志文件路径，如果没有创建日志文件则返回None
    """
    # 移除默认处理器
    logger.remove()

    # 控制台输出格式
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 文件输出格式（更详细）
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    # 设置控制台输出
    log_level = "DEBUG" if verbose else level
    logger.add(
        sys.stderr,
        format=console_format,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # 设置文件输出
    actual_log_file = log_file
    if actual_log_file is None and auto_log_file:
        # 自动创建日志文件：在项目根目录的 logs 目录下
        project_root = Path(__file__).parent.parent.parent
        logs_dir = project_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用时间戳创建日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        actual_log_file = logs_dir / f"ankigen_{timestamp}.log"
    
    if actual_log_file:
        actual_log_file = Path(actual_log_file)
        try:
            actual_log_file.parent.mkdir(parents=True, exist_ok=True)
            logger.add(
                actual_log_file,
                format=file_format,
                level=level,
                rotation=rotation,
                retention=retention,
                compression="zip",
                backtrace=True,
                diagnose=True,
            )
            logger.info(f"日志文件已创建: {actual_log_file}")
            return actual_log_file
        except Exception as e:
            logger.warning(f"无法创建日志文件 {actual_log_file}: {e}")
            return None
    
    return None


def get_logger(name: Optional[str] = None):
    """
    获取logger实例

    Args:
        name: logger名称，如果为None则返回根logger

    Returns:
        logger实例
    """
    if name:
        return logger.bind(name=name)
    return logger
