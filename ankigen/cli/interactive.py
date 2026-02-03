"""
交互式CLI模块

提供交互式命令选择和参数输入功能，使用 questionary 库实现专业的交互体验。
支持菜单式参数编辑、错误恢复、API密钥验证等功能。
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import questionary
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ankigen.core.config_loader import (
    find_project_root,
    find_user_config_file,
    load_config,
    load_model_info,
)
from ankigen.models.config import LLMProvider

console = Console()


# ==================== 验证函数 ====================


def validate_file_path(path_str: str, must_exist: bool = True) -> bool:
    """
    验证文件路径

    Args:
        path_str: 路径字符串
        must_exist: 是否必须存在

    Returns:
        验证通过返回True，否则返回错误消息
    """
    if not path_str or not path_str.strip():
        return "路径不能为空"
    try:
        path = Path(path_str).expanduser().resolve()
        if must_exist and not path.exists():
            return f"文件或目录不存在: {path}"
        return True
    except Exception as e:
        return f"无效的路径: {e}"


def validate_integer(
    value: str, min_value: Optional[int] = None, max_value: Optional[int] = None
) -> bool:
    """
    验证整数输入

    Args:
        value: 输入值
        min_value: 最小值（可选）
        max_value: 最大值（可选）

    Returns:
        验证通过返回True，否则返回错误消息
    """
    if not value.strip():
        return True  # 允许空值（可选参数）
    try:
        num = int(value)
        if min_value is not None and num < min_value:
            return f"值必须 >= {min_value}"
        if max_value is not None and num > max_value:
            return f"值必须 <= {max_value}"
        return True
    except ValueError:
        return "请输入有效的整数"


def validate_card_type(card_type: str) -> bool:
    """验证卡片类型"""
    valid_types = ["basic", "cloze", "mcq"]
    if card_type.lower() not in valid_types:
        return f"卡片类型必须是以下之一: {', '.join(valid_types)}"
    return True


def validate_export_format(format_str: str) -> bool:
    """验证导出格式"""
    valid_formats = ["apkg", "txt", "csv", "json", "jsonl"]
    if format_str.lower() not in valid_formats:
        return f"导出格式必须是以下之一: {', '.join(valid_formats)}"
    return True


def validate_provider(provider: str) -> bool:
    """验证LLM提供商"""
    try:
        LLMProvider(provider.lower())
        return True
    except ValueError:
        valid_providers = [p.value for p in LLMProvider]
        return f"提供商必须是以下之一: {', '.join(valid_providers)}"


# ==================== API密钥验证 ====================


def get_provider_api_key_env_var(provider: str) -> Optional[str]:
    """
    获取提供商对应的环境变量名

    Args:
        provider: 提供商名称

    Returns:
        环境变量名
    """
    env_var_map = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "ollama": "OLLAMA_API_KEY",
    }
    return env_var_map.get(provider.lower())


def get_provider_api_key(provider: str) -> Optional[str]:
    """
    获取提供商的API密钥（从环境变量或配置文件）

    Args:
        provider: 提供商名称

    Returns:
        API密钥，如果未配置则返回None
    """
    # 先从环境变量获取
    env_var = get_provider_api_key_env_var(provider)
    if env_var:
        api_key = os.getenv(env_var)
        if api_key:
            return api_key

    # 从配置文件获取
    try:
        app_config = load_config()
        if app_config.llm.provider.value == provider.lower():
            return app_config.llm.get_api_key()
    except Exception:
        pass

    return None


def get_configured_providers() -> Dict[str, bool]:
    """
    获取所有提供商的API密钥配置状态

    Returns:
        字典，键为提供商名称，值为是否已配置
    """
    providers_status = {}
    for provider in ["openai", "deepseek", "anthropic", "ollama", "custom"]:
        api_key = get_provider_api_key(provider)
        providers_status[provider] = api_key is not None and api_key.strip() != ""
    return providers_status


def get_provider_status(provider: str) -> Tuple[bool, Optional[str]]:
    """
    获取提供商配置状态

    Args:
        provider: 提供商名称

    Returns:
        (是否已配置, API密钥)
    """
    api_key = get_provider_api_key(provider)
    is_configured = api_key is not None and api_key.strip() != ""
    return is_configured, api_key


def validate_api_key_for_provider(provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
    """
    验证API密钥是否有效

    Args:
        provider: 提供商名称
        api_key: API密钥

    Returns:
        (是否有效, 错误消息)
    """
    if not api_key or not api_key.strip():
        return False, "API密钥不能为空"

    try:
        # 对于不同提供商，使用不同的验证方法
        # 这里我们只做基本检查，实际验证在运行时进行
        # 如果密钥格式明显错误，可以提前发现
        if provider.lower() == "openai" and not api_key.startswith("sk-"):
            return False, "OpenAI API密钥格式不正确（应以sk-开头）"
        if provider.lower() == "anthropic" and not api_key.startswith("sk-ant-"):
            return False, "Anthropic API密钥格式不正确（应以sk-ant-开头）"

        # 对于其他提供商，格式检查较难，返回True
        # 实际有效性在运行时验证
        return True, None

    except Exception as e:
        return False, f"验证API密钥时出错: {e}"


# ==================== 模型选择 ====================


def get_available_models(provider: str) -> List[str]:
    """
    从providers.yml加载指定提供商的可用模型列表

    Args:
        provider: 提供商名称

    Returns:
        模型名称列表
    """
    try:
        model_info = load_model_info()
        if model_info:
            # 处理providers.yml格式
            if "providers" in model_info:
                providers = model_info.get("providers", {})
                provider_config = providers.get(provider.lower(), {})
                models = provider_config.get("models", [])
                model_names = []
                for m in models:
                    if isinstance(m, dict):
                        name = m.get("name")
                        if name:
                            model_names.append(name)
                    elif isinstance(m, str):
                        model_names.append(m)
                return model_names

            # 处理旧的model_info.yml格式
            if "models" in model_info:
                models = model_info.get("models", {})
                # 返回所有模型名称（可能需要根据提供商过滤）
                return list(models.keys())
    except Exception as e:
        logger.debug(f"加载模型列表失败: {e}")

    # 返回默认模型列表
    default_models = {
        "openai": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        "deepseek": ["deepseek-chat", "deepseek-coder"],
        "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
        "ollama": ["llama3", "mistral", "codellama"],
    }
    return default_models.get(provider.lower(), [])


def select_model_name(provider: str, default: str) -> Optional[str]:
    """
    选择模型名称：从列表选择或自定义输入

    Args:
        provider: 提供商名称
        default: 默认模型名称

    Returns:
        选择的模型名称，如果取消则返回None
    """
    try:
        available_models = get_available_models(provider)
        choices = []

        # 添加可用模型选项
        if available_models:
            choices.append(questionary.Separator("--- 从列表选择 ---"))
            for model in available_models:
                label = model
                if model == default:
                    label = f"{model} (默认)"
                choices.append(questionary.Choice(label, model))
            choices.append(questionary.Separator("--- 自定义输入 ---"))

        # 添加自定义输入选项
        choices.append(questionary.Choice("自定义输入", "__custom__"))

        selected = questionary.select(
            f"选择模型名称 (当前: {default}):",
            choices=choices,
            default=default if default in available_models else None,
        ).ask()

        if selected is None:
            return None

        if selected == "__custom__":
            # 自定义输入
            custom_model = questionary.text(
                "请输入模型名称:",
                default=default,
            ).ask()
            return custom_model if custom_model else default

        return selected

    except KeyboardInterrupt:
        return None
    except Exception as e:
        logger.debug(f"选择模型名称时出错: {e}")
        # 出错时使用默认值
        return default


# ==================== 配置文件 ====================


def get_default_config_path() -> Path:
    """
    获取默认配置文件路径

    Returns:
        默认配置文件路径
    """
    # 1. 查找 .config.yml
    user_config = find_user_config_file()
    if user_config:
        return user_config

    # 2. 项目根目录的 config.yaml
    project_root = find_project_root()
    if project_root:
        config_path = project_root / "config.yaml"
        if config_path.exists():
            return config_path

    # 3. 当前目录的 config.yaml
    return Path("config.yaml")


def show_config_file_content(config_path: Path) -> None:
    """
    显示配置文件内容

    Args:
        config_path: 配置文件路径
    """
    try:
        if not config_path.exists():
            console.print(f"[yellow]配置文件不存在: {config_path}[/yellow]")
            return

        console.print(f"\n[bold cyan]配置文件内容: {config_path}[/bold cyan]")
        console.print("=" * 60)
        with open(config_path, encoding="utf-8") as f:
            content = f.read()
            console.print(content)
        console.print("=" * 60 + "\n")

    except Exception as e:
        console.print(f"[red]读取配置文件失败: {e}[/red]")


# ==================== 错误处理 ====================


def show_error_info(error: Exception, log_file_path: Optional[str] = None) -> None:
    """
    显示错误信息和日志位置

    Args:
        error: 异常对象
        log_file_path: 日志文件路径（可选）
    """
    console.print("\n" + "=" * 60)
    console.print("[bold red]执行出错[/bold red]")
    console.print("=" * 60)
    console.print(f"[red]错误类型:[/red] {type(error).__name__}")
    console.print(f"[red]错误信息:[/red] {error!s}")

    if log_file_path:
        console.print(f"\n[yellow]详细日志已保存到:[/yellow] {log_file_path}")
    else:
        console.print("\n[yellow]请查看日志文件以获取详细错误信息[/yellow]")

    console.print("=" * 60 + "\n")


def handle_command_error(error: Exception, command: str, params: Dict[str, Any]) -> str:
    """
    处理命令执行错误，提供恢复选项

    Args:
        error: 异常对象
        command: 命令名称
        params: 参数字典

    Returns:
        用户选择的操作: 'retry', 'edit', 'back', 'exit'
    """
    logger.exception(f"执行 {command} 命令时出错")

    # 尝试获取日志文件路径（从loguru的handlers中查找）
    log_file_path = None
    try:
        # loguru的handlers包含文件路径信息
        for handler in logger._core.handlers.values():
            if hasattr(handler, "_sink") and isinstance(handler._sink, (str, Path)):
                log_file_path = str(handler._sink)
                break
    except Exception:
        pass

    show_error_info(error, log_file_path)

    try:
        choice = questionary.select(
            "请选择操作:",
            choices=[
                questionary.Choice("重试执行", "retry"),
                questionary.Choice("修改参数", "edit"),
                questionary.Choice("返回主菜单", "back"),
                questionary.Choice("退出程序", "exit"),
            ],
        ).ask()

        return choice if choice else "back"

    except KeyboardInterrupt:
        return "back"


# ==================== 菜单系统 ====================


def format_param_value(key: str, value: Any, default_config: Dict[str, Any]) -> str:
    """
    格式化参数值用于显示

    Args:
        key: 参数键
        value: 参数值
        default_config: 默认配置

    Returns:
        格式化后的字符串
    """
    if value is None:
        default_val = default_config.get(key, "")
        if default_val:
            return f"(默认: {default_val})"
        return "(未设置)"

    if isinstance(value, Path):
        return str(value)
    elif isinstance(value, bool):
        return "是" if value else "否"
    else:
        return str(value)


def show_params_menu(command: str, params: Dict[str, Any], default_config: Dict[str, Any]) -> None:
    """
    显示参数菜单

    Args:
        command: 命令名称
        params: 参数字典
        default_config: 默认配置
    """
    console.print("\n" + "=" * 60)
    console.print(f"[bold cyan]当前参数设置 - {command}[/bold cyan]")
    console.print("=" * 60)

    if command == "generate":
        param_labels = {
            "input": "输入文件或目录路径",
            "output": "输出文件路径",
            "card_type": "卡片类型",
            "num_cards": "卡片数量",
            "provider": "LLM提供商",
            "model_name": "模型名称",
            "config": "配置文件路径",
            "prompt": "自定义提示词",
            "export_format": "导出格式",
            "deck_name": "牌组名称",
            "dry_run": "预览模式",
            "verbose": "显示详细日志",
            "all_formats": "导出所有格式",
            "tags_file": "标签文件路径",
            "show_prompt": "显示提示词",
        }
    elif command == "config":
        param_labels = {
            "init": "初始化配置文件",
            "show": "显示配置",
            "config_path": "配置文件路径",
        }
    elif command == "convert":
        param_labels = {
            "input": "输入文件路径",
            "output": "输出文件路径",
            "card_type": "卡片类型",
            "template": "模板名称",
            "deck_name": "牌组名称",
            "verbose": "显示详细日志",
        }
    else:
        param_labels = {}

    for i, (key, label) in enumerate(param_labels.items(), 1):
        value = params.get(key)
        formatted_value = format_param_value(key, value, default_config)

        # 特殊处理：显示提供商状态
        if key == "provider" and value:
            status, _ = get_provider_status(value)
            status_mark = "✓" if status else "✗"
            formatted_value = f"{value} {status_mark}"

        console.print(f"  [{i}] {label}: {formatted_value}")

    console.print("=" * 60 + "\n")


def edit_single_param(
    command: str,
    param_key: str,
    current_value: Any,
    default_config: Dict[str, Any],
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    编辑单个参数

    Args:
        command: 命令名称
        param_key: 参数键
        current_value: 当前值
        default_config: 默认配置

    Returns:
        新值，如果取消则返回None
    """
    try:
        if command == "generate":
            if param_key == "input":
                value = questionary.path(
                    "输入文件或目录路径:",
                    default=str(current_value) if current_value else "",
                    validate=lambda x: validate_file_path(x, must_exist=True),
                ).ask()
                return Path(value) if value else None

            elif param_key == "output":
                value = questionary.path(
                    "输出文件路径:",
                    default=str(current_value) if current_value else "./output/",
                    validate=lambda x: validate_file_path(x, must_exist=False),
                ).ask()
                return Path(value) if value else None

            elif param_key == "card_type":
                value = questionary.select(
                    "卡片类型:",
                    choices=["basic", "cloze", "mcq"],
                    default=str(current_value)
                    if current_value
                    else default_config.get("card_type", "basic"),
                ).ask()
                return value

            elif param_key == "num_cards":
                value = questionary.text(
                    "卡片数量（留空则自动估算）:",
                    default=str(current_value) if current_value else "",
                    validate=lambda x: validate_integer(x, min_value=1) if x.strip() else True,
                ).ask()
                return int(value) if value and value.strip() else None

            elif param_key == "provider":
                # 提供商选择和API密钥配置子菜单
                current_provider = (
                    current_value if current_value else default_config.get("provider", "deepseek")
                )

                while True:
                    # 获取提供商状态
                    providers_status = get_configured_providers()
                    choices = []

                    # 添加提供商选择选项
                    choices.append(questionary.Separator("--- 选择提供商 ---"))
                    for provider in ["openai", "deepseek", "anthropic", "ollama", "custom"]:
                        status = providers_status.get(provider, False)
                        status_mark = "✓" if status else "✗"
                        label = f"{provider} {status_mark}"
                        choices.append(questionary.Choice(label, provider))

                    # 添加API密钥管理选项
                    choices.append(questionary.Separator("--- API密钥管理 ---"))
                    choices.append(
                        questionary.Choice("[配置] 配置API密钥（选择提供商）", "__config_api_key__")
                    )
                    if current_provider:
                        is_configured, _ = get_provider_status(current_provider)
                        choices.append(
                            questionary.Choice(
                                f"[查看] 查看 {current_provider} 的API密钥状态", "__view_api_key__"
                            )
                        )

                    choices.append(questionary.Separator())
                    choices.append(questionary.Choice("[确认] 确认选择", "__confirm__"))
                    choices.append(questionary.Choice("[返回] 返回上一级", "__back__"))

                    selected = questionary.select(
                        f"LLM提供商管理 (当前: {current_provider}):",
                        choices=choices,
                        default=current_provider
                        if current_provider in [p.value for p in LLMProvider]
                        else None,
                    ).ask()

                    if selected is None:
                        return current_value

                    if selected == "__back__":
                        return current_value

                    if selected == "__confirm__":
                        # 确认当前选择
                        if current_provider:
                            # 检查API密钥
                            is_configured, api_key = get_provider_status(current_provider)
                            if not is_configured:
                                console.print(
                                    f"[yellow]警告: {current_provider} 的API密钥未配置[/yellow]"
                                )
                                if questionary.confirm("是否现在配置API密钥?", default=True).ask():
                                    new_key = questionary.password("请输入API密钥:").ask()
                                    if new_key:
                                        # 验证密钥
                                        is_valid, error_msg = validate_api_key_for_provider(
                                            current_provider, new_key
                                        )
                                        if is_valid:
                                            # 设置环境变量（临时，仅本次会话有效）
                                            env_var = get_provider_api_key_env_var(current_provider)
                                            if env_var:
                                                os.environ[env_var] = new_key
                                                console.print(
                                                    f"[green]✓ {current_provider} 的API密钥已设置[/green]"
                                                )
                                        else:
                                            console.print(
                                                f"[red]✗ API密钥验证失败: {error_msg}[/red]"
                                            )
                                            if not questionary.confirm(
                                                "是否继续使用此密钥?", default=False
                                            ).ask():
                                                continue  # 继续循环
                        return current_provider

                    if selected == "__config_api_key__":
                        # 选择要配置的提供商
                        provider_choices = []
                        for provider in ["openai", "deepseek", "anthropic", "ollama", "custom"]:
                            status = providers_status.get(provider, False)
                            status_mark = "✓" if status else "✗"
                            label = f"{provider} {status_mark}"
                            provider_choices.append(questionary.Choice(label, provider))

                        provider_to_config = questionary.select(
                            "选择要配置API密钥的提供商:",
                            choices=provider_choices,
                        ).ask()

                        if provider_to_config:
                            new_key = questionary.password(
                                f"请输入 {provider_to_config} 的API密钥:"
                            ).ask()
                            if new_key:
                                # 验证密钥
                                is_valid, error_msg = validate_api_key_for_provider(
                                    provider_to_config, new_key
                                )
                                if is_valid:
                                    # 设置环境变量（临时，仅本次会话有效）
                                    env_var = get_provider_api_key_env_var(provider_to_config)
                                    if env_var:
                                        os.environ[env_var] = new_key
                                        console.print(
                                            f"[green]✓ {provider_to_config} 的API密钥已设置[/green]"
                                        )
                                        # 如果配置的是当前提供商，更新状态
                                        if provider_to_config == current_provider:
                                            # 刷新状态显示
                                            pass
                                else:
                                    console.print(f"[red]✗ API密钥验证失败: {error_msg}[/red]")
                                    if not questionary.confirm(
                                        "是否继续使用此密钥?", default=False
                                    ).ask():
                                        continue
                        continue

                    if selected == "__view_api_key__":
                        # 查看API密钥状态
                        is_configured, api_key = get_provider_status(current_provider)
                        console.print(f"\n[bold cyan]{current_provider} API密钥状态[/bold cyan]")
                        console.print("=" * 60)
                        if is_configured:
                            # 只显示部分密钥（保护隐私）
                            masked_key = (
                                api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
                            )
                            console.print("[green]状态:[/green] 已配置")
                            console.print(f"[green]密钥:[/green] {masked_key}")
                            env_var = get_provider_api_key_env_var(current_provider)
                            if env_var:
                                console.print(f"[green]环境变量:[/green] {env_var}")
                        else:
                            console.print("[red]状态:[/red] 未配置")
                            env_var = get_provider_api_key_env_var(current_provider)
                            if env_var:
                                console.print(f"[yellow]环境变量:[/yellow] {env_var} (未设置)")
                        console.print("=" * 60 + "\n")
                        questionary.confirm("按 Enter 继续...", default=True).ask()
                        continue

                    # 选择了新的提供商
                    new_provider = selected
                    if new_provider:
                        # 更新当前提供商
                        current_provider = new_provider
                        # 检查API密钥
                        is_configured, api_key = get_provider_status(new_provider)
                        if not is_configured:
                            console.print(f"[yellow]警告: {new_provider} 的API密钥未配置[/yellow]")
                            if questionary.confirm("是否现在配置API密钥?", default=True).ask():
                                new_key = questionary.password("请输入API密钥:").ask()
                                if new_key:
                                    # 验证密钥
                                    is_valid, error_msg = validate_api_key_for_provider(
                                        new_provider, new_key
                                    )
                                    if is_valid:
                                        # 设置环境变量（临时，仅本次会话有效）
                                        env_var = get_provider_api_key_env_var(new_provider)
                                        if env_var:
                                            os.environ[env_var] = new_key
                                            console.print(
                                                f"[green]✓ {new_provider} 的API密钥已设置[/green]"
                                            )
                                    else:
                                        console.print(f"[red]✗ API密钥验证失败: {error_msg}[/red]")
                                        if not questionary.confirm(
                                            "是否继续使用此密钥?", default=False
                                        ).ask():
                                            # 不更新提供商，继续循环
                                            current_provider = (
                                                current_value
                                                if current_value
                                                else default_config.get("provider", "deepseek")
                                            )
                                            continue
                        # 继续循环，显示更新后的菜单
                        continue

            elif param_key == "model_name":
                # 获取当前选择的provider
                provider = (
                    params.get("provider") if params else default_config.get("provider", "deepseek")
                )
                if not provider:
                    provider = default_config.get("provider", "deepseek")
                return select_model_name(
                    provider,
                    str(current_value)
                    if current_value
                    else default_config.get("model_name", "deepseek-chat"),
                )

            elif param_key == "config":
                default_path = get_default_config_path()
                value = questionary.path(
                    "配置文件路径（可选，留空跳过）:",
                    default=str(current_value) if current_value else str(default_path),
                    validate=lambda x: validate_file_path(x, must_exist=True)
                    if x.strip()
                    else True,
                ).ask()

                if value and questionary.confirm("是否查看配置文件内容?", default=False).ask():
                    show_config_file_content(Path(value))

                return Path(value) if value and value.strip() else None

            elif param_key == "prompt":
                value = questionary.text(
                    "自定义提示词（可选，留空跳过）:",
                    default=str(current_value) if current_value else "",
                ).ask()
                return value if value and value.strip() else None

            elif param_key == "export_format":
                value = questionary.select(
                    "导出格式:",
                    choices=["apkg", "txt", "csv", "json", "jsonl"],
                    default=str(current_value)
                    if current_value
                    else default_config.get("export_format", "apkg"),
                ).ask()
                return value

            elif param_key == "deck_name":
                value = questionary.text(
                    "牌组名称（可选，留空使用默认值）:",
                    default=str(current_value)
                    if current_value
                    else default_config.get("deck_name", ""),
                ).ask()
                return value if value and value.strip() else None

            elif param_key in ["dry_run", "verbose", "all_formats", "show_prompt"]:
                value = questionary.confirm(
                    f"{'启用' if not current_value else '禁用'} {param_key}?",
                    default=bool(current_value),
                ).ask()
                return value

            elif param_key == "tags_file":
                value = questionary.path(
                    "标签文件路径（可选，留空跳过）:",
                    default=str(current_value) if current_value else "",
                    validate=lambda x: validate_file_path(x, must_exist=True)
                    if x.strip()
                    else True,
                ).ask()
                return Path(value) if value and value.strip() else None

        elif command == "config":
            if param_key == "init":
                return questionary.confirm("初始化配置文件?", default=bool(current_value)).ask()
            elif param_key == "show":
                return questionary.confirm("显示配置?", default=bool(current_value)).ask()
            elif param_key == "config_path":
                value = questionary.path(
                    "配置文件路径:",
                    default=str(current_value) if current_value else str(get_default_config_path()),
                    validate=lambda x: validate_file_path(x, must_exist=False),
                ).ask()
                return Path(value) if value else None

        elif command == "convert":
            if param_key == "input":
                value = questionary.path(
                    "输入文件路径:",
                    default=str(current_value) if current_value else "",
                    validate=lambda x: validate_file_path(x, must_exist=True),
                ).ask()
                return Path(value) if value else None
            elif param_key == "output":
                value = questionary.path(
                    "输出文件路径:",
                    default=str(current_value) if current_value else "",
                    validate=lambda x: validate_file_path(x, must_exist=False),
                ).ask()
                return Path(value) if value else None
            elif param_key == "card_type":
                value = questionary.select(
                    "卡片类型（可选，留空自动判定）:",
                    choices=["auto", "basic", "cloze", "mcq"],
                    default=str(current_value) if current_value else "auto",
                ).ask()
                return None if value == "auto" else value
            elif param_key == "template":
                value = questionary.text(
                    "模板名称（可选，留空跳过）:",
                    default=str(current_value) if current_value else "",
                ).ask()
                return value if value and value.strip() else None
            elif param_key == "deck_name":
                value = questionary.text(
                    "牌组名称（可选，留空跳过）:",
                    default=str(current_value) if current_value else "",
                ).ask()
                return value if value and value.strip() else None
            elif param_key == "verbose":
                return questionary.confirm("显示详细日志?", default=bool(current_value)).ask()

        return current_value

    except KeyboardInterrupt:
        return None
    except Exception as e:
        logger.debug(f"编辑参数 {param_key} 时出错: {e}")
        console.print(f"[yellow]编辑参数时出错: {e}[/yellow]")
        return current_value


