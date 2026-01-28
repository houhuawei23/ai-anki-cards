"""
配置加载模块

支持从YAML文件和环境变量加载配置，并提供配置合并功能。

配置优先级（从低到高）：
1. 默认配置 (ankigen/config/default.yaml)
2. 用户配置文件 (.config.yml)
3. 环境变量
4. 命令行参数（在CLI中处理）
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from loguru import logger

from ankigen.models.config import AppConfig


def load_env_file(env_path: Optional[Path] = None) -> None:
    """
    加载环境变量文件

    Args:
        env_path: .env文件路径，如果为None则自动查找
    """
    if env_path:
        load_dotenv(env_path)
    else:
        # 自动查找项目根目录的.env文件
        current_dir = Path(__file__).parent.parent.parent
        env_file = current_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        else:
            # 尝试加载用户主目录的.env文件
            home_env = Path.home() / ".ankigen" / ".env"
            if home_env.exists():
                load_dotenv(home_env)


def resolve_env_vars(value: Any) -> Any:
    """
    解析环境变量引用

    支持 ${VAR_NAME} 格式的环境变量引用。

    Args:
        value: 可能包含环境变量引用的值

    Returns:
        解析后的值
    """
    if isinstance(value, str):
        # 匹配 ${VAR_NAME} 格式
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)

        if matches:
            for var_name in matches:
                env_value = os.getenv(var_name)
                if env_value:
                    value = value.replace(f"${{{var_name}}}", env_value)
                else:
                    logger.warning(f"环境变量 {var_name} 未设置")

        return value
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    else:
        return value


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """
    从YAML文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
        yaml.YAMLError: YAML解析错误
    """
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config_dict = yaml.safe_load(f)

    if not config_dict:
        return {}

    # 解析环境变量引用
    config_dict = resolve_env_vars(config_dict)

    return config_dict


def get_default_config_path() -> Path:
    """
    获取默认配置文件路径

    Returns:
        默认配置文件路径
    """
    return Path(__file__).parent.parent / "config" / "default.yaml"


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    查找项目根目录

    通过查找包含 .git、setup.py、pyproject.toml 或 README.md 的目录来确定项目根目录。
    如果找不到，则返回当前工作目录。

    Args:
        start_path: 起始搜索路径，如果为None则从当前文件所在目录开始

    Returns:
        项目根目录路径，如果找不到则返回None
    """
    if start_path is None:
        start_path = Path(__file__).parent.parent.parent

    current = Path(start_path).resolve()

    # 查找包含项目标识文件的目录
    markers = [".git", "setup.py", "pyproject.toml", "README.md", "README.rst"]

    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    # 如果找不到，返回起始目录
    return Path(start_path).resolve()


def find_user_config_file() -> Optional[Path]:
    """
    查找用户配置文件 .config.yml

    在项目主目录下查找 .config.yml 文件。

    Returns:
        配置文件路径，如果不存在则返回None
    """
    project_root = find_project_root()
    if project_root:
        config_file = project_root / ".config.yml"
        if config_file.exists():
            return config_file
    return None


