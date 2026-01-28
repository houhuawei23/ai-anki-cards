# Python项目开发 Prompt 模板

本文档提供了一套完整的Prompt模板，用于指导AI助手（如Cursor、Claude、GPT等）按照项目规范进行Python项目开发。

## 目录

- [项目初始化Prompt](#项目初始化prompt)
- [功能开发Prompt](#功能开发prompt)
- [代码重构Prompt](#代码重构prompt)
- [测试编写Prompt](#测试编写prompt)
- [代码审查Prompt](#代码审查prompt)
- [文档编写Prompt](#文档编写prompt)
- [问题修复Prompt](#问题修复prompt)

---

## 项目初始化Prompt

### 模板1：创建新Python项目

```
请帮我创建一个新的Python项目，项目名称为：{项目名称}

要求：
1. 项目结构：
   - 使用现代Python项目结构（pyproject.toml）
   - 主包目录：{项目名称}/
   - 测试目录：tests/
   - 脚本目录：scripts/
   - 配置文件：pyproject.toml, README.md, DEVELOPMENT.md

2. 代码质量工具配置：
   - Ruff：代码检查和格式化（替代flake8+isort+black）
   - MyPy：类型检查
   - Pydocstyle：文档字符串检查（Google风格）
   - Bandit：安全扫描
   - Safety：依赖漏洞扫描
   - Pre-commit hooks：自动化检查

3. 依赖管理：
   - 使用pyproject.toml管理依赖
   - 开发依赖分组：dev, lint, security
   - Python版本要求：>=3.8

4. 测试框架：
   - Pytest + pytest-asyncio + pytest-cov
   - 测试覆盖率报告
   - conftest.py配置共享fixtures

5. 代码规范：
   - 全面使用类型提示
   - Google风格的文档字符串
   - 遵循PEP 8规范
   - 模块化设计，单一职责原则

6. 日志系统：
   - 使用loguru
   - 支持控制台和文件输出
   - 自动日志轮转

请按照《软件设计流程和规范经验指导.md》中的规范创建项目。
```

### 模板2：配置代码质量工具

```
请为我的Python项目配置完整的代码质量工具链：

1. 在pyproject.toml中配置：
   - Ruff：代码检查和格式化
   - MyPy：类型检查（渐进式）
   - Pydocstyle：文档字符串检查（Google风格）
   - Bandit：安全扫描配置
   - Pytest：测试配置

2. 创建.pre-commit-config.yaml：
   - 基础hooks（尾随空格、文件大小等）
   - Ruff检查和格式化
   - MyPy类型检查
   - Bandit安全扫描

3. 创建scripts/check_code_quality.sh：
   - 运行所有代码质量检查
   - 彩色输出
   - 错误统计

4. 创建scripts/quick_check.sh：
   - 快速检查（Ruff + 测试）

请参考项目中的现有配置，确保配置一致。
```

---

## 功能开发Prompt

### 模板3：添加新功能模块

```
请帮我添加一个新功能模块：{模块名称}

要求：
1. 模块位置：{项目名称}/core/{模块名称}.py
2. 设计原则：
   - 单一职责原则：模块只负责一个功能
   - 依赖倒置：依赖抽象接口而非具体实现
   - 接口隔离：使用小而专的接口

3. 代码要求：
   - 完整的类型提示（函数参数、返回值、类属性）
   - Google风格的文档字符串
   - 使用Pydantic模型进行数据验证
   - 自定义异常处理（使用项目异常层次结构）
   - 结构化日志（使用loguru）

4. 测试要求：
   - 单元测试：tests/test_{模块名称}.py
   - 测试覆盖率：>=80%
   - 使用pytest fixtures
   - Mock外部依赖

5. 示例代码结构：
   ```python
   """
   模块描述

   详细说明模块的功能和用途。
   """
   from typing import List, Optional
   from loguru import logger
   from pydantic import BaseModel

   from {项目名称}.exceptions import ValidationError

   class {模块类名}:
       """
       类描述

       Attributes:
           attr1: 属性1描述
       """
       def __init__(self, ...):
           """初始化方法"""
           ...

       async def method(self, ...) -> ReturnType:
           """
           方法描述

           Args:
               param: 参数描述

           Returns:
               返回值描述

           Raises:
               ValidationError: 当验证失败时
           """
           ...
   ```

请按照项目规范实现，并确保代码通过所有质量检查。
```

### 模板4：添加CLI命令

```
请帮我添加一个新的CLI命令：{命令名称}

要求：
1. 使用Typer框架
2. 命令位置：{项目名称}/cli.py 或 {项目名称}/cli/{命令名称}.py
3. 命令功能：{功能描述}

4. 参数设计：
   - 使用Typer的Option和Argument
   - 提供完整的help文本
   - 参数验证使用Pydantic

5. 错误处理：
   - 使用项目自定义异常
   - 友好的错误提示
   - 记录详细日志

6. 示例结构：
   ```python
   @app.command()
   def {命令名称}(
       input: Path = typer.Option(..., "--input", "-i", help="输入描述"),
       output: Path = typer.Option(..., "--output", "-o", help="输出描述"),
       verbose: bool = typer.Option(False, "--verbose", help="显示详细日志"),
   ):
       """
       命令描述

       详细说明命令的功能和使用方法。
       """
       # 设置日志
       setup_logger(level="DEBUG" if verbose else "INFO", verbose=verbose)

       try:
           # 命令逻辑
           ...
       except ProjectError as e:
           logger.exception(f"命令执行失败: {e}")
           typer.echo(f"错误: {e}", err=True)
           raise typer.Exit(1)
   ```

7. 测试要求：
   - CLI测试：tests/test_cli.py
   - 测试各种参数组合
   - 测试错误情况

请确保命令符合项目规范，并通过所有检查。
```

---

## 代码重构Prompt

### 模板5：重构模块以符合设计原则

```
请帮我重构以下模块，使其符合SOLID原则：

模块路径：{模块路径}

重构目标：
1. 单一职责原则：拆分职责，每个类/函数只做一件事
2. 依赖倒置：依赖抽象接口而非具体实现
3. 接口隔离：使用小而专的接口
4. 开闭原则：对扩展开放，对修改关闭

具体要求：
1. 分析当前代码的问题：
   - 识别违反单一职责的地方
   - 识别硬编码依赖
   - 识别臃肿的接口

2. 设计重构方案：
   - 提取抽象基类（如果需要）
   - 拆分大函数/类
   - 使用依赖注入

3. 保持向后兼容：
   - 不破坏现有API
   - 保持测试通过
   - 逐步迁移

4. 代码质量：
   - 完整的类型提示
   - 文档字符串
   - 通过所有质量检查

请提供重构前后的对比，说明改进点。
```

### 模板6：优化代码性能

```
请帮我优化以下代码的性能：

代码位置：{文件路径}

优化目标：
1. 性能瓶颈分析
2. 优化方案设计
3. 性能测试验证

具体要求：
1. 分析性能问题：
   - 识别慢速操作（IO、网络、计算）
   - 识别不必要的重复计算
   - 识别内存泄漏风险

2. 优化策略：
   - 异步操作（如果适用）
   - 缓存机制
   - 批量处理
   - 算法优化

3. 保持代码质量：
   - 不破坏现有功能
   - 保持测试通过
   - 添加性能测试

4. 文档更新：
   - 说明优化点
   - 性能指标对比

请提供优化前后的性能对比数据。
```

---

## 测试编写Prompt

### 模板7：为新功能编写测试

```
请为以下功能编写完整的测试：

功能模块：{模块路径}
功能描述：{功能描述}

测试要求：
1. 测试文件：tests/test_{模块名}.py
2. 测试类型：
   - 单元测试：测试单个函数/方法
   - 集成测试：测试模块间协作
   - 边界测试：测试边界情况
   - 错误测试：测试异常处理

3. 测试结构：
   ```python
   """
   模块测试
   """
   import pytest
   from unittest.mock import AsyncMock, MagicMock, patch

   from {项目名称}.core.{模块} import {类名}

   class Test{类名}:
       """{类名}测试类"""

       @pytest.fixture()
       def instance(self):
           """创建实例fixture"""
           return {类名}(...)

       @pytest.mark.asyncio()
       async def test_method_success(self, instance):
           """测试方法成功情况"""
           ...

       @pytest.mark.asyncio()
       async def test_method_error(self, instance):
           """测试方法错误情况"""
           ...
   ```

4. Mock要求：
   - Mock外部依赖（API、文件IO、数据库）
   - 使用pytest fixtures
   - 使用unittest.mock

5. 覆盖率要求：
   - 目标覆盖率：>=80%
   - 关键路径：100%

6. 测试数据：
   - 使用fixtures目录的测试数据
   - 创建临时测试数据

请确保测试通过，并达到覆盖率要求。
```

### 模板8：修复失败的测试

```
请帮我修复以下失败的测试：

测试文件：{测试文件路径}
错误信息：{错误信息}

要求：
1. 分析失败原因：
   - 查看错误堆栈
   - 识别根本原因
   - 检查测试数据

2. 修复方案：
   - 如果是代码bug：修复代码
   - 如果是测试问题：修复测试
   - 如果是环境问题：更新配置

3. 验证修复：
   - 运行测试确保通过
   - 检查其他相关测试
   - 运行完整测试套件

4. 代码质量：
   - 确保修复后的代码通过所有质量检查
   - 更新相关文档

请提供修复说明和验证结果。
```

---

## 代码审查Prompt

### 模板9：代码审查检查清单

```
请对以下代码进行代码审查：

代码位置：{文件路径或PR链接}

审查维度：
1. 代码质量：
   - [ ] 通过Ruff检查（无错误）
   - [ ] 通过MyPy类型检查
   - [ ] 通过Pydocstyle文档检查
   - [ ] 代码格式正确

2. 设计原则：
   - [ ] 单一职责原则
   - [ ] 依赖倒置原则
   - [ ] 接口隔离原则
   - [ ] 开闭原则

3. 代码规范：
   - [ ] 完整的类型提示
   - [ ] Google风格文档字符串
   - [ ] 遵循PEP 8规范
   - [ ] 命名规范

4. 错误处理：
   - [ ] 使用项目自定义异常
   - [ ] 结构化异常处理
   - [ ] 友好的错误消息

5. 日志记录：
   - [ ] 关键操作有日志
   - [ ] 日志级别适当
   - [ ] 结构化日志

6. 测试：
   - [ ] 有单元测试
   - [ ] 测试覆盖率>=80%
   - [ ] 测试通过

7. 安全性：
   - [ ] 通过Bandit扫描
   - [ ] 无硬编码密钥
   - [ ] 输入验证

8. 性能：
   - [ ] 无明显的性能问题
   - [ ] 异步操作（如果适用）
   - [ ] 适当的缓存

请提供详细的审查报告，包括：
- 发现的问题（按优先级排序）
- 改进建议
- 代码示例（如果需要）
```

### 模板10：代码质量检查

```
请运行完整的代码质量检查：

检查范围：{文件路径或目录}

检查项目：
1. Ruff检查：
   ```bash
   ruff check {路径}
   ruff format --check {路径}
   ```

2. MyPy类型检查：
   ```bash
   mypy {路径}
   ```

3. Pydocstyle文档检查：
   ```bash
   pydocstyle {路径}
   ```

4. Bandit安全扫描：
   ```bash
   bandit -r {路径} -ll
   ```

5. 测试运行：
   ```bash
   pytest --cov={项目名} --cov-report=term-missing
   ```

6. Safety依赖扫描：
   ```bash
   safety check
   ```

请提供：
- 检查结果摘要
- 发现的问题列表
- 修复建议
- 优先级排序
```

---

## 文档编写Prompt

### 模板11：编写API文档

```
请为以下模块编写API文档：

模块路径：{模块路径}

文档要求：
1. 格式：Markdown
2. 位置：docs/api/{模块名}.md

3. 内容结构：
   ```markdown
   # {模块名} API文档

   ## 概述
   模块功能概述

   ## 类和方法

   ### {类名}
   类描述

   #### 方法列表
   - `method1(param) -> ReturnType`: 方法1描述
   - `method2(param) -> ReturnType`: 方法2描述

   #### 使用示例
   \`\`\`python
   from {项目名}.core.{模块} import {类名}

   instance = {类名}(...)
   result = await instance.method1(...)
   \`\`\`

   ## 异常
   - `{异常名}`: 异常描述

   ## 注意事项
   使用注意事项
   ```

4. 从代码中提取：
   - 类和方法签名
   - 文档字符串
   - 类型提示
   - 使用示例

请确保文档准确、完整、易于理解。
```

### 模板12：编写开发指南

```
请编写开发指南文档：

文档名称：DEVELOPMENT.md

内容要求：
1. 项目概述
2. 开发环境设置
3. 代码质量工具使用
4. 测试指南
5. 提交规范
6. 常见问题

参考项目中的DEVELOPMENT.md，确保：
- 命令准确
- 示例可运行
- 说明清晰
- 包含故障排除

请更新文档，确保与当前项目配置一致。
```

---

## 问题修复Prompt

### 模板13：修复Bug

```
请帮我修复以下Bug：

问题描述：{问题描述}
错误信息：{错误信息}
相关文件：{文件路径}

修复要求：
1. 问题分析：
   - 查看错误堆栈
   - 识别根本原因
   - 检查相关代码

2. 修复方案：
   - 最小化修改
   - 保持向后兼容
   - 添加错误处理

3. 测试验证：
   - 编写回归测试
   - 运行相关测试
   - 确保所有测试通过

4. 代码质量：
   - 通过所有质量检查
   - 更新文档（如果需要）

请提供：
- 问题根本原因分析
- 修复方案说明
- 修复后的代码
- 测试验证结果
```

### 模板14：处理依赖冲突

```
请帮我解决以下依赖冲突：

冲突描述：{冲突描述}
相关依赖：{依赖列表}

解决要求：
1. 分析冲突：
   - 识别冲突的依赖
   - 查看版本要求
   - 检查兼容性

2. 解决方案：
   - 更新依赖版本
   - 使用兼容版本
   - 替换冲突依赖（如果需要）

3. 验证：
   - 安装依赖
   - 运行测试
   - 检查功能

4. 更新文档：
   - 更新pyproject.toml
   - 更新README.md（如果需要）

请提供：
- 冲突分析
- 解决方案
- 验证结果
```

---

## 通用Prompt模板

### 模板15：遵循项目规范

```
在编写/修改代码时，请严格遵循以下项目规范：

1. 代码结构：
   - 模块化设计，单一职责原则
   - 依赖倒置，使用抽象接口
   - 接口隔离，小而专的接口

2. 代码质量：
   - 全面使用类型提示
   - Google风格文档字符串
   - 通过Ruff、MyPy、Pydocstyle检查

3. 错误处理：
   - 使用项目自定义异常
   - 结构化异常处理
   - 使用loguru记录日志

4. 测试：
   - 编写单元测试
   - 测试覆盖率>=80%
   - 使用pytest fixtures

5. 安全：
   - 通过Bandit扫描
   - 不硬编码密钥
   - 输入验证

请参考《软件设计流程和规范经验指导.md》中的详细规范。
```

### 模板16：代码生成规范

```
请按照以下规范生成代码：

1. 文件头部：
   ```python
   """
   模块描述

   详细说明模块的功能和用途。
   """
   ```

2. 导入顺序：
   - 标准库
   - 第三方库
   - 本地应用/库

3. 类型提示：
   - 所有函数参数和返回值
   - 类属性
   - 使用typing模块的类型

4. 文档字符串（Google风格）：
   ```python
   def function(param: Type) -> ReturnType:
       """
       函数描述

       Args:
           param: 参数描述

       Returns:
           返回值描述

       Raises:
           ExceptionType: 异常描述
       """
   ```

5. 错误处理：
   ```python
   try:
       # 操作
   except SpecificError as e:
       logger.error(f"错误描述: {e}")
       raise CustomError(f"友好错误消息: {e}") from e
   ```

6. 日志记录：
   ```python
   from loguru import logger

   logger.debug("调试信息")
   logger.info("信息")
   logger.warning("警告")
   logger.error("错误")
   logger.exception("异常（包含堆栈）")
   ```

请确保生成的代码符合以上所有规范。
```

---

## 使用建议

### 1. 组合使用

可以将多个模板组合使用，例如：
- 项目初始化 + 代码质量工具配置
- 功能开发 + 测试编写
- 代码审查 + 问题修复

### 2. 自定义模板

根据项目特点，可以：
- 修改模板中的占位符
- 添加项目特定的要求
- 调整检查项和优先级

### 3. 迭代改进

- 根据使用效果调整模板
- 添加新的模板类型
- 优化模板描述

---

## 参考文档

- [软件设计流程和规范经验指导.md](./软件设计流程和规范经验指导.md)
- [DEVELOPMENT.md](./DEVELOPMENT.md)
- [TOOLS_QUICK_START.md](./TOOLS_QUICK_START.md)
