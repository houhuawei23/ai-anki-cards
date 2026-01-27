"""
卡片生成器模块

负责调用LLM生成卡片，解析响应，并进行质量过滤和去重。
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, Template
from loguru import logger

from ankigen.core.config_loader import load_model_info
from ankigen.core.llm_engine import LLMEngine
from ankigen.core.template_loader import get_template_dir
from ankigen.core.estimator import create_estimator_from_config
from ankigen.core.tags_loader import load_tags_file
from ankigen.models.card import (
    BasicCard,
    Card,
    CardType,
    ClozeCard,
    MCQCard,
    MCQOption,
)
from ankigen.models.config import GenerationConfig, LLMConfig
from ankigen.utils.cache import FileCache


@dataclass
class GenerationStats:
    """生成统计信息"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_time: float = 0.0
    api_responses: List[str] = field(default_factory=list)  # 保存 API 响应 JSON
    input_cache_hit_tokens: int = 0  # cache hit 的输入 token 数
    prompts: List[str] = field(default_factory=list)  # 保存生成的提示词
    
    @property
    def total_tokens(self) -> int:
        """总 token 数"""
        return self.input_tokens + self.output_tokens
    
    @property
    def avg_time_per_token(self) -> float:
        """平均每 token 用时（秒）"""
        if self.total_tokens == 0:
            return 0.0
        return self.total_time / self.total_tokens
    
    @property
    def tokens_per_second(self) -> float:
        """每秒生成的 token 数"""
        if self.total_time == 0:
            return 0.0
        return self.output_tokens / self.total_time
    
    @property
    def input_cache_miss_tokens(self) -> int:
        """cache miss 的输入 token 数"""
        return self.input_tokens - self.input_cache_hit_tokens


