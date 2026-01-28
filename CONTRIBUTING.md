# 贡献指南

感谢您对AnkiGen项目的关注！本文档将帮助您了解如何参与项目开发。

## 开发环境设置

1. **克隆仓库**
   ```bash
   git clone <repository_url>
   cd ai-anki-cards
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -e ".[dev]"  # 安装所有依赖和开发工具
   # 或分别安装
   pip install -e .           # 基础依赖
   pip install -e ".[lint]"   # 代码质量工具
   pip install -e ".[security]" # 安全扫描工具
   ```

4. **设置 Pre-commit Hooks（推荐）**
   ```bash
   pre-commit install
   ```

## 代码规范

### 代码质量工具

项目使用以下工具确保代码质量：

- **Ruff**: 代码检查和格式化（替代 flake8 + isort + black）
- **MyPy**: 静态类型检查
- **Pydocstyle**: 文档字符串检查
- **Bandit**: 安全漏洞扫描
- **Safety**: 依赖漏洞扫描

详细使用方法请参考 [DEVELOPMENT.md](DEVELOPMENT.md)。

### 代码风格

- 使用**Ruff**进行代码格式化和检查（行长度100）
- 遵循PEP 8规范
- 使用 Google 风格的文档字符串

### 类型提示

- 所有公共函数和类方法都应包含类型提示
- 使用`typing`模块的类型注解

### 文档字符串

- 所有公共函数、类和方法都应包含docstring
- 使用Google风格的docstring

示例：
```python
def function_name(param1: str, param2: int) -> bool:
    """
    函数简短描述

    Args:
        param1: 参数1的描述
        param2: 参数2的描述

    Returns:
        返回值的描述

    Raises:
        ValueError: 何时抛出此异常
    """
    pass
```

## 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_parser.py

# 运行并显示覆盖率
pytest --cov=ankigen tests/
```

### 编写测试

- 测试文件应放在`tests/`目录下
- 测试函数名以`test_`开头
- 使用pytest fixtures管理测试数据
- Mock外部依赖（如API调用）

示例：
```python
def test_function_name():
    """测试函数描述"""
    # Arrange
    input_data = "test"

    # Act
    result = function_to_test(input_data)

    # Assert
    assert result == expected_value
```

## 提交代码

### 提交信息规范

使用清晰的提交信息，格式如下：

```
类型: 简短描述

详细描述（可选）
```

类型包括：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `test`: 测试相关
- `refactor`: 代码重构
- `style`: 代码格式调整
- `chore`: 构建/工具相关

示例：
```
feat: 添加Ollama提供商支持

- 实现OllamaProvider类
- 添加Ollama API集成
- 更新文档和测试
```

### Pull Request流程

1. Fork仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "feat: 添加新功能"`
4. 推送到分支：`git push origin feature/your-feature`
5. 创建Pull Request

### PR检查清单

- [ ] 代码通过所有测试
- [ ] 添加了新功能的测试
- [ ] 更新了相关文档
- [ ] 代码符合风格规范
- [ ] 提交信息清晰明确

## 项目结构说明

- `ankigen/core/`: 核心功能模块
- `ankigen/models/`: 数据模型
- `ankigen/utils/`: 工具函数
- `ankigen/templates/`: 提示词模板
- `tests/`: 测试文件
- `config/`: 配置文件

## 添加新功能

### 添加新的LLM提供商

1. 在`ankigen/core/llm_engine.py`中创建新的Provider类
2. 继承`BaseLLMProvider`并实现抽象方法
3. 在`LLMEngine._create_provider()`中注册
4. 添加测试用例

### 添加新的卡片类型

1. 在`ankigen/models/card.py`中定义新的Card类
2. 创建对应的提示词模板（`templates/`）
3. 在`CardGenerator`中添加解析逻辑
4. 在`Exporter`中添加导出支持
5. 添加测试用例

### 添加新的导出格式

1. 在`ankigen/core/exporter.py`中创建新的Exporter类
2. 继承`BaseExporter`并实现`export`方法
3. 在`export_cards`函数中注册
4. 添加测试用例

## 问题报告

如果发现bug或有功能建议，请创建Issue，包含：

- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（Python版本、操作系统等）

## 联系方式

如有问题，请通过Issue或Pull Request联系。

感谢您的贡献！
