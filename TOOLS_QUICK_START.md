# 代码质量工具快速开始指南

## 🚀 快速开始

### 1. 安装工具

```bash
# 安装所有开发工具
pip install -e ".[dev]"

# 或分别安装
pip install -e ".[lint]"      # Ruff, MyPy, Pydocstyle
pip install -e ".[security]"  # Bandit, Safety
```

### 2. 设置 Pre-commit（推荐）

```bash
pre-commit install
```

之后每次 `git commit` 前会自动运行检查。

### 3. 使用便捷脚本

```bash
# 完整检查（所有工具）
./scripts/check_code_quality.sh

# 快速检查（Ruff + 测试）
./scripts/quick_check.sh
```

## 📋 常用命令速查

### Ruff（代码检查和格式化）

```bash
# 检查代码问题
ruff check ankigen/

# 自动修复
ruff check --fix ankigen/

# 格式化代码
ruff format ankigen/

# 检查格式（不修改）
ruff format --check ankigen/
```

### MyPy（类型检查）

```bash
# 类型检查
mypy ankigen/

# 显示错误代码
mypy --show-error-codes ankigen/
```

### Bandit（安全扫描）

```bash
# 安全扫描
bandit -r ankigen/

# 只显示中高危
bandit -r ankigen/ -ll

# 生成 HTML 报告
bandit -r ankigen/ -f html -o report.html
```

### Safety（依赖漏洞扫描）

```bash
# 检查依赖漏洞
safety check

# 更新数据库
safety check --update
```

### Pytest（测试）

```bash
# 运行测试
pytest

# 显示覆盖率
pytest --cov=ankigen --cov-report=html

# 并行运行
pytest -n auto
```

## 🔧 手动运行 Pre-commit

```bash
# 检查所有文件
pre-commit run --all-files

# 运行特定工具
pre-commit run ruff --all-files
pre-commit run mypy --all-files
pre-commit run bandit --all-files
```

## 📚 详细文档

完整的使用说明请参考：
- [DEVELOPMENT.md](DEVELOPMENT.md) - 详细开发指南
- [CONTRIBUTING.md](CONTRIBUTING.md) - 贡献指南

## ⚡ 日常开发工作流

```bash
# 1. 开发代码...

# 2. 提交前检查（自动运行，或手动）
pre-commit run --all-files

# 3. 如果 pre-commit 失败，修复后重新运行
ruff check --fix ankigen/
ruff format ankigen/

# 4. 运行测试
pytest

# 5. 提交
git commit -m "feat: 新功能"
```

## 🐛 常见问题

**Q: Ruff 报错怎么办？**
```bash
# 自动修复大部分问题
ruff check --fix ankigen/
ruff format ankigen/
```

**Q: MyPy 类型错误？**
- 检查类型注解是否正确
- 使用 `# type: ignore` 临时忽略（不推荐）
- 查看 [DEVELOPMENT.md](DEVELOPMENT.md) 中的 MyPy 配置说明

**Q: Bandit 误报？**
- 在代码行添加 `# nosec` 注释
- 或在 `pyproject.toml` 的 `[tool.bandit]` 中配置 `skips`

**Q: Pre-commit 太慢？**
- 默认只检查修改的文件
- 可以跳过：`git commit --no-verify`（不推荐）

## 📊 工具对比

| 工具 | 用途 | 替代 | 速度 |
|------|------|------|------|
| Ruff | 代码检查+格式化 | flake8+isort+black | ⚡⚡⚡ 极快 |
| MyPy | 类型检查 | - | ⚡⚡ 快 |
| Pydocstyle | 文档检查 | - | ⚡⚡ 快 |
| Bandit | 安全扫描 | - | ⚡⚡ 快 |
| Safety | 依赖扫描 | - | ⚡ 中等 |

## 🎯 推荐配置

### VS Code

安装扩展：
- Python
- Ruff（官方扩展）
- Pylance（内置类型检查）

### PyCharm

1. 设置 Ruff 为代码检查工具
2. 启用 MyPy 类型检查
3. 配置 Pre-commit hooks

## 📝 提交前检查清单

- [ ] `ruff check --fix` 通过
- [ ] `ruff format` 通过
- [ ] `mypy` 无严重错误
- [ ] `pytest` 所有测试通过
- [ ] `bandit` 无高危漏洞
- [ ] 代码已格式化
- [ ] 类型注解完整