class PromptTemplate:
    """提示词模板管理器"""

    def __init__(self):
        """
        初始化模板管理器
        
        模板现在从 cards_templates 目录下的各个卡片类型目录中加载 prompt.j2
        """
        self.base_dir = Path(__file__).parent.parent / "cards_templates"
        self.env = Environment(
            loader=FileSystemLoader(str(self.base_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        template_name: str,
        content: str,
        card_count: int,
        difficulty: str = "medium",
        custom_prompt: Optional[str] = None,
        basic_tags: Optional[List[str]] = None,
        optional_tags: Optional[List[str]] = None,
    ) -> str:
        """
        渲染模板

        Args:
            template_name: 卡片类型名称（basic/cloze/mcq）
            content: 要生成卡片的内容
            card_count: 卡片数量
            difficulty: 难度级别
            custom_prompt: 自定义提示词，如果提供则覆盖模板

        Returns:
            渲染后的提示词
        """
        if custom_prompt:
            # 使用自定义提示词，但仍需要注入变量
            template = Template(custom_prompt)
            return template.render(
                content=content,
                card_count=card_count,
                difficulty=difficulty,
                basic_tags=basic_tags or [],
                optional_tags=optional_tags or [],
            )

        # 根据卡片类型确定模板目录
        card_type = CardType(template_name)
        template_dir = get_template_dir(card_type)
        
        if not template_dir:
            raise FileNotFoundError(
                f"未找到卡片类型 {template_name} 的模板目录。"
                f"请确保 cards_templates/{template_name}/prompt.j2 文件存在"
            )

        # 加载 prompt.j2 文件
        template_path = template_dir / "prompt.j2"
        if not template_path.exists():
            logger.warning(f"模板文件不存在: {template_path}")
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        # 使用相对路径加载模板
        relative_path = template_path.relative_to(self.base_dir)
        template = self.env.get_template(str(relative_path))

        return template.render(
            content=content,
            card_count=card_count,
            difficulty=difficulty,
            basic_tags=basic_tags or [],
            optional_tags=optional_tags or [],
        )


class CardGenerator:
    """卡片生成器"""

    def __init__(
        self,
        llm_config: LLMConfig,
        cache: Optional[FileCache] = None,
    ):
        """
        初始化卡片生成器

        Args:
            llm_config: LLM配置
            cache: 缓存对象，如果为None则不使用缓存
        """
        self.llm_config = llm_config
        self.llm_engine = LLMEngine(llm_config)
        self.template_manager = PromptTemplate()
        self.cache = cache
        # 初始化资源估算器
        self.estimator = create_estimator_from_config(llm_config)
        # 用于保护 stdout 写入的锁（避免并发输出混乱）
        self._stdout_lock = asyncio.Lock()

    async def generate_cards(
        self,
        content: str,
        config: GenerationConfig,
        output_dir: Optional[Path] = None,
    ) -> tuple[List[Card], GenerationStats]:
        """
        生成卡片

        如果需要的卡片数量超过20张，会自动切分内容并多次调用API。

        Args:
            content: 输入内容
            config: 生成配置
            output_dir: 输出目录，如果提供则在获得 API 响应后立即保存

        Returns:
            (卡片列表, 统计信息) 元组
        """
        # 加载标签文件（如果指定）
        basic_tags = []
        optional_tags = []
        if config.tags_file:
            try:
                tags_path = Path(config.tags_file)
                tags_data = load_tags_file(tags_path)
                basic_tags = tags_data.get("basic_tags", [])
                optional_tags = tags_data.get("optional_tags", [])
            except Exception as e:
                logger.warning(f"加载标签文件失败: {e}，将不使用标签限制")
        
        # 检查缓存
        if self.cache:
            cache_key = f"{config.card_type}:{config.card_count}:{content[:100]}"
            cached_result = self.cache.get(cache_key, prefix="cards")
            if cached_result:
                logger.info("从缓存加载卡片")
                # 处理缓存格式：新格式是 (cards, stats) 元组，旧格式只有 cards 列表
                if isinstance(cached_result, tuple) and len(cached_result) == 2:
                    cards, stats = cached_result
                    return cards, stats
                elif isinstance(cached_result, list):
                    # 旧格式缓存：只有卡片列表，创建空的 stats
                    logger.debug("检测到旧格式缓存（只有卡片列表），创建空的统计信息")
                    empty_stats = GenerationStats()
                    return cached_result, empty_stats
                else:
                    logger.warning(f"未知的缓存格式: {type(cached_result)}，尝试直接返回")
                    # 如果格式未知，尝试作为卡片列表处理
                    if isinstance(cached_result, (list, tuple)):
                        empty_stats = GenerationStats()
                        return list(cached_result), empty_stats
                    raise ValueError(f"无法处理缓存格式: {type(cached_result)}")

        # 确定目标卡片数量
        if config.card_count:
            target_card_count = config.card_count
        else:
            target_card_count = self._estimate_total_card_count(content)

        # 使用资源估算器计算最优切分策略
        strategy = self.estimator.calculate_optimal_chunks(
            target_card_count, config.card_type
        )

        # 从配置读取最大并发数
        MAX_CONCURRENT_REQUESTS = config.max_concurrent_requests

        # 如果策略要求切分（num_chunks > 1），需要切分内容多次生成
        if strategy.num_chunks > 1:
            logger.info(
                f"目标卡片数量 {target_card_count}，"
                f"将切分内容并分 {strategy.num_chunks} 次并发生成"
            )

            # 切分内容（使用策略中的cards_per_chunk）
            content_chunks = self._chunk_content_for_cards(
                content, target_card_count, strategy.cards_per_chunk
            )
            logger.info(f"内容已切分为 {len(content_chunks)} 个块")

            # 准备并发任务
            tasks = []
            for i, chunk in enumerate(content_chunks, 1):
                # 计算每个块应该生成的卡片数量
                if i == len(content_chunks):
                    # 最后一个块生成剩余的卡片
                    remaining_cards = target_card_count - (i - 1) * strategy.cards_per_chunk
                    cards_per_chunk = max(0, min(remaining_cards, strategy.cards_per_chunk))
                else:
                    cards_per_chunk = strategy.cards_per_chunk

                if cards_per_chunk > 0:
                    logger.info(
                        f"准备生成第 {i}/{len(content_chunks)} 个块，"
                        f"目标 {cards_per_chunk} 张卡片，max_tokens={strategy.max_tokens_per_request}..."
                    )
                    tasks.append(
                        self._generate_cards_single(
                            chunk, config, cards_per_chunk, output_dir,
                            max_tokens=strategy.max_tokens_per_request,
                            task_id=i,  # 传递任务编号
                            basic_tags=basic_tags,
                            optional_tags=optional_tags,
                        )
                    )

            # 并发执行所有任务（使用信号量控制并发数）
            logger.info(f"开始并发生成 {len(tasks)} 个任务（最大并发数: {MAX_CONCURRENT_REQUESTS}）")
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

            async def bounded_generate(coro):
                """使用信号量限制并发的包装函数"""
                async with semaphore:
                    return await coro

            # 使用 gather 并发执行所有任务
            try:
                results = await asyncio.gather(
                    *[bounded_generate(task) for task in tasks],
                    return_exceptions=True,
                )
            except Exception as e:
                logger.exception(f"并发执行任务失败: {e}")
                raise Exception(f"并发执行任务失败: {e}")

            # 收集结果并处理错误
            all_cards = []
            total_stats = GenerationStats()
            for i, result in enumerate(results, 1):
                if isinstance(result, Exception):
                    logger.error(f"第 {i} 个块生成失败: {result}")
                    import traceback
                    if hasattr(result, '__traceback__'):
                        logger.debug(f"第 {i} 个块错误详情:\n{traceback.format_exception(type(result), result, result.__traceback__)}")
                    continue
                elif isinstance(result, tuple) and len(result) == 2:
                    cards, stats = result
                    all_cards.extend(cards)
                    # 合并统计信息
                    total_stats.input_tokens += stats.input_tokens
                    total_stats.output_tokens += stats.output_tokens
                    total_stats.total_time += stats.total_time
                    total_stats.api_responses.extend(stats.api_responses)
                    total_stats.prompts.extend(stats.prompts)
                    logger.info(f"第 {i} 个块成功生成 {len(cards)} 张卡片")
                else:
                    logger.warning(f"第 {i} 个块返回了意外的结果类型: {type(result)}")

            # 限制总数量
            if len(all_cards) > target_card_count:
                all_cards = all_cards[:target_card_count]

            # 最终去重（跨块去重）
            if config.enable_deduplication:
                all_cards = self._deduplicate_cards(all_cards)

            logger.info(
                f"成功生成 {len(all_cards)} 张卡片（并发执行 {len(tasks)} 个任务）"
            )

            # 保存到缓存（保存 cards 和 stats 的元组）
            if self.cache:
                cache_key = f"{config.card_type}:{config.card_count}:{content[:100]}"
                # 创建简化的 stats（不包含 prompts 和 api_responses，因为它们可能很大）
                cached_stats = GenerationStats()
                cached_stats.input_tokens = total_stats.input_tokens
                cached_stats.output_tokens = total_stats.output_tokens
                cached_stats.total_time = total_stats.total_time
                cached_stats.input_cache_hit_tokens = total_stats.input_cache_hit_tokens
                self.cache.set(cache_key, (all_cards, cached_stats), prefix="cards")

            # 显示统计信息
            self._display_stats(total_stats, len(all_cards))

            return all_cards, total_stats
        else:
            # 单次生成即可
            card_count = min(target_card_count, strategy.cards_per_chunk)
            cards, stats = await self._generate_cards_single(
                content, config, card_count, output_dir,
                max_tokens=strategy.max_tokens_per_request,
                basic_tags=basic_tags,
                optional_tags=optional_tags,
            )
            
            # 保存到缓存（保存 cards 和 stats 的元组）
            if self.cache:
                cache_key = f"{config.card_type}:{config.card_count}:{content[:100]}"
                # 创建简化的 stats（不包含 prompts 和 api_responses，因为它们可能很大）
                cached_stats = GenerationStats()
                cached_stats.input_tokens = stats.input_tokens
                cached_stats.output_tokens = stats.output_tokens
                cached_stats.total_time = stats.total_time
                cached_stats.input_cache_hit_tokens = stats.input_cache_hit_tokens
                self.cache.set(cache_key, (cards, cached_stats), prefix="cards")
            
            # 显示统计信息
            self._display_stats(stats, len(cards))
            return cards, stats

    async def _generate_cards_single(
        self,
        content: str,
        config: GenerationConfig,
        card_count: int,
        output_dir: Optional[Path] = None,
        max_tokens: Optional[int] = None,
        task_id: Optional[int] = None,
        basic_tags: Optional[List[str]] = None,
        optional_tags: Optional[List[str]] = None,
    ) -> tuple[List[Card], GenerationStats]:
        """
        单次生成卡片（内部方法）

        Args:
            content: 输入内容
            config: 生成配置
            card_count: 本次生成的卡片数量
            output_dir: 输出目录，如果提供则在获得 API 响应后立即保存
            max_tokens: 本次API调用的max_tokens，如果为None则使用配置中的值
            task_id: 任务编号（用于并发时区分不同任务的输出）

        Returns:
            (卡片列表, 统计信息) 元组
        """
        stats = GenerationStats()
        start_time = time.time()
        
        # 渲染提示词
        try:
            prompt = self.template_manager.render(
                template_name=config.card_type,
                content=content,
                card_count=card_count,
                difficulty=config.difficulty,
                custom_prompt=config.custom_prompt,
                basic_tags=basic_tags or [],
                optional_tags=optional_tags or [],
            )
            # 保存提示词到统计信息
            stats.prompts.append(prompt)
        except FileNotFoundError as e:
            logger.error(f"模板文件未找到: {e}")
            raise Exception(f"模板文件未找到: {e}。请检查卡片类型 '{config.card_type}' 的模板是否存在")
        except Exception as e:
            logger.exception(f"渲染提示词失败: {e}")
            raise Exception(f"渲染提示词失败: {e}")

        # 估算输入 token 数
        try:
            stats.input_tokens = self.llm_engine.provider._estimate_tokens(prompt)
        except Exception as e:
            logger.warning(f"估算输入 token 数失败: {e}，使用默认值")
            stats.input_tokens = len(prompt) // 4  # 简单估算

        # 如果指定了max_tokens，临时修改llm_config
        original_max_tokens = None
        if max_tokens is not None:
            original_max_tokens = self.llm_config.max_tokens
            self.llm_config.max_tokens = max_tokens
            # 需要更新llm_engine的provider配置
            self.llm_engine.provider.config.max_tokens = max_tokens

        try:
            # 调用LLM生成（使用流式输出以显示进度）
            task_prefix = f"[任务 {task_id}] " if task_id else ""
            logger.info(f"{task_prefix}正在生成 {card_count} 张 {config.card_type} 卡片...")
            response_parts = []
            last_token_count = 0
            last_display_time = time.time()
            
            try:
                async for chunk, token_count in self.llm_engine.stream_generate(prompt):
                    response_parts.append(chunk)
                    # 每增加10个token或每0.5秒更新一次显示
                    current_time = time.time()
                    if (token_count - last_token_count >= 10 or 
                        current_time - last_display_time >= 0.5 or 
                        token_count < 50):
                        # 使用锁保护 stdout 写入，避免并发输出混乱
                        async with self._stdout_lock:
                            # 使用 sys.stdout.write 实现实时更新（覆盖同一行）
                            progress_msg = f"{task_prefix}已接收 {token_count} tokens..."
                            sys.stdout.write(f"\r{progress_msg}")
                            sys.stdout.flush()
                        last_token_count = token_count
                        last_display_time = current_time
                
                # 换行，结束进度显示
                async with self._stdout_lock:
                    finish_msg = f"{task_prefix}已接收 {last_token_count} tokens，解析响应中..."
                    sys.stdout.write(f"\r{finish_msg}\n")
                    sys.stdout.flush()
                response = "".join(response_parts)
                stats.output_tokens = last_token_count
            except Exception as e:
                # 如果流式输出失败，回退到非流式
                async with self._stdout_lock:
                    sys.stdout.write("\n")  # 确保换行
                    sys.stdout.flush()
                logger.warning(f"{task_prefix}流式输出失败，回退到非流式模式: {e}")
                try:
                    response = await self.llm_engine.generate(prompt)
                    # 估算输出 token 数
                    try:
                        stats.output_tokens = self.llm_engine.provider._estimate_tokens(response)
                    except Exception as e2:
                        logger.warning(f"估算输出 token 数失败: {e2}，使用默认值")
                        stats.output_tokens = len(response) // 4  # 简单估算
                except Exception as e2:
                    logger.exception(f"LLM生成失败: {e2}")
                    raise Exception(f"LLM生成失败: {e2}。请检查API配置和网络连接")
        finally:
            # 恢复原始的max_tokens
            if original_max_tokens is not None:
                self.llm_config.max_tokens = original_max_tokens
                self.llm_engine.provider.config.max_tokens = original_max_tokens

        # 记录总用时
        stats.total_time = time.time() - start_time

        # 保存 API 响应
        stats.api_responses.append(response)

        # 立即保存 API 响应到文件（如果提供了输出目录）
        if output_dir:
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                import uuid
                timestamp = int(time.time())
                api_response_file = output_dir / f"api_response_{timestamp}_{uuid.uuid4().hex[:8]}.json"
                import json
                with open(api_response_file, "w", encoding="utf-8") as f:
                    json.dump({"response": response, "response_count": len(stats.api_responses)}, f, ensure_ascii=False, indent=2)
                logger.info(f"已立即保存 API 响应到: {api_response_file}")
            except PermissionError as e:
                logger.error(f"保存 API 响应失败（权限错误）: {e}")
            except Exception as e:
                logger.exception(f"保存 API 响应失败: {e}")

        # 解析响应（加强错误处理）
        cards = []
        try:
            cards = self._parse_response(response, config.card_type)
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            logger.error(f"响应内容预览: {response[:500]}")
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")
            # 即使解析失败，也返回空列表，不抛出异常

        # 质量过滤（加强错误处理）
        try:
            if config.enable_quality_filter:
                original_count = len(cards)
                cards = self._filter_cards(cards, config.card_type)
                if len(cards) < original_count:
                    logger.info(f"质量过滤: {original_count} -> {len(cards)} 张卡片")
        except Exception as e:
            logger.warning(f"质量过滤失败: {e}，跳过过滤")
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")

        # 去重（加强错误处理）
        try:
            if config.enable_deduplication:
                original_count = len(cards)
                cards = self._deduplicate_cards(cards)
                if len(cards) < original_count:
                    logger.info(f"去重: {original_count} -> {len(cards)} 张卡片")
        except Exception as e:
            logger.warning(f"去重失败: {e}，跳过去重")
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")

        # 限制数量
        if len(cards) > card_count:
            cards = cards[:card_count]

        if len(cards) == 0:
            logger.warning("解析后未获得任何有效卡片")
            logger.warning(f"API 响应长度: {len(response)} 字符")
            logger.warning(f"API 响应预览: {response[:500]}")
        else:
            logger.info(f"成功生成 {len(cards)} 张卡片")
        
        return cards, stats

    def _load_pricing_config(self) -> Optional[dict]:
        """
        从 model_info.yml 加载 pricing_per_million_tokens 配置
        
        Returns:
            包含 input, input_cache_hit, output 键的字典，如果未找到则返回 None
        """
        try:
            model_info_dict = load_model_info()
            if model_info_dict:
                models = model_info_dict.get("models", {})
                # 根据配置中的 model_name 查找对应的模型信息
                model_name = self.llm_config.model_name
                if model_name in models:
                    model_data = models[model_name]
                    pricing_config = model_data.get("pricing_per_million_tokens", {})
                    if pricing_config:
                        return {
                            "input": pricing_config.get("input", 2.0),
                            "input_cache_hit": pricing_config.get("input_cache_hit", 0.2),
                            "output": pricing_config.get("output", 3.0),
                        }
        except Exception as e:
            logger.debug(f"加载 pricing_per_million_tokens 配置失败: {e}")
        return None

    def _calculate_cost(self, stats: GenerationStats) -> Optional[float]:
        """
        计算 API 调用花费（人民币）
        
        Args:
            stats: 统计信息
            
        Returns:
            花费金额（人民币），如果配置不存在则返回 None
        """
        pricing_config = self._load_pricing_config()
        if not pricing_config:
            return None
        
        # 计算输入 token 花费（区分 cache hit 和 cache miss）
        input_cache_miss_tokens = stats.input_cache_miss_tokens
        input_cache_hit_tokens = stats.input_cache_hit_tokens
        
        input_cost = (
            input_cache_miss_tokens / 1_000_000 * pricing_config["input"] +
            input_cache_hit_tokens / 1_000_000 * pricing_config["input_cache_hit"]
        )
        
        # 计算输出 token 花费
        output_cost = stats.output_tokens / 1_000_000 * pricing_config["output"]
        
        total_cost = input_cost + output_cost
        return total_cost

    def _display_stats(self, stats: GenerationStats, card_count: int) -> None:
        """
        显示生成统计信息

        Args:
            stats: 统计信息
            card_count: 生成的卡片数量
        """
        if card_count == 0:
            return
        
        logger.info("=" * 60)
        logger.info("生成统计信息:")
        logger.info(f"  输入 Token 数: {stats.input_tokens:,}")
        if stats.input_cache_hit_tokens > 0:
            logger.info(f"    - Cache Hit: {stats.input_cache_hit_tokens:,}")
            logger.info(f"    - Cache Miss: {stats.input_cache_miss_tokens:,}")
        logger.info(f"  输出 Token 数: {stats.output_tokens:,}")
        logger.info(f"  总 Token 数: {stats.total_tokens:,}")
        logger.info(f"  总用时: {stats.total_time:.2f} 秒")
        logger.info(f"  平均每 Token 用时: {stats.avg_time_per_token * 1000:.2f} 毫秒")
        logger.info(f"  生成速度: {stats.tokens_per_second:.2f} tokens/秒")
        logger.info(f"  每张卡片平均 Token: {stats.output_tokens / card_count:.1f}")
        logger.info(f"  每张卡片平均用时: {stats.total_time / card_count:.2f} 秒")
        
        # 计算并显示花费
        cost = self._calculate_cost(stats)
        if cost is not None:
            logger.info(f"  预估花费: ¥{cost:.4f}")
            logger.info(f"  每张卡片平均花费: ¥{cost / card_count:.4f}")
        else:
            logger.debug("  未找到定价配置，跳过花费计算")
        
        logger.info("=" * 60)

    def _parse_response(self, response: str, card_type: str) -> List[Card]:
        """
        解析LLM响应

        Args:
            response: LLM响应文本
            card_type: 卡片类型

        Returns:
            卡片列表
        """
        cards = []

        # 尝试提取JSON
        json_str = None
        
        # 方法1: 提取代码块中的JSON
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 方法2: 提取代码块中的JSON（无语言标识）
            json_match = re.search(r"```\s*(\{.*\"cards\".*?\})\s*```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 方法3: 尝试找到完整的JSON对象（从第一个{到匹配的}）
                # 使用栈来匹配括号
                start_idx = response.find('{"cards"')
                if start_idx == -1:
                    start_idx = response.find('{\"cards\"')
                if start_idx != -1:
                    brace_count = 0
                    for i in range(start_idx, len(response)):
                        if response[i] == '{':
                            brace_count += 1
                        elif response[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_str = response[start_idx:i+1]
                                break
                
                if not json_str:
                    # 方法4: 尝试直接解析整个响应
                    json_str = response.strip()

        if not json_str:
            logger.warning("无法从响应中提取JSON")
            return cards

        try:
            # 清理可能的markdown格式
            json_str = json_str.strip()
            if json_str.startswith("```"):
                json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
                json_str = re.sub(r"\s*```$", "", json_str)
            
            data = json.loads(json_str)
            cards_data = data.get("cards", [])

            for card_data in cards_data:
                try:
                    card = self._create_card_from_data(card_data, card_type)
                    if card:
                        cards.append(card)
                except Exception as e:
                    logger.warning(f"解析卡片失败: {e}, 数据: {card_data}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.debug(f"响应内容: {response[:500]}")
            # 尝试修复常见的JSON问题
            try:
                # 尝试修复尾随逗号
                json_str_fixed = re.sub(r',\s*}', '}', json_str)
                json_str_fixed = re.sub(r',\s*]', ']', json_str_fixed)
                data = json.loads(json_str_fixed)
                cards_data = data.get("cards", [])
                for card_data in cards_data:
                    try:
                        card = self._create_card_from_data(card_data, card_type)
                        if card:
                            cards.append(card)
                    except Exception as e2:
                        logger.warning(f"解析卡片失败: {e2}, 数据: {card_data}")
            except Exception:
                pass

        return cards

    def _create_card_from_data(
        self, card_data: dict, card_type: str
    ) -> Optional[Card]:
        """
        从数据字典创建卡片对象
        
        支持从模板字段名称（如 "Front", "Back", "Text", "Tags"）映射到Card对象字段

        Args:
            card_data: 卡片数据字典（可能包含模板字段名称）
            card_type: 卡片类型

        Returns:
            卡片对象
        """
        card_type_enum = CardType(card_type)

        if card_type_enum == CardType.BASIC:
            # 支持 "Front"/"front" 和 "Back"/"back" 字段
            front = card_data.get("Front") or card_data.get("front", "")
            back = card_data.get("Back") or card_data.get("back", "")
            # 将换行符替换为 HTML <br>
            front = front.replace("\n", "<br>") if front else ""
            back = back.replace("\n", "<br>") if back else ""
            # 支持 "Tags"/"tags" 字段
            tags = card_data.get("Tags") or card_data.get("tags", [])
            
            return BasicCard(
                front=front,
                back=back,
                tags=tags if isinstance(tags, list) else [],
                metadata=card_data.get("metadata", {}),
            )

        elif card_type_enum == CardType.CLOZE:
            # Cloze卡片使用 "Text" 字段
            text = card_data.get("Text") or card_data.get("text") or card_data.get("front", "")
            # 将换行符替换为 HTML <br>
            text = text.replace("\n", "<br>") if text else ""
            # 验证是否包含cloze标记
            if "{{c" not in text:
                logger.warning("Cloze卡片缺少填空标记")
                return None

            # 支持 "Tags"/"tags" 字段
            tags = card_data.get("Tags") or card_data.get("tags", [])

            return ClozeCard(
                front=text,
                back=text,  # Cloze卡片back通常与front相同
                tags=tags if isinstance(tags, list) else [],
                metadata=card_data.get("metadata", {}),
            )

        elif card_type_enum == CardType.MCQ:
            # MCQ卡片使用 "Question" 或 "Front" 字段
            front = card_data.get("Question") or card_data.get("Front") or card_data.get("front", "")
            # 将换行符替换为 HTML <br>
            front = front.replace("\n", "<br>") if front else ""
            
            # 支持新的格式：OptionA-F 字段
            options = []
            option_letters = ["A", "B", "C", "D", "E", "F"]
            
            # 首先尝试新格式（OptionA-F）
            has_new_format = False
            for letter in option_letters:
                option_key = f"Option{letter}"
                option_value = card_data.get(option_key, "").strip()
                if option_value:
                    has_new_format = True
                    # 将换行符替换为 HTML <br>
                    option_value = option_value.replace("\n", "<br>")
                    # 从 Answer 字段判断是否正确
                    answer = card_data.get("Answer", "").strip().upper()
                    is_correct = letter in answer
                    options.append(MCQOption(text=option_value, is_correct=is_correct))
            
            # 如果没有新格式，尝试 Options 数组格式
            if not has_new_format:
                options_data = card_data.get("Options") or card_data.get("options", [])
                if options_data:
                    for opt_data in options_data:
                        if isinstance(opt_data, dict):
                            opt_text = opt_data.get("text", "")
                            # 将换行符替换为 HTML <br>
                            opt_text = opt_text.replace("\n", "<br>")
                            options.append(
                                MCQOption(
                                    text=opt_text,
                                    is_correct=opt_data.get("is_correct", False),
                                )
                            )
                        elif isinstance(opt_data, str):
                            # 简单格式：字符串列表，第一个是正确答案
                            opt_text = opt_data.replace("\n", "<br>")
                            options.append(MCQOption(text=opt_text, is_correct=len(options) == 0))
            
            if not options:
                logger.warning("MCQ卡片缺少选项")
                return None

            # 验证是否有正确答案
            if not any(opt.is_correct for opt in options):
                logger.warning("MCQ卡片没有正确答案")
                return None

            # 支持 "Tags"/"tags" 字段
            tags = card_data.get("Tags") or card_data.get("tags", [])
            # 支持 "Note"/"Explanation"/"explanation" 字段
            explanation = (
                card_data.get("Note")
                or card_data.get("Explanation")
                or card_data.get("explanation")
            )
            # 将换行符替换为 HTML <br>
            if explanation:
                explanation = explanation.replace("\n", "<br>")
            
            # 提取 NoteA-F 字段并存储到 metadata 中
            metadata = card_data.get("metadata", {})
            option_letters = ["A", "B", "C", "D", "E", "F"]
            for letter in option_letters:
                note_key = f"Note{letter}"
                note_value = card_data.get(note_key, "").strip()
                if note_value:
                    metadata[note_key] = note_value

            return MCQCard(
                front=front,
                back="",  # MCQ卡片不使用back字段
                card_type=CardType.MCQ,
                options=options,
                explanation=explanation,
                tags=tags if isinstance(tags, list) else [],
                metadata=metadata,
            )

        return None

    def _filter_cards(self, cards: List[Card], card_type: str) -> List[Card]:
        """
        过滤低质量卡片

        Args:
            cards: 卡片列表
            card_type: 卡片类型

        Returns:
            过滤后的卡片列表
        """
        filtered = []

        for card in cards:
            # 基本验证
            if not card.front or len(card.front.strip()) == 0:
                continue

            if card.card_type == CardType.BASIC:
                if not card.back or len(card.back.strip()) == 0:
                    continue

            elif card.card_type == CardType.CLOZE:
                # 验证cloze标记
                if "{{c" not in card.front:
                    continue

            elif card.card_type == CardType.MCQ:
                if isinstance(card, MCQCard):
                    if len(card.options) < 2:
                        continue
                    if not card.validate_options():
                        continue

            filtered.append(card)

        logger.debug(f"质量过滤: {len(cards)} -> {len(filtered)}")
        return filtered

    def _deduplicate_cards(self, cards: List[Card]) -> List[Card]:
        """
        去重卡片（基于正面内容）

        Args:
            cards: 卡片列表

        Returns:
            去重后的卡片列表
        """
        seen = set()
        unique_cards = []

        for card in cards:
            # 使用front内容作为唯一标识
            front_normalized = card.front.lower().strip()
            if front_normalized not in seen:
                seen.add(front_normalized)
                unique_cards.append(card)

        logger.debug(f"去重: {len(cards)} -> {len(unique_cards)}")
        return unique_cards

    def _estimate_card_count(self, content: str) -> int:
        """
        估算卡片数量

        基于内容长度估算合适的卡片数量。
        单次API请求最多生成20张卡片。

        Args:
            content: 内容文本

        Returns:
            估算的卡片数量（最多20张）
        """
        # 策略：每500字符生成1张卡片，最少5张，最多20张（单次API限制）
        char_count = len(content)
        estimated = max(5, min(20, char_count // 500))
        return estimated

    def _estimate_total_card_count(self, content: str) -> int:
        """
        估算总卡片数量（不考虑单次限制）

        用于确定是否需要切分内容多次生成。

        Args:
            content: 内容文本

        Returns:
            估算的总卡片数量
        """
        # 策略：每500字符生成1张卡片，最少5张，最多不限制
        char_count = len(content)
        estimated = max(5, char_count // 500)
        return estimated

    def _chunk_content_for_cards(
        self, content: str, target_card_count: int, max_cards_per_chunk: int = 20
    ) -> List[str]:
        """
        根据目标卡片数量切分内容

        将内容切分成多个块，每个块最多生成max_cards_per_chunk张卡片。

        Args:
            content: 输入内容
            target_card_count: 目标卡片总数
            max_cards_per_chunk: 每个块最多生成的卡片数（默认20）

        Returns:
            内容块列表
        """
        if target_card_count <= max_cards_per_chunk:
            return [content]

        # 计算需要多少个块
        num_chunks = (target_card_count + max_cards_per_chunk - 1) // max_cards_per_chunk

        # 估算每个块应该包含多少字符
        # 假设每500字符生成1张卡片
        chars_per_card = 500
        chars_per_chunk = chars_per_card * max_cards_per_chunk

        # 按段落切分（保持语义完整性）
        paragraphs = content.split("\n\n")
        if not paragraphs:
            # 如果没有段落分隔，按换行符切分
            paragraphs = [p for p in content.split("\n") if p.strip()]

        if not paragraphs:
            return [content]

        chunks = []
        current_chunk = []
        current_chars = 0

        for para in paragraphs:
            para_chars = len(para)

            # 如果当前块加上这个段落会超过限制，保存当前块
            if current_chars + para_chars > chars_per_chunk * 1.1 and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_chars = para_chars
            else:
                current_chunk.append(para)
                current_chars += para_chars

        # 添加最后一个块
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # 如果切分后块数不够，尝试更细粒度的切分
        if len(chunks) < num_chunks and len(chunks) > 0:
            # 重新计算每个块应该包含的字符数
            total_chars = len(content)
            chars_per_chunk = total_chars // num_chunks

            # 按句子切分
            sentences = re.split(r'[。！？\n]', content)
            sentences = [s.strip() for s in sentences if s.strip()]

            if sentences:
                chunks = []
                current_chunk = []
                current_chars = 0

                for sent in sentences:
                    sent_chars = len(sent)

                    if current_chars + sent_chars > chars_per_chunk * 1.1 and current_chunk:
                        chunks.append(" ".join(current_chunk))
                        current_chunk = [sent]
                        current_chars = sent_chars
                    else:
                        current_chunk.append(sent)
                        current_chars += sent_chars

                if current_chunk:
                    chunks.append(" ".join(current_chunk))

        # 确保至少有一个块
        return chunks if chunks else [content]