def format_menu_choice_label(
    label: str, param_key: str, value: Any, default_config: Dict[str, Any]
) -> str:
    """
    格式化菜单选项标签，包含当前参数值

    Args:
        label: 参数标签
        param_key: 参数键
        value: 参数值
        default_config: 默认配置

    Returns:
        格式化后的标签字符串
    """
    # 格式化值用于显示
    if value is None:
        default_val = default_config.get(param_key, "")
        value_str = f"(默认: {default_val})" if default_val else "(未设置)"
    elif isinstance(value, Path):
        value_str = str(value)
    elif isinstance(value, bool):
        value_str = "是" if value else "否"
    else:
        value_str = str(value)

    # 特殊处理：显示提供商状态
    if param_key == "provider" and value:
        status, _ = get_provider_status(value)
        status_mark = "✓" if status else "✗"
        value_str = f"{value} {status_mark}"

    return f"{label}：{value_str}"


def edit_params_menu(
    command: str, params: Dict[str, Any], default_config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    参数编辑菜单

    Args:
        command: 命令名称
        params: 当前参数字典
        default_config: 默认配置

    Returns:
        更新后的参数字典，如果返回主菜单则返回None
    """
    while True:
        try:
            show_params_menu(command, params, default_config)

            # 构建菜单选项（包含当前值）
            if command == "generate":
                choices = [
                    questionary.Choice(
                        format_menu_choice_label(
                            "[1] 输入文件或目录路径", "input", params.get("input"), default_config
                        ),
                        "input",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[2] 输出文件路径", "output", params.get("output"), default_config
                        ),
                        "output",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[3] 卡片类型", "card_type", params.get("card_type"), default_config
                        ),
                        "card_type",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[4] 卡片数量", "num_cards", params.get("num_cards"), default_config
                        ),
                        "num_cards",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[5] LLM提供商", "provider", params.get("provider"), default_config
                        ),
                        "provider",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[6] 模型名称", "model_name", params.get("model_name"), default_config
                        ),
                        "model_name",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[7] 配置文件路径", "config", params.get("config"), default_config
                        ),
                        "config",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[8] 自定义提示词", "prompt", params.get("prompt"), default_config
                        ),
                        "prompt",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[9] 导出格式",
                            "export_format",
                            params.get("export_format"),
                            default_config,
                        ),
                        "export_format",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[10] 牌组名称", "deck_name", params.get("deck_name"), default_config
                        ),
                        "deck_name",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[11] 预览模式", "dry_run", params.get("dry_run"), default_config
                        ),
                        "dry_run",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[12] 显示详细日志", "verbose", params.get("verbose"), default_config
                        ),
                        "verbose",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[13] 导出所有格式",
                            "all_formats",
                            params.get("all_formats"),
                            default_config,
                        ),
                        "all_formats",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[14] 标签文件路径",
                            "tags_file",
                            params.get("tags_file"),
                            default_config,
                        ),
                        "tags_file",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[15] 显示提示词",
                            "show_prompt",
                            params.get("show_prompt"),
                            default_config,
                        ),
                        "show_prompt",
                    ),
                    questionary.Separator(),
                    questionary.Choice("[0] 返回上一级", "back"),
                    questionary.Choice("[确认] 确认执行", "confirm"),
                ]
            elif command == "config":
                choices = [
                    questionary.Choice(
                        format_menu_choice_label(
                            "[1] 初始化配置文件", "init", params.get("init"), default_config
                        ),
                        "init",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[2] 显示配置", "show", params.get("show"), default_config
                        ),
                        "show",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[3] 配置文件路径",
                            "config_path",
                            params.get("config_path"),
                            default_config,
                        ),
                        "config_path",
                    ),
                    questionary.Separator(),
                    questionary.Choice("[0] 返回上一级", "back"),
                    questionary.Choice("[确认] 确认执行", "confirm"),
                ]
            elif command == "convert":
                choices = [
                    questionary.Choice(
                        format_menu_choice_label(
                            "[1] 输入文件路径", "input", params.get("input"), default_config
                        ),
                        "input",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[2] 输出文件路径", "output", params.get("output"), default_config
                        ),
                        "output",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[3] 卡片类型", "card_type", params.get("card_type"), default_config
                        ),
                        "card_type",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[4] 模板名称", "template", params.get("template"), default_config
                        ),
                        "template",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[5] 牌组名称", "deck_name", params.get("deck_name"), default_config
                        ),
                        "deck_name",
                    ),
                    questionary.Choice(
                        format_menu_choice_label(
                            "[6] 显示详细日志", "verbose", params.get("verbose"), default_config
                        ),
                        "verbose",
                    ),
                    questionary.Separator(),
                    questionary.Choice("[0] 返回上一级", "back"),
                    questionary.Choice("[确认] 确认执行", "confirm"),
                ]
            else:
                choices = [
                    questionary.Choice("[0] 返回上一级", "back"),
                ]

            selected = questionary.select(
                "请选择要修改的参数或操作:",
                choices=choices,
            ).ask()

            if selected is None:
                return None

            if selected == "back":
                return None

            if selected == "confirm":
                return params

            # 编辑选中的参数
            new_value = edit_single_param(
                command, selected, params.get(selected), default_config, params
            )
            if new_value is not None:
                params[selected] = new_value

        except KeyboardInterrupt:
            return None


# ==================== 命令执行 ====================


def execute_generate(**kwargs) -> Tuple[bool, Optional[Exception]]:
    """
    执行 generate 命令

    Args:
        **kwargs: generate 命令的参数

    Returns:
        (是否成功, 异常对象)
    """
    try:
        import importlib

        if "ankigen.cli" in sys.modules:
            cli_module = sys.modules["ankigen.cli"]
        else:
            cli_module = importlib.import_module("ankigen.cli")

        cli_module.generate(**kwargs)
        return True, None
    except Exception as e:
        return False, e


def execute_config(**kwargs) -> Tuple[bool, Optional[Exception]]:
    """
    执行 config 命令

    Args:
        **kwargs: config 命令的参数

    Returns:
        (是否成功, 异常对象)
    """
    try:
        import importlib

        if "ankigen.cli" in sys.modules:
            cli_module = sys.modules["ankigen.cli"]
        else:
            cli_module = importlib.import_module("ankigen.cli")

        cli_module.config(**kwargs)
        return True, None
    except Exception as e:
        return False, e


def execute_convert(**kwargs) -> Tuple[bool, Optional[Exception]]:
    """
    执行 convert 命令

    Args:
        **kwargs: convert 命令的参数

    Returns:
        (是否成功, 异常对象)
    """
    try:
        import importlib

        if "ankigen.cli" in sys.modules:
            cli_module = sys.modules["ankigen.cli"]
        else:
            cli_module = importlib.import_module("ankigen.cli")

        cli_module.convert(**kwargs)
        return True, None
    except Exception as e:
        return False, e


# ==================== 主流程 ====================


def select_command() -> Optional[str]:
    """
    选择要执行的命令

    Returns:
        选择的命令名称，如果用户取消则返回None
    """
    try:
        command = questionary.select(
            "请选择要执行的命令:",
            choices=[
                questionary.Choice("[1] generate - 生成Anki卡片", "generate"),
                questionary.Choice("[2] config - 配置管理", "config"),
                questionary.Choice("[3] convert - 转换卡片格式", "convert"),
                questionary.Choice("[0] exit - 退出", "exit"),
            ],
        ).ask()
        return command
    except KeyboardInterrupt:
        console.print("\n[yellow]操作已取消[/yellow]")
        return None


def get_default_config_for_command(command: str) -> Dict[str, Any]:
    """
    获取命令的默认配置

    Args:
        command: 命令名称

    Returns:
        默认配置字典
    """
    try:
        app_config = load_config()
        if command == "generate":
            return {
                "card_type": app_config.generation.card_type,
                "provider": app_config.llm.provider.value,
                "model_name": app_config.llm.model_name,
                "export_format": app_config.export.format,
                "deck_name": app_config.export.deck_name,
            }
    except Exception:
        pass

    # 返回硬编码默认值
    if command == "generate":
        return {
            "card_type": "basic",
            "provider": "deepseek",
            "model_name": "deepseek-chat",
            "export_format": "apkg",
            "deck_name": "Generated Deck",
        }
    return {}


def interactive_mode() -> None:
    """
    交互式模式主入口（重构版）

    实现循环菜单，支持错误恢复和参数编辑。
    """
    try:
        # 显示欢迎信息
        welcome_text = Text("欢迎使用 AnkiGen 交互式模式", style="bold cyan")
        console.print(Panel(welcome_text, border_style="cyan"))

        while True:
            try:
                # 选择命令
                command = select_command()
                if command is None or command == "exit":
                    console.print("\n[yellow]再见！[/yellow]")
                    break

                # 获取默认配置
                default_config = get_default_config_for_command(command)

                # 初始化参数字典
                if command == "generate":
                    params = {
                        "input": None,
                        "output": Path("./output/"),
                        "card_type": default_config.get("card_type", "basic"),
                        "num_cards": None,
                        "provider": default_config.get("provider", "deepseek"),
                        "model_name": default_config.get("model_name", "deepseek-chat"),
                        "config": None,
                        "prompt": None,
                        "export_format": default_config.get("export_format", "apkg"),
                        "deck_name": default_config.get("deck_name"),
                        "dry_run": False,
                        "verbose": False,
                        "all_formats": False,
                        "tags_file": None,
                        "show_prompt": False,
                    }
                elif command == "config":
                    params = {
                        "init": False,
                        "show": False,
                        "config_path": get_default_config_path(),
                    }
                elif command == "convert":
                    params = {
                        "input": None,
                        "output": None,
                        "card_type": None,
                        "template": None,
                        "deck_name": None,
                        "verbose": False,
                    }
                else:
                    console.print(f"[red]未知命令: {command}[/red]")
                    continue

                # 参数编辑循环
                while True:
                    updated_params = edit_params_menu(command, params.copy(), default_config)
                    if updated_params is None:
                        # 返回主菜单
                        break

                    params = updated_params

                    # 验证必填参数
                    if command == "generate":
                        if not params.get("input"):
                            console.print("[red]错误: 必须设置输入文件路径[/red]")
                            continue
                        if not params.get("output"):
                            console.print("[red]错误: 必须设置输出文件路径[/red]")
                            continue

                    # 执行命令
                    console.print(f"\n[bold green]正在执行 {command} 命令...[/bold green]\n")

                    success = False
                    error = None

                    if command == "generate":
                        success, error = execute_generate(**params)
                    elif command == "config":
                        success, error = execute_config(**params)
                    elif command == "convert":
                        success, error = execute_convert(**params)

                    if success:
                        console.print("\n[bold green]✓ 命令执行完成[/bold green]")
                        # 询问是否继续
                        if questionary.confirm("是否继续使用交互式模式?", default=True).ask():
                            break  # 返回命令选择
                        else:
                            console.print("\n[yellow]再见！[/yellow]")
                            return
                    else:
                        # 处理错误
                        action = handle_command_error(error, command, params)
                        if action == "retry":
                            continue  # 重试
                        elif action == "edit":
                            continue  # 继续编辑参数
                        elif action == "back":
                            break  # 返回主菜单
                        elif action == "exit":
                            console.print("\n[yellow]再见！[/yellow]")
                            return

            except KeyboardInterrupt:
                console.print("\n[yellow]操作已取消[/yellow]")
                if questionary.confirm("是否退出交互式模式?", default=True).ask():
                    console.print("\n[yellow]再见！[/yellow]")
                    break
            except Exception as e:
                logger.exception("交互式模式执行失败")
                console.print(f"\n[bold red]未预期的错误: {e}[/bold red]")
                console.print("[yellow]请查看日志文件以获取详细错误信息[/yellow]")
                if questionary.confirm("是否继续?", default=True).ask():
                    continue
                else:
                    break

    except KeyboardInterrupt:
        console.print("\n[yellow]操作已取消[/yellow]")
        logger.warning("用户中断交互式操作")
    except Exception as e:
        logger.exception("交互式模式执行失败")
        console.print(f"\n[bold red]错误: {e}[/bold red]")
        console.print("[yellow]请查看日志文件以获取详细错误信息[/yellow]")
