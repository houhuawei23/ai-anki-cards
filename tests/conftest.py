"""
Pytest 配置和共享 fixtures

提供测试中使用的共享 fixtures 和配置。
"""

import os
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture()
def test_data_dir() -> Path:
    """返回测试数据目录路径"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_txt_file(test_data_dir: Path) -> Path:
    """返回示例文本文件路径"""
    return test_data_dir / "sample.txt"


@pytest.fixture()
def sample_md_file(test_data_dir: Path) -> Path:
    """返回示例 Markdown 文件路径"""
    return test_data_dir / "sample.md"


@pytest.fixture()
def tmp_output_dir(tmp_path: Path) -> Path:
    """返回临时输出目录"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture(autouse=True)
def _reset_env() -> Generator[None, None, None]:
    """在每个测试前后重置环境变量"""
    # 保存原始环境变量
    original_env = os.environ.copy()

    yield

    # 恢复原始环境变量
    os.environ.clear()
    os.environ.update(original_env)
