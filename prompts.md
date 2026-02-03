@ai-anki-cards/ankigen/cli/interactive.py 修改完善代码，以实现：
1. 在交互模式下，要有效处理错误，避免因为出错而直接退出，要正确地处理错误，提示错误 和 log信息和log文件，并回到初始选择界面，请求修改或改正可能存在错误的地方。
2. 在交互模式下，现在只能依次选择参数，而不能重新修改选择，不能够灵活地选择修改。请改进代码，实现更灵活方便的交互。

应实现成如下交互模式：
```bash

请选择要执行的命令:
- [1] generate - 生成Anki卡片
- [2] config - 配置管理
- [3] convert - 转换卡片格式
- [0] exit - 退出

请选择要执行的命令: generate

---

请设置或选择参数：
- [1] 输入文件或目录路径:
- [2]输出文件路径: (./output/ 默认)
- [3] 卡片类型: basic （默认），可选 basic/cloze/mcq
- [4] 卡片数量（留空则自动估算）: 10 (默认)
- [5] LLM提供商: deepseek （默认），可选 openai/deepseek/ollama/anthropic/custom
- [6] 模型名称: deepseek-chat （默认），可选 deepseek-chat/gpt-4o/claude-3-sonnet/llama3
- [7] 配置文件路径（可选，留空跳过）: (./.config.yml 默认)
- [0] 返回上一级

...
请确认执行: y/n
```
3. 在交互模式下，在选择 LLM 提供商时，要验证 api 密钥是否正确，如果不正确，要提示错误，提示重新输入 api 密钥。
  - 也要显示哪些提供商的密钥已经配置好，是可用的。
4. 在交互模式下，在选择模型名称时，模型名称可以自定义输入，也可以从配置文件中有的模型名称中选择。
5. 配置文件爱你路径也要显示默认的路径，并且可以选择查看配置文件内容。


请逐步移除 ai-anki-cards/ankigen 中的 @providers  代码，全部替换成对 llm_engine 的使用，因为 ankigen 中的 providers 与 llm_engine 中的providers  @llm_engine 造成了不必要的混淆。 如果 llm_engine 不能完全满足 ankigen 的要求，可以进一步修改完善 llm_engine  @llm_engine 。注意要提高代码质量，删除冗余冗杂部分，使代码精简、鲁棒、高效、专业、逻辑清晰直接。


请分析项目框架、代码框架，梳理所使用的工具链、第三方库等，梳理代码结构布局，从而形成一篇软件设计流程和规范经验指导，用于后续继续编写新的python项目时来借鉴学习。并形成一篇 Skiils.md，用于配置skills。

请分析项目框架、代码框架，代码质量，进一步从如下方面重构和提升代码质量：

- 代码结构与组织
模块化设计
单一职责原则：每个模块/函数只做一件事
依赖倒置：高层模块不依赖低层模块，都依赖抽象
接口隔离：使用小而专的接口
- 集成代码质量工具
 静态代码分析（flake8 pylint mypy black isort）与代码格式化（ruff）
- 类型提示与文档
 全面的类型提示，文档字符串规范
- 测试策略
 测试金字塔（单元测试+集成测试）， 测试配置文件
- 错误处理与日志
 结构化异常处理，日志配置
- 依赖管理
 现代依赖管理，虚拟环境管理
- 安全考虑
 安全扫描工具

---
添加新的工具：

给定输入文件夹，自动遍历所有的md文件，逐一生成卡片组（标签为这个文件的标题/主题）


用于卡片化给定的笔记库

新功能：

- 根据内容自动判定生成什么样类型的卡片？
- 支持数学公式
-

给定一个笔记库（md files），可以做哪些工作？如何维护自己的知识库？在笔记库之上可以做哪些工作？

---

经过测试发现：
对于 basic/cloze 卡片，平均每张卡片用时约 5s、使用 token 约 150 个；
对于 mcq 卡片，平均每张卡片用时约 15s、使用 token 约 500 个；
请添加新模块，用于估算当前输入文件、当前卡片类型、卡片生成数，所需要的时间和 token，从而自适应设定内容切分 和 每次 api 调用时所要求生成的卡片数量。

单次 max_tokens 设置为 4000（平衡生成质量和耗时），可以根据当前输入和模型信息自适设置。

例如，如果要求生成 20 张 mcq 卡片，20 * 500 / 4000 = 2.5,就分 3 次生成，将文本切分成 3 份，调用 3 次 api。

