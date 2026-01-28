# Python项目开发规范 Skill

本文档是一个Cursor Skill配置文件，用于指导AI助手按照项目规范进行Python开发。

## 使用说明

### 作为Cursor Skill使用

将此文件复制到项目的 `.cursor/skills/python-project-standards/` 目录下，命名为 `SKILL.md`：

```bash
mkdir -p .cursor/skills/python-project-standards
cp Skills.md .cursor/skills/python-project-standards/SKILL.md
```

### 作为个人Skill使用

复制到个人Skills目录：

```bash
mkdir -p ~/.cursor/skills/python-project-standards
cp Skills.md ~/.cursor/skills/python-project-standards/SKILL.md
```

---

## Skill文件内容

创建 `.cursor/skills/python-project-standards/SKILL.md` 文件，内容如下：

```markdown
---
name: python-project-standards
description: Enforces Python project development standards including code structure, type hints, documentation, testing, and code quality tools. Use when writing Python code, creating new modules, refactoring code, or when the user asks about Python best practices, code quality, or project structure.
---

# Python Project Development Standards

## Core Principles

When writing Python code, follow these principles:

1. **Modular Design**: Single responsibility, dependency inversion, interface segregation
2. **Type Safety**: Complete type hints for all functions, methods, and class attributes
3. **Documentation**: Google-style docstrings for all public APIs
4. **Testing**: Unit tests + integration tests with >=80% coverage
5. **Code Quality**: Pass Ruff, MyPy, and Pydocstyle checks
6. **Error Handling**: Use project custom exceptions, structured logging with loguru
7. **Professional**: Use mature libraries and tools, robust code logic
8. **Maintainability**: Modular design, comprehensive error handling, structured logging
9. **Readability**: Clear comments, type hints, code style compliance
10. **Interactivity**: Clear CLI with Typer, progress bars with tqdm

## Code Structure

### Module Organization

```
project_name/
├── project_name/
│   ├── __init__.py
│   ├── __main__.py        # CLI entry point
│   ├── cli.py             # Typer CLI commands
│   ├── core/              # Core business logic
│   │   ├── providers/    # Provider abstractions (dependency inversion)
│   │   │   ├── base.py   # Abstract base class
│   │   │   └── concrete.py # Concrete implementations
│   │   └── ...
│   ├── models/           # Pydantic data models
│   │   ├── config.py     # Configuration models
│   │   └── data.py       # Business data models
│   ├── cli/              # CLI subcommands (if CLI is complex)
│   │   ├── config_handler.py
│   │   └── ...
│   ├── utils/            # Utility functions
│   │   ├── logger.py     # Logging configuration
│   │   └── cache.py      # Cache utilities
│   ├── exceptions.py     # Custom exceptions
│   └── config/           # Configuration files
│       └── default.yaml
├── tests/
│   ├── conftest.py       # Shared fixtures
│   ├── fixtures/         # Test data
│   ├── integration/      # Integration tests
│   └── test_*.py         # Unit tests
├── scripts/              # Automation scripts
│   ├── check_code_quality.sh
│   └── quick_check.sh
└── pyproject.toml        # Project configuration
```

### Import Order

```python
# 1. Standard library
import asyncio
from pathlib import Path
from typing import List, Optional

# 2. Third-party libraries
import typer
from loguru import logger
from pydantic import BaseModel

# 3. Local application/library
from project_name.core.module import Class
```

## Type Hints

Always provide complete type hints:

```python
from typing import List, Optional, Tuple, Dict, AsyncIterator
from pathlib import Path

# Function signatures
async def generate_cards(
    content: str,
    config: GenerationConfig,
    output_dir: Optional[Path] = None,
) -> Tuple[List[Card], GenerationStats]:
    """Generate cards from content."""
    ...

# Class attributes
class CardGenerator:
    def __init__(self, llm_config: LLMConfig, cache: Optional[FileCache] = None):
        self.llm_config: LLMConfig = llm_config
        self.cache: Optional[FileCache] = cache
        self.cards: List[Card] = []
