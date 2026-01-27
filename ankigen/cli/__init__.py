"""
CLI模块

包含命令行接口的各种处理模块。
"""

import importlib.util
from pathlib import Path

# 由于存在同名文件 ankigen/cli.py，需要使用特殊方式导入
_cli_file_path = Path(__file__).parent.parent / "cli.py"
if _cli_file_path.exists():
    spec = importlib.util.spec_from_file_location("ankigen.cli.cli", _cli_file_path)
    _cli_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_cli_module)
    app = _cli_module.app
    generate = _cli_module.generate
    config = _cli_module.config
    convert = _cli_module.convert
    __all__ = ["app", "generate", "config", "convert"]
else:
    __all__ = []
