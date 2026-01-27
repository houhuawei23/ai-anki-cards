"""
响应解析器模块

负责解析LLM响应，提取JSON并创建卡片对象。
"""

import json
import re
from typing import List, Optional

from loguru import logger

from ankigen.models.card import Card


class ResponseParser:
    """
    LLM响应解析器
    
    负责从LLM响应中提取JSON数据并解析为卡片对象。
    """

    def parse_response(self, response: str, card_type: str, card_factory) -> List[Card]:
        """
        解析LLM响应
        
        Args:
            response: LLM响应文本
            card_type: 卡片类型
            card_factory: 卡片工厂对象，用于创建卡片
            
        Returns:
            卡片列表
        """
        cards = []

        # 尝试提取JSON
        json_str = self._extract_json(response)
        if not json_str:
            logger.warning("无法从响应中提取JSON")
            return cards

        try:
            # 清理可能的markdown格式
            json_str = self._clean_json_string(json_str)
            
            data = json.loads(json_str)
            cards_data = data.get("cards", [])

            for card_data in cards_data:
                try:
                    card = card_factory.create_card_from_data(card_data, card_type)
                    if card:
                        cards.append(card)
                except Exception as e:
                    logger.warning(f"解析卡片失败: {e}, 数据: {card_data}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.debug(f"响应内容: {response[:500]}")
            # 尝试修复常见的JSON问题
            cards = self._try_fix_json(response, json_str, card_type, card_factory)

        return cards

    def _extract_json(self, response: str) -> Optional[str]:
        """
        从响应中提取JSON字符串
        
        Args:
            response: LLM响应文本
            
        Returns:
            JSON字符串，如果无法提取则返回None
        """
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

        return json_str

    def _clean_json_string(self, json_str: str) -> str:
        """
        清理JSON字符串，移除markdown格式
        
        Args:
            json_str: 原始JSON字符串
            
        Returns:
            清理后的JSON字符串
        """
        json_str = json_str.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
            json_str = re.sub(r"\s*```$", "", json_str)
        return json_str

    def _try_fix_json(
        self, 
        response: str, 
        json_str: str, 
        card_type: str, 
        card_factory
    ) -> List[Card]:
        """
        尝试修复JSON解析错误
        
        Args:
            response: 原始响应
            json_str: JSON字符串
            card_type: 卡片类型
            card_factory: 卡片工厂对象
            
        Returns:
            解析后的卡片列表
        """
        cards = []
        try:
            # 尝试修复尾随逗号
            json_str_fixed = re.sub(r',\s*}', '}', json_str)
            json_str_fixed = re.sub(r',\s*]', ']', json_str_fixed)
            data = json.loads(json_str_fixed)
            cards_data = data.get("cards", [])
            for card_data in cards_data:
                try:
                    card = card_factory.create_card_from_data(card_data, card_type)
                    if card:
                        cards.append(card)
                except Exception as e2:
                    logger.warning(f"解析卡片失败: {e2}, 数据: {card_data}")
        except Exception:
            pass
        return cards