```

## Documentation (Google Style)

```python
class CardGenerator:
    """
    Card generator class.

    Responsible for generating cards using LLM, parsing responses,
    and performing quality filtering and deduplication.

    Attributes:
        llm_config: LLM configuration object
        cache: Cache object (optional)
    """

    async def generate_cards(
        self,
        content: str,
        config: GenerationConfig,
    ) -> List[Card]:
        """
        Generate cards from input content.

        Automatically splits content and makes multiple API calls
        if the required number of cards exceeds single request limit.

        Args:
            content: Input content, can be text or Markdown format
            config: Generation configuration with card type, count, difficulty

        Returns:
            List of generated cards

        Raises:
            CardGenerationError: When LLM call fails or parsing fails
            ValidationError: When configuration parameters are invalid

        Example:
            >>> generator = CardGenerator(llm_config)
            >>> cards = await generator.generate_cards(
            ...     content="Python is a programming language",
            ...     config=GenerationConfig(card_type="basic", card_count=5)
            ... )
            >>> len(cards)
            5
        """
        ...
```

## Error Handling

Use project custom exceptions with structured error handling:

```python
from project_name.exceptions import (
    CardGenerationError,
    ConfigurationError,
    ProviderError,
)
from loguru import logger

async def generate_cards(...) -> List[Card]:
    """Generate cards."""
    try:
        # Validate configuration
        if not config.is_valid():
            raise ConfigurationError("Invalid configuration")

        # Call LLM
        response = await self.llm_engine.generate(prompt)

        # Parse response
        cards = self.parse_response(response)
        return cards

    except ProviderError as e:
        logger.error(f"LLM provider error: {e}")
        raise CardGenerationError(f"Generation failed: {e}") from e
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise CardGenerationError(f"Data validation failed: {e}") from e
    except Exception as e:
        logger.exception("Unknown error during card generation")
        raise CardGenerationError(f"Unknown error: {e}") from e
```

## Logging (loguru)

```python
from loguru import logger

# Different log levels
logger.debug("Debug info: variable = {}", variable_value)
logger.info("Processing complete, generated {} cards", card_count)
logger.warning("API response format abnormal, trying fallback parser")
logger.error("Generation failed: {}", error_message)
logger.exception("Exception occurred")  # Includes stack trace

# Structured logging
logger.bind(user_id=123, request_id="abc").info("Processing user request")
```

## Testing

### Test Structure

```python
"""
Module tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from project_name.core.module import ClassName

class TestClassName:
    """ClassName test class"""

    @pytest.fixture()
    def instance(self):
        """Create instance fixture"""
        return ClassName(...)

    @pytest.mark.asyncio()
    async def test_method_success(self, instance):
        """Test successful method execution"""
        ...

    @pytest.mark.asyncio()
    async def test_method_error(self, instance):
        """Test error handling"""
        ...
```

### Coverage Requirements

- Target coverage: >=80%
- Critical paths: 100%
- Use pytest fixtures for shared test data
- Mock external dependencies (APIs, file I/O, databases)

## Code Quality Checks

Before committing, ensure code passes:

1. **Ruff**: `ruff check project_name/ && ruff format --check project_name/`
2. **MyPy**: `mypy project_name/`
3. **Pydocstyle**: `pydocstyle project_name/`
4. **Tests**: `pytest --cov=project_name --cov-report=term-missing`
5. **Security**: `bandit -r project_name/ -ll`

## Design Patterns

### Dependency Inversion

```python
# ✅ Good: Depend on abstraction
class CardGenerator:
    def __init__(self, llm_provider: BaseLLMProvider):  # Abstract
        self.provider = llm_provider

# ❌ Bad: Depend on concrete implementation
class CardGenerator:
    def __init__(self):
        self.provider = OpenAIProvider()  # Hard-coded
```

### Single Responsibility

```python
# ✅ Good: Single responsibility
class CardGenerator:
    """Only responsible for card generation"""
    async def generate_cards(self, ...) -> List[Card]:
        ...

class CardFilter:
    """Only responsible for filtering"""
    def filter_cards(self, cards: List[Card]) -> List[Card]:
        ...

# ❌ Bad: Multiple responsibilities
class CardProcessor:
    """Does everything"""
    async def generate_cards(self, ...): ...
    def filter_cards(self, ...): ...
    def deduplicate_cards(self, ...): ...
    def export_cards(self, ...): ...
```

## Pydantic Models

Use Pydantic for data validation:

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class LLMConfig(BaseModel):
    """
    LLM configuration model.

    Attributes:
        provider: LLM provider (openai/deepseek/ollama)
        model_name: Model name
        api_key: API key (optional, can be from env var)
    """

    provider: LLMProvider = Field(
        default=LLMProvider.DEEPSEEK,
        description="LLM provider"
    )
    model_name: str = Field(
        default="deepseek-chat",
        description="Model name"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key (prefer environment variable)"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature parameter"
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate API key format."""
        if v and v.startswith("${") and v.endswith("}"):
            # Environment variable reference
            return v
        return v
