"""
AnkiGen 自定义异常类模块

定义项目专用的异常类层次结构，提供结构化的错误处理。
"""


class AnkiGenError(Exception):
    """AnkiGen 基础异常类

    所有 AnkiGen 特定异常的基类。
    """


class ConfigurationError(AnkiGenError):
    """配置错误异常

    当配置加载、验证或处理失败时抛出。
    """


class LLMProviderError(AnkiGenError):
    """LLM 提供商错误异常

    当 LLM API 调用失败、认证失败或其他提供商相关错误时抛出。
    """


class CardGenerationError(AnkiGenError):
    """卡片生成错误异常

    当卡片生成过程中发生错误时抛出。
    """


class ParsingError(AnkiGenError):
    """解析错误异常

    当文件解析或内容解析失败时抛出。
    """


class ExportError(AnkiGenError):
    """导出错误异常

    当卡片导出过程中发生错误时抛出。
    """


class TemplateError(AnkiGenError):
    """模板错误异常

    当模板加载、渲染或处理失败时抛出。
    """


class ValidationError(AnkiGenError):
    """验证错误异常

    当数据验证失败时抛出。
    """
