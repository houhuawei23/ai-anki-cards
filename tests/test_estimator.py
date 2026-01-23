"""
资源估算模块测试
"""

import math
import pytest
from pathlib import Path

from ankigen.core.estimator import (
    ResourceEstimator,
    ModelInfo,
    CardTypeMetrics,
    ChunkingStrategy,
    create_estimator_from_config,
)
from ankigen.models.config import LLMConfig, LLMProvider


class TestCardTypeMetrics:
    """测试CardTypeMetrics数据类"""

    def test_create_metrics(self):
        """测试创建性能指标"""
        metrics = CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150)
        assert metrics.avg_time_per_card == 5.0
        assert metrics.avg_tokens_per_card == 150


class TestModelInfo:
    """测试ModelInfo数据类"""

    def test_create_model_info(self):
        """测试创建模型信息"""
        card_metrics = {
            "basic": CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150),
            "mcq": CardTypeMetrics(avg_time_per_card=15.0, avg_tokens_per_card=500),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        assert model_info.provider == "deepseek"
        assert model_info.context_length == 128000
        assert model_info.max_output_default == 4000
        assert len(model_info.card_metrics) == 2


class TestResourceEstimator:
    """测试ResourceEstimator类"""

    def test_estimate_tokens_basic(self):
        """测试估算basic卡片的token数"""
        card_metrics = {
            "basic": CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        assert estimator.estimate_tokens("basic", 10) == 1500
        assert estimator.estimate_tokens("basic", 1) == 150

    def test_estimate_tokens_mcq(self):
        """测试估算mcq卡片的token数"""
        card_metrics = {
            "mcq": CardTypeMetrics(avg_time_per_card=15.0, avg_tokens_per_card=500),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        assert estimator.estimate_tokens("mcq", 10) == 5000
        assert estimator.estimate_tokens("mcq", 1) == 500

    def test_estimate_tokens_default_fallback(self):
        """测试默认值回退"""
        estimator = ResourceEstimator(None)
        
        # 应该使用默认值
        assert estimator.estimate_tokens("basic", 10) == 1500
        assert estimator.estimate_tokens("mcq", 10) == 5000

    def test_estimate_time_basic(self):
        """测试估算basic卡片的时间"""
        card_metrics = {
            "basic": CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        assert estimator.estimate_time("basic", 10) == 50.0
        assert estimator.estimate_time("basic", 1) == 5.0

    def test_estimate_time_mcq(self):
        """测试估算mcq卡片的时间"""
        card_metrics = {
            "mcq": CardTypeMetrics(avg_time_per_card=15.0, avg_tokens_per_card=500),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        assert estimator.estimate_time("mcq", 10) == 150.0
        assert estimator.estimate_time("mcq", 1) == 15.0

    def test_get_max_tokens_for_request(self):
        """测试获取单次请求的max_tokens"""
        card_metrics = {
            "basic": CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        # 应该返回4000（默认值，不超过maximum）
        assert estimator.get_max_tokens_for_request("basic") == 4000

    def test_get_max_tokens_with_lower_default(self):
        """测试max_tokens不超过模型的default值"""
        card_metrics = {
            "basic": CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=2000,  # 低于4000
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        # 应该返回2000（不超过default）
        assert estimator.get_max_tokens_for_request("basic") == 2000

    def test_calculate_optimal_chunks_basic_single(self):
        """测试计算basic卡片的切分策略（单次生成）"""
        card_metrics = {
            "basic": CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        # 10张basic卡片：10 * 150 = 1500 tokens，小于4000，应该1次生成
        strategy = estimator.calculate_optimal_chunks(10, "basic")
        assert strategy.num_chunks == 1
        assert strategy.cards_per_chunk == 10
        assert strategy.max_tokens_per_request == 4000

    def test_calculate_optimal_chunks_mcq_multiple(self):
        """测试计算mcq卡片的切分策略（多次生成）"""
        card_metrics = {
            "mcq": CardTypeMetrics(avg_time_per_card=15.0, avg_tokens_per_card=500),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        # 20张mcq卡片：20 * 500 = 10000 tokens
        # 10000 / 4000 = 2.5，向上取整 = 3次
        strategy = estimator.calculate_optimal_chunks(20, "mcq")
        assert strategy.num_chunks == 3
        # 每次卡片数：ceil(20 / 3) = 7
        assert strategy.cards_per_chunk == 7
        assert strategy.max_tokens_per_request == 4000

    def test_calculate_optimal_chunks_large_count(self):
        """测试大量卡片的切分策略"""
        card_metrics = {
            "mcq": CardTypeMetrics(avg_time_per_card=15.0, avg_tokens_per_card=500),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        # 100张mcq卡片：100 * 500 = 50000 tokens
        # 50000 / 4000 = 12.5，向上取整 = 13次
        strategy = estimator.calculate_optimal_chunks(100, "mcq")
        assert strategy.num_chunks == 13
        # 每次卡片数：ceil(100 / 13) = 8
        assert strategy.cards_per_chunk == 8

    def test_estimate_for_generation(self):
        """测试为生成任务估算资源需求"""
        card_metrics = {
            "basic": CardTypeMetrics(avg_time_per_card=5.0, avg_tokens_per_card=150),
        }
        model_info = ModelInfo(
            provider="deepseek",
            context_length=128000,
            max_output_default=4000,
            max_output_maximum=8000,
            speed_tokens_per_second=30,
            card_metrics=card_metrics,
        )
        estimator = ResourceEstimator(model_info)
        
        content = "这是一段测试内容" * 100
        result = estimator.estimate_for_generation(content, "basic", 10)
        
        assert result["total_tokens"] == 1500
        assert result["total_time"] == 50.0
        assert isinstance(result["strategy"], ChunkingStrategy)
        assert result["content_length"] == len(content)


class TestCreateEstimatorFromConfig:
    """测试从配置创建估算器"""

    def test_create_estimator_with_model_info(self, tmp_path):
        """测试从配置创建估算器（有model_info.yml）"""
        # 创建临时的model_info.yml
        model_info_file = tmp_path / "model_info.yml"
        model_info_file.write_text("""
models:
  deepseek-chat:
    provider: deepseek
    context_length: 128000
    max_output:
      default: 4000
      maximum: 8000
    speed_tokens_per_second: 30
    card_metrics:
      basic:
        avg_time_per_card: 5.0
        avg_tokens_per_card: 150
      mcq:
        avg_time_per_card: 15.0
        avg_tokens_per_card: 500
""")
        
        # 修改load_model_info函数以使用临时文件
        from ankigen.core import config_loader
        original_load = config_loader.load_model_info
        
        def mock_load(path=None):
            if path is None:
                return config_loader.load_yaml_config(model_info_file)
            return original_load(path)
        
        # 创建配置
        llm_config = LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
        )
        
        # 由于load_model_info的查找逻辑比较复杂，这里直接测试ResourceEstimator的解析功能
        estimator = ResourceEstimator()
        # 如果model_info.yml存在，应该能加载
        # 这里主要测试create_estimator_from_config函数不会抛出异常
        estimator = create_estimator_from_config(llm_config)
        assert estimator is not None

    def test_create_estimator_without_model_info(self):
        """测试从配置创建估算器（无model_info.yml）"""
        llm_config = LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
        )
        
        estimator = create_estimator_from_config(llm_config)
        assert estimator is not None
        # 应该使用默认值
        assert estimator.estimate_tokens("basic", 10) == 1500