关于模型的信息：

Deepseek deepseek-chat 模型：

CONTEXT LENGTH：128k

MAX OUTPUT：
DEFAULT: 4K
MAXIMUM: 8K

Speed: about 30 tokens/s

可以将这些信息格式化存储在 model_info.yml 配置文件中，供程序读取与使用。

---

@ai-anki-cards/ankigen/utils/cache.py cache 功能似乎不管用了，请

Use a Gen Z design style (like Duolingo)。

创建一个能够将上传的文件（pdf/docx 等）或纯文本，利用大模型 LLM AI ，一键生成 anki cards deck 的应用。要求如下：

- 可以选择不同类型的卡片：Basic, Cloze, Basic MCQs 等
- 可以选择创建 cards 的数量
- 可以添加设置提示词
- 可以自定义添加模型提供商、模型、API 等
- 支持导出成纯文本格式的卡片或笔记（txt），Deck (.apkg) 等格式
- ...
  创建一个 python 脚本，能够输入纯文本文件或 markdown 文件，利用大模型 LLM AI ，生成 anki cards deck。

python 脚本或代码要专业鲁棒：

- 专业性：
  - 充分利用使用现有的成熟的库（lib）与工具
  - 代码逻辑清晰专业
  - 代码鲁棒性强
- 较好的可维护性：
  - 代码模块化设计、分文件管理（对于较复杂、编程量较大的编程要求）
  - 有完善的错误处理与异常处理
  - 有完善的日志记录 `loguru`
- 较好的可读性：
  - 简洁清晰直观的注释
  - 清晰的类型注释
  - 遵循代码风格要求
- 良好的交互性：
  - 清晰简洁的命令行参数与交互 `typer`
  - 命令行输出简洁清晰美观
  - 用进度条显示备份/恢复进度 `tqdm`
- 文档：
  - READEME_XXX.md 文档说明该代码的主要内容、主要结构、运行方式、主要函数接口
  - XXX 为脚本主题/名称
- 测试要求：

  - 编写简单的测试脚本/demo 脚本测试验证 所编写的 python 脚本的正确性
  - 在 `tests` 目录下编写单元测试与集成测试
  - 对核心逻辑要有单元测试
  - 对程序整体逻辑与功能进行集成测试

- 可视化：
  - 使用 matplotlib/seaborn 绘图
  - 使用 plotly 绘图
  - 绘图要求：
    - 美观、专业、清晰、直观
    - 保存为矢量图

##

以下是一个经过优化和完善的提示词版本，旨在更清晰、专业地指导大模型生成一个功能完整且可扩展的 Python 脚本：

---

**提示词：**

你是一位经验丰富的 Python 开发工程师，擅长构建 CLI 工具、集成 LLM API、处理文档解析和生成 Anki 卡片。请设计并实现一个生产级的 Anki 卡片批量生成系统。

开发一个功能完备、配置灵活、易于扩展的 Python 命令行工具，能够自动解析文本/Markdown 文件，调用大语言模型生成高质量 Anki 卡片，并支持多种导出格式。

请设计并实现一个 Python 脚本，用于将纯文本文件或 Markdown 文件的内容转换为 Anki 卡片组（deck）。该脚本应具备以下功能与特性：

### 核心功能

1. **输入支持**：

   - 支持读取 `.txt` 和 `.md` 文件作为输入。
   - 允许用户通过命令行参数或配置文件指定输入文件路径。

2. **卡片类型选择**：

   - 支持生成多种 Anki 卡片类型，包括但不限于：
     - **Basic**（正反面卡片）
     - **Cloze**（填空卡片）
     - **Basic MCQs**（基础多项选择题）
   - 允许用户通过参数或交互式菜单选择卡片类型。

3. **生成数量控制**：
   - 允许用户指定生成卡片的数量（例如，从输入内容中提取前 N 条或随机选择 N 条）。
   - 若未指定数量，则默认基于输入内容自动生成所有可能的卡片。
     - 按内容比例生成（如：每 500 字生成 1 张）
     - 智能密度控制（根据内容复杂度动态调整）
4. **大模型集成**：

   - 集成 LLM（如 DeepSeek、OpenAI GPT、Claude、本地模型等）用于智能生成卡片内容。
   - 允许用户通过配置文件或命令行参数自定义以下模型设置：
     - 模型提供商（如 DeepSeek、OpenAI、Anthropic、Groq、Ollama 等）
     - 模型名称（如 `deepseek-chat`、`gpt-4o`、`claude-3-sonnet`、`llama3` 等）
     - API 密钥与基础 URL（支持自定义端点，如本地部署的模型）
     - 生成参数（如温度、最大令牌数等）
     - 自定义 OpenAI 兼容 API 端点