def validate_config(config_dict: Dict[str, Any]) -> List[str]:
    """
    验证配置参数并返回警告列表

    Args:
        config_dict: 配置字典

    Returns:
        警告信息列表
    """
    warnings = []

    # 验证 LLM 配置
    if "llm" in config_dict:
        llm = config_dict["llm"]
        if "temperature" in llm:
            temp = llm["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
                warnings.append(f"LLM temperature 值 {temp} 超出有效范围 [0, 2]，将被限制")
        if "max_tokens" in llm:
            tokens = llm["max_tokens"]
            if not isinstance(tokens, int) or tokens < 1:
                warnings.append(f"LLM max_tokens 值 {tokens} 无效，必须 >= 1")
        if "timeout" in llm:
            timeout = llm["timeout"]
            if not isinstance(timeout, int) or timeout < 1:
                warnings.append(f"LLM timeout 值 {timeout} 无效，必须 >= 1")

    # 验证生成配置
    if "generation" in config_dict:
        gen = config_dict["generation"]
        if "card_type" in gen:
            valid_types = ["basic", "cloze", "mcq"]
            if gen["card_type"].lower() not in valid_types:
                warnings.append(
                    f"card_type '{gen['card_type']}' 无效，必须是以下之一: {valid_types}"
                )
        if "difficulty" in gen:
            valid_difficulties = ["easy", "medium", "hard"]
            if gen["difficulty"].lower() not in valid_difficulties:
                warnings.append(
                    f"difficulty '{gen['difficulty']}' 无效，必须是以下之一: {valid_difficulties}"
                )
        if "chunk_size" in gen:
            chunk_size = gen["chunk_size"]
            if not isinstance(chunk_size, int) or chunk_size < 1:
                warnings.append(f"chunk_size 值 {chunk_size} 无效，必须 >= 1")
        if "max_cards_per_request" in gen:
            max_cards = gen["max_cards_per_request"]
            if not isinstance(max_cards, int) or max_cards < 1:
                warnings.append(f"max_cards_per_request 值 {max_cards} 无效，必须 >= 1")
        if "max_concurrent_requests" in gen:
            max_concurrent = gen["max_concurrent_requests"]
            if not isinstance(max_concurrent, int) or max_concurrent < 1:
                warnings.append(f"max_concurrent_requests 值 {max_concurrent} 无效，必须 >= 1")

    # 验证导出配置
    if "export" in config_dict:
        exp = config_dict["export"]
        if "format" in exp:
            valid_formats = ["apkg", "txt", "csv", "json", "jsonl"]
            if exp["format"].lower() not in valid_formats:
                warnings.append(
                    f"export format '{exp['format']}' 无效，必须是以下之一: {valid_formats}"
                )

    return warnings


def load_config(
    config_path: Optional[Path] = None,
    env_file: Optional[Path] = None,
) -> AppConfig:
    """
    加载应用配置

    配置优先级（从低到高）：
    1. 默认配置 (ankigen/config/default.yaml)
    2. 用户配置文件 (.config.yml，如果存在)
    3. 命令行指定的配置文件 (config_path)
    4. 环境变量
    5. 命令行参数（在CLI中处理）

    Args:
        config_path: 命令行指定的配置文件路径，如果为None则自动查找
        env_file: 环境变量文件路径

    Returns:
        应用配置对象
    """
    # 加载环境变量
    load_env_file(env_file)

    # 1. 加载默认配置
    default_config_path = get_default_config_path()
    if default_config_path.exists():
        default_config = load_yaml_config(default_config_path)
        logger.debug(f"已加载默认配置: {default_config_path}")
    else:
        default_config = {}
        logger.warning("默认配置文件不存在，使用空配置")

    # 2. 加载用户配置文件 .config.yml（如果存在且未通过命令行指定）
    user_config_file = None
    if not config_path:
        user_config_file = find_user_config_file()
        if user_config_file:
            logger.info(f"发现用户配置文件: {user_config_file}")

    # 3. 合并配置：默认配置 < .config.yml < 命令行指定的配置文件
    merged_config = default_config.copy()

    # 先合并 .config.yml（如果存在）
    if user_config_file:
        try:
            user_config = load_yaml_config(user_config_file)
            merged_config = _merge_dicts(merged_config, user_config)
            logger.debug(f"已合并用户配置文件: {user_config_file}")
        except Exception as e:
            logger.warning(f"加载用户配置文件失败: {e}")

    # 再合并命令行指定的配置文件（优先级更高）
    if config_path:
        if config_path.exists():
            try:
                cmd_config = load_yaml_config(config_path)
                merged_config = _merge_dicts(merged_config, cmd_config)
                logger.debug(f"已合并命令行指定的配置文件: {config_path}")
            except Exception as e:
                logger.warning(f"加载命令行指定的配置文件失败: {e}")
        else:
            logger.warning(f"命令行指定的配置文件不存在: {config_path}")

    # 4. 从环境变量覆盖配置
    env_config = _load_from_env()
    if env_config:
        merged_config = _merge_dicts(merged_config, env_config)
        logger.debug("已合并环境变量配置")

    # 5. 验证配置并显示警告
    warnings = validate_config(merged_config)
    if warnings:
        logger.warning("配置验证发现以下问题：")
        for warning in warnings:
            logger.warning(f"  - {warning}")

    # 创建配置对象
    try:
        app_config = AppConfig.from_dict(merged_config)
        return app_config
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        logger.error("请检查配置文件格式是否正确，或使用 --config 参数指定正确的配置文件")
        # 返回默认配置
        return AppConfig()


def _load_from_env() -> Dict[str, Any]:
    """
    从环境变量加载配置

    支持的环境变量：
    - LLM相关: DEEPSEEK_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY,
               LLM_PROVIDER, LLM_MODEL_NAME, LLM_BASE_URL, LLM_TEMPERATURE, LLM_MAX_TOKENS
    - 生成相关: GEN_CARD_TYPE, GEN_CARD_COUNT, GEN_DIFFICULTY,
               GEN_MAX_CARDS_PER_REQUEST, GEN_MAX_CONCURRENT_REQUESTS
    - 导出相关: EXPORT_FORMAT, EXPORT_DECK_NAME

    Returns:
        配置字典
    """
    config = {}

    # LLM配置
    llm_config = {}
    # API密钥（优先级：DEEPSEEK > OPENAI > ANTHROPIC）
    if os.getenv("DEEPSEEK_API_KEY"):
        llm_config["provider"] = "deepseek"
        llm_config["api_key"] = os.getenv("DEEPSEEK_API_KEY")
    elif os.getenv("OPENAI_API_KEY"):
        llm_config["provider"] = "openai"
        llm_config["api_key"] = os.getenv("OPENAI_API_KEY")
    elif os.getenv("ANTHROPIC_API_KEY"):
        llm_config["provider"] = "anthropic"
        llm_config["api_key"] = os.getenv("ANTHROPIC_API_KEY")

    # 显式指定provider（优先级高于API密钥推断）
    if os.getenv("LLM_PROVIDER"):
        llm_config["provider"] = os.getenv("LLM_PROVIDER").lower()

    if os.getenv("LLM_MODEL_NAME"):
        llm_config["model_name"] = os.getenv("LLM_MODEL_NAME")
    if os.getenv("LLM_BASE_URL"):
        llm_config["base_url"] = os.getenv("LLM_BASE_URL")
    if os.getenv("LLM_TEMPERATURE"):
        try:
            llm_config["temperature"] = float(os.getenv("LLM_TEMPERATURE"))
        except ValueError:
            logger.warning(f"无效的 LLM_TEMPERATURE 值: {os.getenv('LLM_TEMPERATURE')}")
    if os.getenv("LLM_MAX_TOKENS"):
        try:
            llm_config["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS"))
        except ValueError:
            logger.warning(f"无效的 LLM_MAX_TOKENS 值: {os.getenv('LLM_MAX_TOKENS')}")

    if llm_config:
        config["llm"] = llm_config

    # 生成配置
    generation_config = {}
    if os.getenv("GEN_CARD_TYPE"):
        generation_config["card_type"] = os.getenv("GEN_CARD_TYPE")
    if os.getenv("GEN_CARD_COUNT"):
        try:
            generation_config["card_count"] = int(os.getenv("GEN_CARD_COUNT"))
        except ValueError:
            logger.warning(f"无效的 GEN_CARD_COUNT 值: {os.getenv('GEN_CARD_COUNT')}")
    if os.getenv("GEN_DIFFICULTY"):
        generation_config["difficulty"] = os.getenv("GEN_DIFFICULTY")
    if os.getenv("GEN_MAX_CARDS_PER_REQUEST"):
        try:
            generation_config["max_cards_per_request"] = int(os.getenv("GEN_MAX_CARDS_PER_REQUEST"))
        except ValueError:
            logger.warning(
                f"无效的 GEN_MAX_CARDS_PER_REQUEST 值: {os.getenv('GEN_MAX_CARDS_PER_REQUEST')}"
            )
    if os.getenv("GEN_MAX_CONCURRENT_REQUESTS"):
        try:
            generation_config["max_concurrent_requests"] = int(
                os.getenv("GEN_MAX_CONCURRENT_REQUESTS")
            )
        except ValueError:
            logger.warning(
                f"无效的 GEN_MAX_CONCURRENT_REQUESTS 值: {os.getenv('GEN_MAX_CONCURRENT_REQUESTS')}"
            )

    if generation_config:
        config["generation"] = generation_config

    # 导出配置
    export_config = {}
    if os.getenv("EXPORT_FORMAT"):
        export_config["format"] = os.getenv("EXPORT_FORMAT")
    if os.getenv("EXPORT_DECK_NAME"):
        export_config["deck_name"] = os.getenv("EXPORT_DECK_NAME")

    if export_config:
        config["export"] = export_config

    return config


