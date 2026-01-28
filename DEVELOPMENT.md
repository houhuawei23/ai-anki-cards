# 开发指南

本文档介绍如何使用项目中的代码质量工具和安全扫描工具。

## 目录

- [安装开发依赖](#安装开发依赖)
- [代码质量工具](#代码质量工具)
  - [Ruff - 代码检查和格式化](#ruff---代码检查和格式化)
  - [MyPy - 类型检查](#mypy---类型检查)
  - [Pydocstyle - 文档字符串检查](#pydocstyle---文档字符串检查)
- [安全扫描工具](#安全扫描工具)
  - [Bandit - 安全漏洞扫描](#bandit---安全漏洞扫描)
  - [Safety - 依赖漏洞扫描](#safety---依赖漏洞扫描)
- [Pre-commit Hooks](#pre-commit-hooks)
- [测试工具](#测试工具)
- [CI/CD 集成](#cicd-集成)

## 安装开发依赖

### 方式一：使用 pip 安装（推荐）

```bash
# 安装所有开发依赖
pip install -e ".[dev]"

# 或分别安装
pip install -e ".[lint]"      # 代码质量工具
pip install -e ".[security]"  # 安全扫描工具
```

### 方式二：使用虚拟环境

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -e ".[dev]"
```

## 代码质量工具

### Ruff - 代码检查和格式化

Ruff 是一个快速的 Python linter 和代码格式化工具，替代了 flake8、isort 和 black。

#### 检查代码问题

```bash
# 检查所有 Python 文件
ruff check ankigen/

# 检查特定文件
ruff check ankigen/cli.py

# 自动修复可修复的问题
ruff check --fix ankigen/

# 检查并显示所有规则
ruff check --show-source ankigen/
```

#### 格式化代码

```bash
# 格式化所有文件
ruff format ankigen/

# 检查格式（不修改文件）
ruff format --check ankigen/

# 格式化特定文件
ruff format ankigen/cli.py
```

#### 常用命令组合

```bash
# 检查并修复 + 格式化（推荐在提交前运行）
ruff check --fix ankigen/ && ruff format ankigen/

# 只检查不修复
ruff check ankigen/
```

#### 配置说明

Ruff 的配置在 `pyproject.toml` 的 `[tool.ruff]` 部分：

```toml
[tool.ruff]
line-length = 100
target-version = "py38"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "ARG", "PIE", "T20", "PT", "Q", "RUF"]
ignore = ["E501", "B008", "ARG001", "ARG002"]
```

### MyPy - 类型检查

MyPy 用于静态类型检查，确保类型注解的正确性。

#### 基本使用

```bash
# 检查所有文件
mypy ankigen/

# 检查特定文件
mypy ankigen/cli.py

# 显示详细的错误信息
mypy --show-error-codes ankigen/

# 忽略缺失导入（用于第三方库）
mypy --ignore-missing-imports ankigen/
```

#### 常用选项

```bash
# 严格模式（更严格的类型检查）
mypy --strict ankigen/

# 显示未使用的忽略
mypy --warn-unused-ignores ankigen/

# 生成 HTML 报告
mypy --html-report html-report ankigen/
```

#### 配置说明

MyPy 的配置在 `pyproject.toml` 的 `[tool.mypy]` 部分。当前配置允许渐进式类型检查，不会因为缺少类型注解而报错。

### Pydocstyle - 文档字符串检查

Pydocstyle 检查文档字符串是否符合规范（Google 风格）。

#### 基本使用

```bash
# 检查所有文件
pydocstyle ankigen/

# 检查特定文件
pydocstyle ankigen/cli.py

# 显示源代码
pydocstyle --source ankigen/

# 只检查公共接口（推荐）
pydocstyle --convention=google ankigen/
```

#### 常用选项

```bash
# 检查所有文件（包括私有方法）
pydocstyle --match='.*' ankigen/

# 忽略特定错误代码
pydocstyle --ignore=D100,D104 ankigen/

# 显示统计信息
pydocstyle --count ankigen/
```

## 安全扫描工具

### Bandit - 安全漏洞扫描

Bandit 扫描 Python 代码中的安全漏洞。

#### 基本使用

```bash
# 扫描所有代码
bandit -r ankigen/

# 扫描特定文件
bandit ankigen/cli.py

# 生成 JSON 报告
bandit -r ankigen/ -f json -o bandit-report.json

# 生成 HTML 报告
bandit -r ankigen/ -f html -o bandit-report.html

# 只显示高/中危漏洞
bandit -r ankigen/ -ll  # 低危及以上
bandit -r ankigen/ -li  # 中危及以上
bandit -r ankigen/ -lll # 高危及以上
```

#### 常用选项

```bash
# 排除测试目录
bandit -r ankigen/ --exclude tests/

# 跳过特定测试
bandit -r ankigen/ --skip B101,B601

# 显示详细信息
bandit -r ankigen/ -v

# 配置文件扫描（使用 pyproject.toml 中的配置）
bandit -r ankigen/ -c pyproject.toml
```

#### 配置说明

Bandit 的配置在 `pyproject.toml` 的 `[tool.bandit]` 部分：

```toml
[tool.bandit]
exclude_dirs = ["tests", "venv", ".venv", "build", "dist"]
skips = ["B101"]  # 允许在测试中使用 assert
```

### Safety - 依赖漏洞扫描

Safety 检查已安装的 Python 包是否存在已知的安全漏洞。

#### 基本使用

```bash
# 检查当前环境的依赖
safety check

# 检查 requirements 文件
safety check --file requirements.txt

# 检查并显示详细信息
safety check --full-report

# 只显示高危漏洞
safety check --json
```

#### 常用选项

```bash
# 检查并自动更新数据库
safety check --update

# 忽略特定漏洞（使用 CVE ID）
safety check --ignore 12345

# 生成报告文件
safety check --output safety-report.json
```

#### 注意事项

Safety 需要访问在线数据库，首次运行可能需要下载漏洞数据库。

## Pre-commit Hooks

Pre-commit hooks 在每次 git commit 前自动运行代码质量检查。

### 安装 Pre-commit

```bash
# 安装 pre-commit
pip install pre-commit

# 或使用项目依赖
pip install -e ".[dev]"
```

### 设置 Hooks

```bash
# 安装 git hooks
pre-commit install

# 安装 commit-msg hook（可选）
pre-commit install --hook-type commit-msg
```

### 手动运行

```bash
# 检查所有文件
pre-commit run --all-files

# 运行特定 hook
pre-commit run ruff --all-files
pre-commit run mypy --all-files
pre-commit run bandit --all-files

# 跳过 hooks（不推荐）
git commit --no-verify
```

### 更新 Hooks

```bash
# 更新所有 hooks 到最新版本
pre-commit autoupdate
```

### 配置说明

Pre-commit 配置在 `.pre-commit-config.yaml` 文件中，包含以下 hooks：

- **pre-commit-hooks**: 基础检查（尾随空格、文件大小等）
- **ruff**: 代码检查和格式化
- **mypy**: 类型检查
- **bandit**: 安全扫描
- **pytest**: 运行测试（本地 hook）

## 测试工具

### Pytest - 测试框架

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_cli.py

# 运行并显示覆盖率
pytest --cov=ankigen --cov-report=html

# 运行并显示详细输出
pytest -v

# 运行并显示打印输出
pytest -s

# 并行运行测试（需要 pytest-xdist）
pytest -n auto
```

### 测试覆盖率

```bash
# 生成 HTML 覆盖率报告
pytest --cov=ankigen --cov-report=html

# 生成终端报告
pytest --cov=ankigen --cov-report=term-missing

# 生成 XML 报告（用于 CI）
pytest --cov=ankigen --cov-report=xml

# 设置覆盖率阈值
pytest --cov=ankigen --cov-fail-under=80
```

覆盖率报告会生成在：
- HTML: `htmlcov/index.html`
- XML: `coverage.xml`
- 终端: 直接显示

## CI/CD 集成

### GitHub Actions 示例

创建 `.github/workflows/ci.yml`：

```yaml
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - run: pip install -e ".[dev]"
      - run: ruff check ankigen/
      - run: ruff format --check ankigen/
      - run: mypy ankigen/
      - run: pydocstyle ankigen/

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - run: pip install -e ".[security]"
      - run: bandit -r ankigen/
      - run: safety check

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - run: pip install -e ".[dev]"
      - run: pytest --cov=ankigen --cov-report=xml
```

## 快速开始工作流

### 日常开发流程

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 安装 pre-commit hooks
pre-commit install

# 3. 开发代码...

# 4. 提交前检查（pre-commit 会自动运行，或手动运行）
pre-commit run --all-files

# 5. 运行测试
pytest

# 6. 提交代码
git commit -m "feat: 添加新功能"
```

### 代码审查前检查清单

```bash
# 运行所有检查
ruff check --fix ankigen/ && \
ruff format ankigen/ && \
mypy ankigen/ && \
pydocstyle ankigen/ && \
bandit -r ankigen/ && \
pytest --cov=ankigen
```

## 常见问题

### Q: Ruff 和 Black/Isort 冲突吗？

A: 不需要。Ruff 已经包含了格式化功能，可以完全替代 Black 和 Isort。如果项目中还有 Black/Isort 配置，可以移除。

### Q: MyPy 报错但代码能运行？

A: MyPy 是静态类型检查器，它检查类型注解的正确性。如果代码能运行但 MyPy 报错，说明类型注解可能不准确。可以：
1. 修复类型注解
2. 使用 `# type: ignore` 注释（不推荐）
3. 调整 MyPy 配置使其更宽松

### Q: Bandit 误报怎么办？

A: 如果 Bandit 报告了误报，可以：
1. 在代码中添加 `# nosec` 注释
2. 在 `pyproject.toml` 的 `skips` 中添加测试 ID
3. 使用 `--skip` 选项跳过特定测试

### Q: Pre-commit 运行太慢？

A: 可以：
1. 只运行必要的 hooks
2. 使用 `--hook-stage manual` 手动运行
3. 配置 hooks 只检查修改的文件（默认行为）

## 更多资源

- [Ruff 文档](https://docs.astral.sh/ruff/)
- [MyPy 文档](https://mypy.readthedocs.io/)
- [Bandit 文档](https://bandit.readthedocs.io/)
- [Pre-commit 文档](https://pre-commit.com/)
- [Pytest 文档](https://docs.pytest.org/)