```

## CLI with Typer

```python
import typer
from pathlib import Path
from loguru import logger

app = typer.Typer()

@app.command()
def generate(
    input: Path = typer.Option(..., "--input", "-i", help="Input file path"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed logs"),
):
    """
    Generate cards from input file.

    Detailed description of the command functionality.
    """
    # Setup logging
    setup_logger(level="DEBUG" if verbose else "INFO", verbose=verbose)

    try:
        # Command logic
        ...
    except ProjectError as e:
        logger.exception(f"Command failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
```

## Progress Bars with tqdm

```python
from tqdm import tqdm

# File processing progress
with tqdm(total=file_count, desc="Processing files") as pbar:
    for file in files:
        process_file(file)
        pbar.update(1)

# API call progress
with tqdm(total=len(chunks), desc="Generating cards") as pbar:
    for chunk in chunks:
        await generate_chunk(chunk)
        pbar.update(1)
```

## Security

### API Keys

```python
# ❌ Bad: Hard-coded
api_key = "sk-1234567890abcdef"

# ✅ Good: Environment variable
import os
from python_dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("API_KEY")
```

### Input Validation

```python
from pydantic import BaseModel, Field, field_validator

class UserInput(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    card_count: int = Field(..., ge=1, le=100)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Check for malicious content."""
        if "DROP TABLE" in v.upper():
            raise ValueError("Potential SQL injection detected")
        return v
```

## Quick Reference

### When Writing Code

- [ ] Complete type hints for all functions/methods
- [ ] Google-style docstrings for public APIs
- [ ] Use project custom exceptions
- [ ] Structured logging with loguru
- [ ] Pydantic models for data validation
- [ ] Single responsibility principle
- [ ] Dependency inversion (depend on abstractions)
- [ ] Clear CLI with Typer
- [ ] Progress bars with tqdm for long operations

### Before Committing

- [ ] `ruff check --fix project_name/`
- [ ] `ruff format project_name/`
- [ ] `mypy project_name/` (no critical errors)
- [ ] `pytest --cov=project_name` (all tests pass, >=80% coverage)
- [ ] `bandit -r project_name/ -ll` (no high-severity issues)

## Additional Resources

- See `软件设计流程和规范经验指导.md` for detailed guidelines
- See `prompt模板.md` for prompt templates
- See `DEVELOPMENT.md` for development workflow
```

---

## 安装步骤

### 方法1：项目级Skill（推荐）

```bash
# 在项目根目录执行
mkdir -p .cursor/skills/python-project-standards

# 创建SKILL.md文件
cat > .cursor/skills/python-project-standards/SKILL.md << 'EOF'
[将上面的Skill文件内容粘贴到这里]
EOF
```

### 方法2：个人Skill

```bash
# 创建个人Skills目录
mkdir -p ~/.cursor/skills/python-project-standards

# 创建SKILL.md文件
cat > ~/.cursor/skills/python-project-standards/SKILL.md << 'EOF'
[将上面的Skill文件内容粘贴到这里]
EOF
```

---

## 验证安装

安装后，Cursor会自动识别这个Skill。当你在编写Python代码时，AI助手会自动应用这些规范。

### 测试方法

1. 打开Cursor编辑器
2. 创建一个新的Python文件
3. 输入代码时，AI助手应该会：
   - 自动添加类型提示
   - 建议Google风格的文档字符串
   - 遵循项目代码结构规范
   - 使用项目自定义异常
   - 使用loguru进行日志记录
   - 使用Typer构建CLI
   - 使用tqdm显示进度

---

## 自定义配置

你可以根据项目需求修改Skill文件：

1. **修改描述**：更新frontmatter中的`description`，添加项目特定的触发词
2. **添加项目特定规范**：在Skill文件中添加项目特有的编码规范
3. **更新示例**：使用项目中的实际代码示例

---

## 注意事项

1. **Skill文件大小**：SKILL.md应该保持在合理大小，详细内容可以放在参考文档中
2. **描述要具体**：frontmatter中的`description`应该包含触发词，帮助AI决定何时应用这个Skill
3. **使用第三人称**：描述应该用第三人称（"Enforces standards"而不是"I enforce standards"）
4. **保持更新**：当项目规范变化时，记得更新Skill文件

---

## 参考

- [Cursor Skills文档](https://cursor.sh/docs/skills)
- [软件设计流程和规范经验指导.md](./软件设计流程和规范经验指导.md)
- [prompt模板.md](./prompt模板.md)
