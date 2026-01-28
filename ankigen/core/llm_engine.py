"""
LLM集成引擎模块

支持多个LLM提供商，提供统一的接口，包含重试、限流等机制。

此模块现在使用 llm-engine 库作为后端。
"""

from typing import AsyncIterator, Optional, Tuple

from ankigen.models.config import LLMConfig

# Import from llm-engine
try:
    from llm_engine import LLMConfig as LLMEngineConfig
    from llm_engine import LLMProvider
    from llm_engine.engine import (
        CustomProvider,
        DeepSeekProvider,
        OllamaProvider,
        OpenAIProvider,
    )
    from llm_engine.engine import (
        LLMEngine as LLMEngineBase,
    )

    LLM_ENGINE_AVAILABLE = True
except ImportError:
    LLM_ENGINE_AVAILABLE = False
    LLMEngineBase = None
    LLMEngineConfig = None
    LLMProvider = None
    OpenAIProvider = None
    DeepSeekProvider = None
    OllamaProvider = None
    CustomProvider = None

# Re-export Provider classes for backward compatibility
if LLM_ENGINE_AVAILABLE:
    # Import Provider classes from llm-engine
    from llm_engine.engine import (
        CustomProvider,
        DeepSeekProvider,
        OllamaProvider,
        OpenAIProvider,
    )

    __all__ = [
        "CustomProvider",
        "DeepSeekProvider",
        "LLMEngine",
        "OllamaProvider",
        "OpenAIProvider",
    ]
else:
    # Fallback stubs if llm-engine not available
    class OpenAIProvider:
        pass

    class DeepSeekProvider:
        pass

    class OllamaProvider:
        pass

    class CustomProvider:
        pass

    __all__ = [
        "CustomProvider",
        "DeepSeekProvider",
        "LLMEngine",
        "OllamaProvider",
        "OpenAIProvider",
    ]


def _convert_llm_config(config: LLMConfig) -> LLMEngineConfig:
    """
    Convert ankigen LLMConfig to llm-engine LLMConfig.

    Args:
        config: ankigen LLMConfig instance

    Returns:
        llm-engine LLMConfig instance
    """
    if not LLM_ENGINE_AVAILABLE:
        raise ImportError("llm-engine is not installed")

    # Map provider enum
    provider_map = {
        "openai": LLMProvider.OPENAI,
        "deepseek": LLMProvider.DEEPSEEK,
        "ollama": LLMProvider.OLLAMA,
        "custom": LLMProvider.CUSTOM,
    }
    provider_enum = provider_map.get(config.provider.value.lower(), LLMProvider.CUSTOM)

    return LLMEngineConfig(
        provider=provider_enum,
        model_name=config.model_name,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
        presence_penalty=config.presence_penalty,
        frequency_penalty=config.frequency_penalty,
        timeout=config.timeout,
        max_retries=config.max_retries,
        api_keys=config.api_keys if hasattr(config, "api_keys") else [],
    )


class LLMEngine:
    """
    LLM引擎统一接口（适配层）

    根据配置自动选择合适的提供商，并提供统一的调用接口。
    此实现使用 llm-engine 库作为后端。
    """

    def __init__(self, config: LLMConfig):
        """
        初始化LLM引擎

        Args:
            config: LLM配置对象（ankigen.models.config.LLMConfig）
        """
        if not LLM_ENGINE_AVAILABLE:
            raise ImportError(
                "llm-engine is not installed. Please install it with: pip install -e ../llm-engine"
            )

        self.config = config
        # Convert ankigen config to llm-engine config
        llm_engine_config = _convert_llm_config(config)
        # Create llm-engine instance
        self._engine = LLMEngineBase(llm_engine_config)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        生成文本

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            生成的文本
        """
        return await self._engine.generate(prompt, system_prompt)

    async def stream_generate(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> AsyncIterator[Tuple[str, int]]:
        """
        流式生成文本

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Yields:
            (文本片段, 累计token数) 元组
        """
        async for chunk in self._engine.stream_generate(prompt, system_prompt):
            yield chunk

    @property
    def provider(self):
        """Get underlying provider instance (for compatibility)."""
        return self._engine.provider