5. **提示词管理**：

   - 提供默认提示词模板，用于指导 LLM 根据输入内容生成指定类型的卡片。
   - 允许用户通过外部文件或命令行参数自定义提示词，以适应特定领域或需求。

6. **导出格式**：
   - 支持导出为以下格式：
     - 纯文本（`.txt`），每行包含卡片问题与答案，用制表符分隔。
     - Anki 卡片包文件（`.apkg`），可直接导入 Anki 软件。
     - 可选支持其他格式（如 CSV、JSON 等）。

### 配置

- 使用配置文件（如 `config.yaml` 或 `config.json`）保存常用设置，如默认模型、API 密钥、提示词模板等。
- 可配置请求参数：temperature, top_p, max_tokens, presence_penalty 等
  - 自动速率限制和重试机制（指数退避）
  - 支持命令行参数覆盖配置文件中的设置。

### 1. 输入处理模块

- **文件格式支持**：

  - 纯文本文件（UTF-8 编码，自动检测 BOM）
  - Markdown 文件（.md, .markdown），支持解析标题层级、代码块、列表等结构
  - 支持批量处理文件夹（递归遍历）
  - 支持文件编码自动检测和错误处理
  - **批量处理**：
    - 支持批量处理多个输入文件，并合并或分别生成卡片组。
    - -i -o 可以指定输入输出目录，批量处理

- **内容预处理**：
  - 智能文本分块（按 token 长度、段落、标题层级）
  - 自动去除冗余空白字符
  - 提取 Markdown 元数据（YAML front matter）
  - 生成内容摘要和关键词
  - 对输入文本进行清洗、分段或提取关键信息，以提高卡片生成质量。
  - 支持 Markdown 解析，保留或转换格式（如将标题作为卡片分类依据）。

### 2. LLM 集成引擎

- **多提供商支持**：

  - OpenAI API (GPT-4, GPT-3.5-turbo)
  - Anthropic Claude
  - Google Gemini
  - 本地模型（Ollama, vLLM, text-generation-webui）
  - 自定义 OpenAI 兼容 API 端点

- **配置管理**：

  - 通过配置文件（YAML/JSON）或环境变量管理 API 密钥
  - 支持多 API 密钥轮询和故障转移
  - 可配置请求参数：temperature, top_p, max_tokens, presence_penalty 等
  - 自动速率限制和重试机制（指数退避）

- **提示词工程系统**：
  - 内置多种卡片类型的提示词模板（支持 Jinja2 模板引擎）
  - 支持用户自定义提示词文件
  - 动态变量注入（{content}, {card_count}, {difficulty}等）
  - 提示词版本管理和 A/B 测试支持

### 3. 卡片类型生成器

- **Basic 卡片**：

  - 正面：问题/术语
  - 背面：答案/解释
  - 支持添加图片、音频占位符

- **Cloze 填空卡**：

  - 自动识别关键概念生成{{c1::答案}}格式
  - 支持多个填空层级（c1, c2, c3...）
  - 智能避免过度标记

- **选择题（MCQs）**：

  - 生成 4-5 个选项，包含 1 个正确答案
  - 干扰项需符合认知逻辑
  - 支持解释说明字段

- **高级卡片类型**：（先不实现，留下接口，后续实现）
  - 反转卡片（Basic and reversed card）
  - 输入型卡片（Type-in-the-answer）
  - 图片遮挡卡（Image Occlusion，生成 SVG 遮罩）

### 4. 生成控制参数

- **数量控制**：

  - 精确卡片数量或范围（如：10-15 张）
  - 按内容比例生成（如：每 500 字生成 1 张）
  - 智能密度控制（根据内容复杂度动态调整）

- **难度分级**：

  - 简单/中等/困难三级难度
  - 基于 SM-2 算法预估初始间隔

- **质量过滤**：
  - 自动去重（语义相似度检测）
  - 卡片完整性验证
  - LLM 自我评估机制（生成后校验）

### 5. 导出模块

- **Anki 原生格式**：

  - `.apkg`文件（通过 genanki 库）
  - 支持牌组元数据（描述、标签、创建者）
  - 媒体文件打包（图片、音频）
  - 增量更新（避免重复导入）

