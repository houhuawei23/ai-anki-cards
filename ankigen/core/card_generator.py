"""
卡片生成器模块

负责调用LLM生成卡片，解析响应，并进行质量过滤和去重。
"""

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import List, Optional

from loguru import logger

from ankigen.core.card_deduplicator import CardDeduplicator
from ankigen.core.card_factory import CardFactory
from ankigen.core.card_filter import CardFilter
from ankigen.core.content_chunker import ContentChunker
from ankigen.core.estimator import create_estimator_from_config
from ankigen.core.llm_engine import LLMEngine
from ankigen.core.prompt_template import PromptTemplate
from ankigen.core.response_parser import ResponseParser
from ankigen.core.stats import GenerationStats
from ankigen.core.stats_display import StatsDisplay
from ankigen.core.tags_loader import load_tags_file
from ankigen.exceptions import CardGenerationError, TemplateError
from ankigen.models.card import Card
from ankigen.models.config import GenerationConfig, LLMConfig
from ankigen.utils.cache import FileCache


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

        # 初始化各个组件
        self.response_parser = ResponseParser()
        self.card_factory = CardFactory()
        self.card_filter = CardFilter()
        self.card_deduplicator = CardDeduplicator()
        self.content_chunker = ContentChunker()
        self.stats_display = StatsDisplay(llm_config)

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
                    raise CardGenerationError(f"无法处理缓存格式: {type(cached_result)}")

        # 确定目标卡片数量
        target_card_count = config.card_count or self._estimate_total_card_count(content)

        # 使用资源估算器计算最优切分策略
        strategy = self.estimator.calculate_optimal_chunks(target_card_count, config.card_type)

        # 从配置读取最大并发数
        max_concurrent_requests = config.max_concurrent_requests

        # 如果策略要求切分（num_chunks > 1），需要切分内容多次生成
        if strategy.num_chunks > 1:
            logger.info(
                f"目标卡片数量 {target_card_count}，将切分内容并分 {strategy.num_chunks} 次并发生成"
            )

            # 切分内容（使用策略中的cards_per_chunk）
            content_chunks = self.content_chunker.chunk_for_cards(
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
                            chunk,
                            config,
                            cards_per_chunk,
                            output_dir,
                            max_tokens=strategy.max_tokens_per_request,
                            task_id=i,  # 传递任务编号
                            basic_tags=basic_tags,
                            optional_tags=optional_tags,
                        )
                    )

            # 并发执行所有任务（使用信号量控制并发数）
            logger.info(
                f"开始并发生成 {len(tasks)} 个任务（最大并发数: {max_concurrent_requests}）"
            )
            semaphore = asyncio.Semaphore(max_concurrent_requests)

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
                raise CardGenerationError(f"并发执行任务失败: {e}") from e

            # 收集结果并处理错误
            all_cards = []
            total_stats = GenerationStats()
            for i, result in enumerate(results, 1):
                if isinstance(result, Exception):
                    logger.error(f"第 {i} 个块生成失败: {result}")
                    import traceback

                    if hasattr(result, "__traceback__"):
                        logger.debug(
                            f"第 {i} 个块错误详情:\n{traceback.format_exception(type(result), result, result.__traceback__)}"
                        )
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
                all_cards = self.card_deduplicator.deduplicate(all_cards)

            logger.info(f"成功生成 {len(all_cards)} 张卡片（并发执行 {len(tasks)} 个任务）")

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
            self.stats_display.display(total_stats, len(all_cards))

            return all_cards, total_stats
        else:
            # 单次生成即可
            card_count = min(target_card_count, strategy.cards_per_chunk)
            cards, stats = await self._generate_cards_single(
                content,
                config,
                card_count,
                output_dir,
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
            self.stats_display.display(stats, len(cards))
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
        except TemplateError as e:
            logger.error(f"模板错误: {e}")
            raise CardGenerationError(f"模板错误: {e}") from e
        except Exception as e:
            logger.exception(f"渲染提示词失败: {e}")
            raise CardGenerationError(f"渲染提示词失败: {e}") from e

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

            # 显示连接提示
            async with self._stdout_lock:
                sys.stdout.write(f"\r{task_prefix}正在连接 API...")
                sys.stdout.flush()

            try:
                stream_start_time = time.time()
                first_chunk_received = False
                async for chunk, token_count in self.llm_engine.stream_generate(prompt):
                    # 收到第一个chunk时显示提示
                    if not first_chunk_received:
                        first_chunk_time = time.time()
                        first_chunk_received = True
                        elapsed = int(first_chunk_time - stream_start_time)
                        async with self._stdout_lock:
                            sys.stdout.write(f"\r{task_prefix}已开始接收响应 (等待 {elapsed}秒)...")
                            sys.stdout.flush()
                    response_parts.append(chunk)
                    # 每增加10个token或每0.5秒更新一次显示
                    current_time = time.time()
                    if (
                        token_count - last_token_count >= 10
                        or current_time - last_display_time >= 0.5
                        or token_count < 50
                    ):
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
                    raise CardGenerationError(f"LLM生成失败: {e2}。请检查API配置和网络连接") from e2
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
                timestamp = int(time.time())
                api_response_file = (
                    output_dir / f"api_response_{timestamp}_{uuid.uuid4().hex[:8]}.json"
                )
                with open(api_response_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {"response": response, "response_count": len(stats.api_responses)},
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
                logger.info(f"已立即保存 API 响应到: {api_response_file}")
            except PermissionError as e:
                logger.error(f"保存 API 响应失败（权限错误）: {e}")
            except Exception as e:
                logger.exception(f"保存 API 响应失败: {e}")

        # 解析响应（加强错误处理）
        cards = []
        try:
            cards = self.response_parser.parse_response(
                response, config.card_type, self.card_factory
            )
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
                cards = self.card_filter.filter_cards(cards, config.card_type)
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
                cards = self.card_deduplicator.deduplicate(cards)
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
        根据目标卡片数量切分内容（已弃用，使用content_chunker.chunk_for_cards）

        保留此方法以保持向后兼容性。
        """
        return self.content_chunker.chunk_for_cards(content, target_card_count, max_cards_per_chunk)