def _merge_dicts(base: Dict, override: Dict) -> Dict:
    """
    深度合并两个字典

    Args:
        base: 基础字典
        override: 覆盖字典

    Returns:
        合并后的字典
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def save_config(config: AppConfig, config_path: Path) -> None:
    """
    保存配置到YAML文件

    Args:
        config: 配置对象
        config_path: 保存路径
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_dict = {
        "llm": config.llm.model_dump(exclude_defaults=True),
        "generation": config.generation.model_dump(exclude_defaults=True),
        "export": config.export.model_dump(exclude_defaults=True),
    }

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

    logger.info(f"配置已保存到: {config_path}")


def load_model_info(model_info_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    加载模型信息配置文件

    Args:
        model_info_path: 模型信息文件路径，如果为None则自动查找项目根目录的model_info.yml

    Returns:
        模型信息字典，如果文件不存在则返回None
    """
    if model_info_path is None:
        # 查找项目根目录的model_info.yml
        project_root = find_project_root()
        if project_root:
            model_info_path = project_root / "model_info.yml"
        else:
            # 如果找不到项目根目录，尝试当前工作目录
            model_info_path = Path.cwd() / "model_info.yml"

    if not model_info_path or not model_info_path.exists():
        logger.debug(f"模型信息文件不存在: {model_info_path}")
        return None

    try:
        config_dict = load_yaml_config(model_info_path)
        logger.debug(f"已加载模型信息: {model_info_path}")
        return config_dict
    except Exception as e:
        logger.warning(f"加载模型信息文件失败: {e}")
        return None
