#!/usr/bin/env python3
"""
交互式CLI演示脚本

演示如何使用交互式CLI功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ankigen.cli.interactive import interactive_mode  # noqa: E402


def main():
    """主函数"""
    print("=" * 60)  # noqa: T201
    print("AnkiGen 交互式CLI演示")  # noqa: T201
    print("=" * 60)  # noqa: T201
    print()  # noqa: T201
    print("此脚本演示交互式命令选择功能。")  # noqa: T201
    print("您将能够：")  # noqa: T201
    print("  1. 选择要执行的命令（generate/config/convert）")  # noqa: T201
    print("  2. 通过交互式界面输入参数")  # noqa: T201
    print("  3. 查看参数摘要并确认执行")  # noqa: T201
    print()  # noqa: T201
    print("提示：")  # noqa: T201
    print("  - 使用方向键选择选项")  # noqa: T201
    print("  - 按 Enter 确认选择")  # noqa: T201
    print("  - 按 Ctrl+C 取消操作")  # noqa: T201
    print()  # noqa: T201
    print("=" * 60)  # noqa: T201
    print()  # noqa: T201

    try:
        interactive_mode()
    except KeyboardInterrupt:
        print("\n演示已取消")  # noqa: T201
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
