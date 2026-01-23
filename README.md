# AnkiGen - Anki卡片批量生成工具

一个功能完备的Python CLI工具，用于从文本/Markdown文件自动生成Anki卡片，支持多种LLM提供商和卡片类型。

## 功能特性

- 📝 **多格式输入支持**: 支持`.txt`和`.md`文件，支持批量处理目录
- 🎴 **多种卡片类型**: Basic（正反面）、Cloze（填空）、MCQ（多项选择）
- 🤖 **多LLM集成**: 支持OpenAI、DeepSeek、Ollama等LLM提供商
- 📦 **多格式导出**: 支持`.apkg`、`.txt`、`.csv`、`.json`、`.jsonl`格式
- ⚙️ **灵活配置**: 支持配置文件、环境变量和命令行参数
- 🔄 **智能缓存**: 避免重复API调用
- 🛡️ **错误处理**: 自动重试、故障转移、优雅降级
- 📊 **进度显示**: 使用tqdm显示处理进度

## 安装

### 使用pip安装

```bash
pip install -r requirements.txt
```

### 开发模式安装

```bash
pip install -e .
```

## 快速开始

### 1. 配置API密钥

设置环境变量（推荐）：

```bash
export DEEPSEEK_API_KEY="your_api_key_here"
# 或
export OPENAI_API_KEY="your_api_key_here"
```

或创建`.env`文件：

```bash
DEEPSEEK_API_KEY=your_api_key_here
```

### 2. 生成卡片

```bash
# 基本用法
python -m ankigen generate -i notes.md -o cards.apkg

# 指定卡片类型和数量
python -m ankigen generate -i notes.md -o cards.apkg -t cloze -n 20

# 指定LLM提供商和模型
python -m ankigen generate -i notes.md -o cards.apkg --provider deepseek -m deepseek-chat

# 使用配置文件
python -m ankigen generate -i notes.md -o cards.apkg -c config.yaml

# 预览模式（不调用API）
python -m ankigen generate -i notes.md -o cards.apkg --dry-run
```

### 3. 配置管理

```bash
# 初始化配置文件
python -m ankigen config --init

# 显示当前配置
python -m ankigen config --show
```

## 使用示例

### 示例1: 从Markdown文件生成Basic卡片

```bash
python -m ankigen generate \
  --input notes.md \
  --output cards.apkg \
  --card-type basic \
  --num-cards 10 \
  --provider deepseek \
  --model-name deepseek-chat
```

### 示例2: 生成Cloze填空卡片

```bash
python -m ankigen generate \
  -i notes.md \
  -o cloze_cards.apkg \
  -t cloze \
  -n 15
```

### 示例3: 批量处理目录

```bash
python -m ankigen generate \
  -i ./notes_directory \
  -o all_cards.apkg \
  -t basic \
  -n 50
```

### 示例4: 导出为CSV格式

```bash
python -m ankigen generate \
  -i notes.md \
  -o cards.csv \
  --export-format csv
```

### 示例5: 使用自定义提示词

```bash
python -m ankigen generate \
  -i notes.md \
  -o cards.apkg \
  -p "你是一位经验丰富的英语老师，请根据以下内容生成20张英语单词卡片："
```

## 配置文件

创建`config.yaml`文件：

```yaml
llm:
  provider: deepseek
  model_name: deepseek-chat
  api_key: ${DEEPSEEK_API_KEY}
  temperature: 0.7
  max_tokens: 2000

generation:
  default_card_type: basic
  card_count: 10
  difficulty: medium

export:
  default_format: apkg
  deck_name: "My Deck"
```

详细配置示例请参考`sample_config.yaml`。

## 支持的LLM提供商

- **OpenAI**: GPT-4, GPT-3.5-turbo等
- **DeepSeek**: deepseek-chat, deepseek-coder等
- **Ollama**: 本地部署的模型
- **Custom**: 自定义OpenAI兼容API端点

## 卡片类型

### Basic卡片
标准的前后卡片，正面是问题，背面是答案。

### Cloze卡片
填空卡片，使用`{{c1::答案}}`格式标记填空位置。

### MCQ卡片
多项选择题，包含4-5个选项和1个正确答案。

## 导出格式

- **apkg**: Anki包文件，可直接导入Anki
- **txt**: 制表符分隔的文本文件
- **csv**: CSV格式，兼容Anki导入向导
- **json**: JSON格式，单个JSON数组
- **jsonl**: JSONL格式，每行一个JSON对象

## 项目结构

```
ankigen/
├── __init__.py
├── __main__.py          # CLI入口
├── cli.py              # Typer CLI命令
├── core/
│   ├── parser.py       # 文件解析器
│   ├── llm_engine.py   # LLM集成引擎
│   ├── card_generator.py # 卡片生成逻辑
│   ├── exporter.py    # 导出模块
│   └── config_loader.py # 配置加载
├── models/
│   ├── card.py         # 卡片数据模型
│   └── config.py       # 配置模型
├── templates/
│   ├── basic.j2        # Basic卡片模板
│   ├── cloze.j2        # Cloze卡片模板
│   └── mcq.j2          # MCQ卡片模板
├── utils/
│   ├── logger.py       # 日志配置
│   ├── token_counter.py # Token计算
│   └── cache.py        # 缓存管理
└── config/
    └── default.yaml     # 默认配置
```

## 开发

### 运行测试

```bash
pytest tests/
```

### 代码风格

项目使用black和isort进行代码格式化：

```bash
black ankigen/
isort ankigen/
```

## 常见问题

### Q: 如何设置API密钥？

A: 有三种方式：
1. 环境变量（推荐）：`export DEEPSEEK_API_KEY="your_key"`
2. 配置文件：在`config.yaml`中设置`api_key`
3. `.env`文件：创建`.env`文件并设置环境变量

### Q: 支持哪些文件格式？

A: 目前支持`.txt`和`.md`文件。批量处理时会自动识别文件类型。

### Q: 如何自定义提示词？

A: 使用`--prompt`参数或配置文件的`custom_prompt`字段。提示词支持Jinja2模板语法，可以使用`{{content}}`、`{{card_count}}`等变量。

### Q: 生成的卡片质量如何保证？

A: 系统包含以下质量保证机制：
- 自动去重（基于正面内容）
- 完整性验证（检查必填字段）
- LLM响应解析和验证
- 可选的语义相似度检测

## 贡献

欢迎贡献！请查看[CONTRIBUTING.md](CONTRIBUTING.md)了解开发指南。

## 许可证

MIT License

## 作者

AnkiGen Team
