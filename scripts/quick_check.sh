#!/bin/bash
# 快速代码质量检查（仅运行关键检查）

set -e

echo "快速代码质量检查..."
echo ""

# Ruff 检查和格式化
echo "1. Ruff 检查..."
ruff check --fix ankigen/ && echo "✓ Ruff 检查完成"

echo "2. Ruff 格式化..."
ruff format ankigen/ && echo "✓ 代码格式化完成"

echo "3. 运行测试..."
pytest --cov=ankigen --cov-report=term-missing -q && echo "✓ 测试通过"

echo ""
echo "✓ 快速检查完成！"