- **文本格式**：

  - CSV（兼容 Anki 导入向导）
  - TSV（制表符分隔）
  - Markdown 表格
  - JSONL（每行一个 JSON 对象）

- **其他格式**：
  - 导出为 AnkiConnect 批量添加格式
  - 生成导入脚本（AppleScript/AutoHotkey）

## 代码结构

```
ankigen/
├── __main__.py          # CLI入口
├── core/
│   ├── parser.py        # 文件解析器
│   ├── llm_engine.py    # LLM集成引擎
│   ├── card_generator.py # 卡片生成逻辑
│   └── exporter.py      # 导出模块
├── models/
│   ├── card.py          # 卡片数据模型（Pydantic）
│   └── config.py        # 配置模型
├── templates/
│   ├── basic.j2         # 提示词模板
│   ├── cloze.j2
│   └── mcq.j2
├── utils/
│   ├── token_counter.py # Token计算
│   ├── cache.py         # 缓存管理
│   └── logger.py        # 日志配置
├── config/
│   └── default.yaml     # 默认配置
└── tests/               # 单元测试和集成测试
```

### 依赖管理

- 使用`pyproject.toml`（Poetry 或 PDM）
- 主要依赖：`click`/`typer`（CLI）、`pydantic`（配置）、`aiohttp`（异步 API）、`jinja2`（模板）、`genanki`（Anki 包）、`tiktoken`（token 计算）
- 可选依赖：`ollama`、`anthropic`、`google-generativeai`

## 代码质量标准

python 脚本或代码要专业鲁棒：

- 专业性：
  - 充分利用使用现有的成熟的库（lib）与工具
  - 代码逻辑清晰专业
  - 代码鲁棒性强
- 较好的可维护性：
  - 代码模块化设计、分文件管理（对于较复杂、编程量较大的编程要求）
  - 有完善的错误处理与异常处理
  - 有完善的日志记录 `loguru`
- 较好的可读性：
  - 简洁清晰直观的注释
  - 清晰的类型注释
  - 遵循代码风格要求
- 良好的交互性：
  - 清晰简洁的命令行参数与交互
  - 命令行输出简洁清晰美观
  - 用进度条显示备份/恢复进度 `tqdm`
- 文档：
  - READEME_XXX.md 文档说明该代码的主要内容、主要结构、运行方式、主要函数接口
  - XXX 为脚本主题/名称
- 测试要求：
  - 编写简单的测试脚本/demo 脚本测试验证 所编写的 python 脚本的正确性
  - 在 `test` 目录下编写单元测试与集成测试
  - 对核心逻辑要有单元测试
  - 对程序整体逻辑与功能进行集成测试

### 使用示例

提供至少一个使用示例，展示如何通过命令行运行脚本，例如：

```bash
# 默认配置
python ankigen.py notes.md

# 指定卡片类型、数量、模型、导出格式
python ankigen.py --input notes.md --card-type cloze --num-cards 20  --provider openai  --model openai --model-name gpt-4o --export-format apkg --prompt "你是一个经验丰富的英语老师，请根据以下内容生成20张英语单词卡片：" --config config.yaml

# 缩写
python ankigen.py -i notes.md -t cloze -n 20 -m deepseek-chat -o notes.apkg -c config.yaml

python ankigen.py -i notes.md -t cloze -n 20 -m deepseek-chat -o notes.apkg -p "你是一个经验丰富的英语老师，请根据以下内容生成20张英语单词卡片："
```

- **交互式模式**：

  - 向导式配置（首次运行）
  - 实时预览生成结果
  - 手动编辑和筛选卡片

- **高级选项**：
  - `--dry-run`：预览生成效果不调用 API
  - `--verbose`：详细日志输出

### 输出要求

- 生成的卡片应确保内容准确、格式正确，适合导入 Anki 进行学习。
- 导出的 `.apkg` 文件应包含完整的卡片信息和可选的卡片模板样式。

## 交付物清单

1. **核心代码**：完整可运行的 Python 包
2. **配置文件**：`pyproject.toml`, `default.yaml`, `.env.example`
3. **文档**：
   - README.md（安装、配置、使用示例）
   - API 文档（代码文档字符串）
   - 贡献指南（CONTRIBUTING.md）
4. **测试套件**：pytest 测试文件 + 测试数据
5. **示例文件**：sample.md, sample_config.yaml
