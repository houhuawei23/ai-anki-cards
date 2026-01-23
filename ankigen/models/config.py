"""
配置数据模型

定义LLM配置、生成配置和应用配置的数据结构。
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LLMProvider(str, Enum):
    """LLM提供商枚举"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class LLMConfig(BaseModel):
    """
    LLM配置模型

    包含模型提供商、API密钥、请求参数等配置。
    """

    provider: LLMProvider = Field(default=LLMProvider.DEEPSEEK, description="LLM提供商")
    model_name: str = Field(default="deepseek-chat", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    base_url: Optional[str] = Field(default=None, description="API基础URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(default=2000, ge=1, description="最大token数")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-p采样参数")
    presence_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="存在惩罚参数"
    )
    frequency_penalty: float = Field(
        default=0.0, ge=-2.0, le=2.0, description="频率惩罚参数"
    )
    timeout: int = Field(default=60, ge=1, description="请求超时时间（秒）")
    max_retries: int = Field(default=3, ge=0, description="最大重试次数")
    api_keys: List[str] = Field(
        default_factory=list, description="多个API密钥（用于轮询）"
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """
        验证API密钥

        Args:
            v: API密钥值

        Returns:
            验证后的API密钥
        """
        if v and v.startswith("${") and v.endswith("}"):
            # 环境变量引用，不在这里解析
            return v
        return v

    def get_api_key(self) -> Optional[str]:
        """
        获取有效的API密钥

        优先使用api_keys列表中的第一个，否则使用api_key。

        Returns:
            API密钥字符串
        """
        if self.api_keys:
            return self.api_keys[0]
        return self.api_key


class GenerationConfig(BaseModel):
    """
    生成配置模型

    包含卡片生成相关的参数配置。
    """

    card_type: str = Field(default="basic", description="卡片类型")
    card_count: Optional[int] = Field(default=None, ge=1, description="卡片数量")
    difficulty: str = Field(default="medium", description="难度级别")
    chunk_size: int = Field(default=500, ge=1, description="内容分块大小（字符数）")
    max_tokens_per_chunk: int = Field(
        default=1000, ge=1, description="每个分块的最大token数"
    )
    custom_prompt: Optional[str] = Field(default=None, description="自定义提示词")
    enable_deduplication: bool = Field(
        default=True, description="是否启用去重"
    )
    enable_quality_filter: bool = Field(
        default=True, description="是否启用质量过滤"
    )
    max_cards_per_request: int = Field(
        default=20, ge=1, description="单次API请求最多生成的卡片数量"
    )
    max_concurrent_requests: int = Field(
        default=5, ge=1, description="最大并发请求数（避免过多并发导致API限流）"
    )

    @field_validator("card_type")
    @classmethod
    def validate_card_type(cls, v: str) -> str:
        """
        验证卡片类型

        Args:
            v: 卡片类型字符串

        Returns:
            验证后的卡片类型
        """
        valid_types = ["basic", "cloze", "mcq"]
        if v.lower() not in valid_types:
            raise ValueError(f"card_type必须是以下之一: {valid_types}")
        return v.lower()

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        """
        验证难度级别

        Args:
            v: 难度级别字符串

        Returns:
            验证后的难度级别
        """
        valid_difficulties = ["easy", "medium", "hard"]
        if v.lower() not in valid_difficulties:
            raise ValueError(f"difficulty必须是以下之一: {valid_difficulties}")
        return v.lower()


class ExportConfig(BaseModel):
    """
    导出配置模型

    包含导出相关的参数配置。
    """

    format: str = Field(default="apkg", description="导出格式")
    deck_name: str = Field(default="Generated Deck", description="牌组名称")
    deck_description: str = Field(default="", description="牌组描述")
    include_media: bool = Field(default=False, description="是否包含媒体文件")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """
        验证导出格式

        Args:
            v: 导出格式字符串

        Returns:
            验证后的导出格式
        """
        valid_formats = ["apkg", "txt", "csv", "json", "jsonl"]
        if v.lower() not in valid_formats:
            raise ValueError(f"format必须是以下之一: {valid_formats}")
        return v.lower()


class AppConfig(BaseModel):
    """
    应用主配置模型

    合并LLM配置、生成配置和导出配置。
    """

    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM配置")
    generation: GenerationConfig = Field(
        default_factory=GenerationConfig, description="生成配置"
    )
    export: ExportConfig = Field(default_factory=ExportConfig, description="导出配置")

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """
        从字典创建配置对象

        Args:
            data: 配置字典

        Returns:
            配置对象
        """
        llm_config = LLMConfig(**data.get("llm", {}))
        generation_config = GenerationConfig(**data.get("generation", {}))
        export_config = ExportConfig(**data.get("export", {}))

        return cls(llm=llm_config, generation=generation_config, export=export_config)

    def merge(self, other: "AppConfig") -> "AppConfig":
        """
        合并另一个配置对象

        使用other中的非默认值覆盖当前配置。

        Args:
            other: 要合并的配置对象

        Returns:
            合并后的新配置对象
        """
        merged = self.model_copy(deep=True)

        # 合并LLM配置
        for key, value in other.llm.model_dump(exclude_defaults=True).items():
            setattr(merged.llm, key, value)

        # 合并生成配置
        for key, value in other.generation.model_dump(exclude_defaults=True).items():
            setattr(merged.generation, key, value)

        # 合并导出配置
        for key, value in other.export.model_dump(exclude_defaults=True).items():
            setattr(merged.export, key, value)

        return merged
