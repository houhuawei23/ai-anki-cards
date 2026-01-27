"""
导出模块

支持将卡片导出为多种格式：APKG、TXT、CSV、JSON等。
"""

import csv
import json
import random
from pathlib import Path
from typing import List, Optional

import genanki
import yaml
from loguru import logger

from ankigen.core.exporter_utils import (
    ensure_output_dir,
    format_tags,
    get_card_type_string,
    parse_tags_string,
    validate_cards,
)
from ankigen.core.field_mapper import get_template_name, map_card_to_fields
from ankigen.core.template_loader import get_template_meta
from ankigen.models.card import Card, CardType, MCQCard
from ankigen.utils.guid import generate_guid_from_card_fields


class BaseExporter:
    """导出器基类"""

    def export(self, cards: List[Card], output_path: Path, **kwargs) -> None:
        """
        导出卡片

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
            **kwargs: 其他参数
        """
        raise NotImplementedError


class APKGExporter(BaseExporter):
    """Anki包（.apkg）导出器"""

    def __init__(self, deck_name: str = "Generated Deck", deck_description: str = ""):
        """
        初始化APKG导出器

        Args:
            deck_name: 牌组名称
            deck_description: 牌组描述
        """
        self.deck_name = deck_name
        self.deck_description = deck_description

    def export(
        self,
        cards: List[Card],
        output_path: Path,
        deck_id: Optional[int] = None,
    ) -> None:
        """
        导出为APKG格式

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
            deck_id: 牌组ID，如果为None则随机生成
        """
        if not validate_cards(cards):
            return

        try:
            # 确保输出目录存在
            ensure_output_dir(output_path)
            
            # 生成牌组ID
            if deck_id is None:
                deck_id = random.randrange(1 << 30, 1 << 31)

            # 创建牌组
            deck = genanki.Deck(deck_id, self.deck_name)

            # 添加描述
            if self.deck_description:
                deck.description = self.deck_description

            # 为每种卡片类型创建模型
            models = self._create_models()

            # 添加卡片
            added_count = 0
            for card in cards:
                try:
                    note = self._create_note(card, models)
                    if note:
                        deck.add_note(note)
                        added_count += 1
                except Exception as e:
                    logger.warning(f"添加卡片失败: {e}，卡片内容: {card.front[:50]}...")
                    continue

            if added_count == 0:
                logger.error("没有成功添加任何卡片")
                raise Exception("没有成功添加任何卡片，请检查卡片数据格式")

            # 生成包
            package = genanki.Package(deck)
            package.write_to_file(str(output_path))

            logger.info(f"已导出 {added_count}/{len(cards)} 张卡片到 {output_path}")
        except PermissionError as e:
            logger.exception(f"导出APKG失败（权限错误）: {e}")
            raise Exception(f"导出APKG失败（权限错误）: 无法写入文件 {output_path}。请检查文件权限")
        except Exception as e:
            logger.exception(f"导出APKG失败: {e}")
            raise Exception(f"导出APKG失败: {e}。请检查卡片数据和输出路径")

    def _create_models(self) -> dict:
        """
        创建Anki模型

        Returns:
            模型字典，键为卡片类型
        """
        models = {}

        # Basic卡片模型
        basic_model = genanki.Model(
            1607392319,
            "Basic Card",
            fields=[
                {"name": "Front"},
                {"name": "Back"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}<hr id='answer'>{{Back}}",
                },
            ],
        )
        models[CardType.BASIC] = basic_model

        # Cloze卡片模型
        cloze_model = genanki.Model(
            1607392320,
            "Cloze Card",
            model_type=genanki.Model.CLOZE,
            fields=[
                {"name": "Text"},
            ],
            templates=[
                {
                    "name": "Cloze",
                    "qfmt": "{{cloze:Text}}",
                    "afmt": "{{cloze:Text}}",
                },
            ],
        )
        models[CardType.CLOZE] = cloze_model

        # MCQ卡片模型
        mcq_model = genanki.Model(
            1607392321,
            "MCQ Card",
            fields=[
                {"name": "Question"},
                {"name": "Options"},
                {"name": "Answer"},
                {"name": "Explanation"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "{{Question}}<br><br>{{Options}}",
                    "afmt": "{{Question}}<br><br>{{Options}}<hr id='answer'>正确答案: {{Answer}}<br><br>{{Explanation}}",
                },
            ],
        )
        models[CardType.MCQ] = mcq_model

        return models

    def _create_note(self, card: Card, models: dict) -> Optional[genanki.Note]:
        """
        创建Anki笔记

        Args:
            card: 卡片对象
            models: 模型字典

        Returns:
            Anki笔记对象
        """
        try:
            model = models.get(card.card_type)
            if not model:
                logger.warning(f"不支持的卡片类型: {card.card_type}")
                return None

            if card.card_type == CardType.BASIC:
                if not card.front or not card.back:
                    logger.warning(f"Basic卡片缺少必要字段: front={bool(card.front)}, back={bool(card.back)}")
                    return None
                return genanki.Note(
                    model=model,
                    fields=[card.front, card.back],
                    tags=card.tags or [],
                )

            elif card.card_type == CardType.CLOZE:
                if not card.front:
                    logger.warning(f"Cloze卡片缺少必要字段: front={bool(card.front)}")
                    return None
                return genanki.Note(
                    model=model,
                    fields=[card.front],  # Cloze卡片front和back相同
                    tags=card.tags or [],
                )

            elif card.card_type == CardType.MCQ:
                if isinstance(card, MCQCard):
                    if not card.front:
                        logger.warning(f"MCQ卡片缺少必要字段: front={bool(card.front)}")
                        return None
                    if not card.options:
                        logger.warning(f"MCQ卡片缺少选项")
                        return None
                    # 格式化选项
                    options_html = "<ul>"
                    for option in card.options:
                        marker = "✓" if option.is_correct else "○"
                        options_html += f"<li>{marker} {option.text}</li>"
                    options_html += "</ul>"

                    # 获取正确答案
                    correct_answer = card.get_correct_answer() or ""

                    return genanki.Note(
                        model=model,
                        fields=[
                            card.front,
                            options_html,
                            correct_answer,
                            card.explanation or "",
                        ],
                        tags=card.tags or [],
                    )
                else:
                    logger.warning(f"MCQ卡片类型不匹配: {type(card)}")
                    return None

            return None
        except Exception as e:
            logger.exception(f"创建Anki笔记失败: {e}，卡片类型: {card.card_type}")
            return None


class TextExporter(BaseExporter):
    """文本文件（.txt）导出器（制表符分隔）"""

    def export(self, cards: List[Card], output_path: Path, **kwargs) -> None:
        """
        导出为文本格式（制表符分隔）

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
        """
        if not cards:
            logger.warning("没有卡片可导出")
            return

        with open(output_path, "w", encoding="utf-8") as f:
            for card in cards:
                if card.card_type == CardType.MCQ and isinstance(card, MCQCard):
                    # MCQ卡片特殊处理
                    options = " | ".join([opt.text for opt in card.options])
                    correct = card.get_correct_answer() or ""
                    line = f"{card.front}\t{options}\t{correct}\t{card.explanation or ''}"
                else:
                    line = f"{card.front}\t{card.back}"
                f.write(line + "\n")

        logger.info(f"已导出 {len(cards)} 张卡片到 {output_path}")


class CSVExporter(BaseExporter):
    """CSV文件导出器（Anki兼容）"""

    def export(self, cards: List[Card], output_path: Path, **kwargs) -> None:
        """
        导出为CSV格式

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
        """
        if not cards:
            logger.warning("没有卡片可导出")
            return

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow(["Front", "Back", "Tags", "Type"])

            # 写入卡片
            for card in cards:
                if card.card_type == CardType.MCQ and isinstance(card, MCQCard):
                    # MCQ卡片特殊处理
                    options = " | ".join([opt.text for opt in card.options])
                    correct = card.get_correct_answer() or ""
                    back = f"{options}\n正确答案: {correct}\n解释: {card.explanation or ''}"
                else:
                    back = card.back

                writer.writerow(
                    [
                        card.front,
                        back,
                        format_tags(card.tags),
                        get_card_type_string(card.card_type),
                    ]
                )

        logger.info(f"已导出 {len(cards)} 张卡片到 {output_path}")


class JSONExporter(BaseExporter):
    """JSON文件导出器"""

    def export(
        self,
        cards: List[Card],
        output_path: Path,
        export_format: str = "json",
        **kwargs,
    ) -> None:
        """
        导出为JSON或JSONL格式

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
            export_format: 格式（json或jsonl）
        """
        if not cards:
            logger.warning("没有卡片可导出")
            return

        cards_data = [card.model_dump() for card in cards]

        if export_format == "jsonl":
            # JSONL格式：每行一个JSON对象
            with open(output_path, "w", encoding="utf-8") as f:
                for card_data in cards_data:
                    f.write(json.dumps(card_data, ensure_ascii=False) + "\n")
        else:
            # JSON格式：单个JSON数组
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(cards_data, f, ensure_ascii=False, indent=2)

        logger.info(f"已导出 {len(cards)} 张卡片到 {output_path}")


class ItemsYAMLExporter(BaseExporter):
    """Items YAML导出器（items.yml格式）"""

    def export(self, cards: List[Card], output_path: Path, **kwargs) -> None:
        """
        导出为items.yml格式

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
        """
        if not cards:
            logger.warning("没有卡片可导出")
            return

        content_lines = []

        for card in cards:
            # 映射卡片到字段
            fields = map_card_to_fields(card)
            template_meta = get_template_meta(card.card_type)

            # 构建YAML条目
            content_lines.append("---")
            # 使用模板字段顺序，如果没有模板则使用字段字典的键
            field_names = template_meta.fields if template_meta else list(fields.keys())
            # 确保Tags字段在最后（如果存在）
            if "Tags" in field_names:
                field_names.remove("Tags")
            if "标签" in field_names:
                field_names.remove("标签")
            # 添加Tags字段（如果存在）
            if "Tags" in fields or "标签" in fields:
                field_names.append("Tags" if "Tags" in fields else "标签")
            
            for field_name in field_names:
                value = fields.get(field_name, "")
                # YAML格式：Field: value（需要转义特殊字符）
                if "\n" in value or (":" in value and not value.startswith("http")):
                    # 使用YAML多行字符串格式
                    content_lines.append(f"{field_name}: |")
                    for line in value.split("\n"):
                        content_lines.append(f"  {line}")
                else:
                    content_lines.append(f"{field_name}: {value}")

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content_lines))
            if content_lines:
                f.write("\n")

        logger.info(f"已导出 {len(cards)} 张卡片到 {output_path}")


class ItemsTXTExporter(BaseExporter):
    """Items TXT导出器（items.txt格式，Anki纯文本格式）"""

    def export(self, cards: List[Card], output_path: Path, **kwargs) -> None:
        """
        导出为items.txt格式

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
        """
        if not cards:
            logger.warning("没有卡片可导出")
            return

        # 获取第一张卡片的模板信息（假设所有卡片类型相同）
        first_card = cards[0]
        template_meta = get_template_meta(first_card.card_type)
        if not template_meta:
            logger.error(f"无法加载卡片类型 {first_card.card_type} 的模板")
            return

        # 构建列名（GUID + 字段 + Tags）
        # Tags字段不在meta.yml的Fields中，需要显式添加
        columns = ["GUID"] + [f for f in template_meta.fields if f not in ("Tags", "标签")]
        # Tags字段始终在最后
        columns.append("Tags")

        # 确定Tags列的位置
        tags_column_index = len(columns)

        # 写入文件头
        content_lines = [
            "#separator:tab",
            "#html:true",
            f"#columns:{chr(9).join(columns)}",
            "#guid column:1",
            f"#tags column:{tags_column_index}",
        ]

        # 写入卡片数据
        for card in cards:
            fields = map_card_to_fields(card)
            # 生成GUID（排除Tags）
            guid_fields = {k: v for k, v in fields.items() if k.lower() not in ("tags", "标签")}
            guid = generate_guid_from_card_fields(guid_fields, get_card_type_string(card.card_type))

            # 构建数据行
            row_values = [guid]
            for field_name in columns[1:]:  # 跳过GUID列
                if field_name == "Tags":
                    # Tags字段可能存储为"Tags"或"标签"
                    row_values.append(fields.get("Tags", fields.get("标签", "")))
                else:
                    row_values.append(fields.get(field_name, ""))

            # 用制表符连接
            content_lines.append(chr(9).join(row_values))

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content_lines))
            f.write("\n")

        logger.info(f"已导出 {len(cards)} 张卡片到 {output_path}")


class ParsedCardsJSONExporter(BaseExporter):
    """解析后的卡片 JSON 导出器"""

    def export(self, cards: List[Card], output_path: Path, **kwargs) -> None:
        """
        导出解析后的卡片为格式化的 JSON

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
        """
        if not cards:
            logger.warning("没有卡片可导出")
            return

        # 确保输出目录存在
        ensure_output_dir(output_path)

        # 将每张卡片映射到字段字典
        parsed_cards = []
        for card in cards:
            fields = map_card_to_fields(card)
            # 将 Tags 字符串转换为列表（如果存在）
            if "Tags" in fields:
                if isinstance(fields["Tags"], str):
                    fields["Tags"] = parse_tags_string(fields["Tags"])
                elif isinstance(fields["Tags"], list):
                    # 如果已经是列表，直接使用
                    fields["Tags"] = fields["Tags"]
                else:
                    # 其他情况，设为空列表
                    fields["Tags"] = []
            else:
                # 如果没有 Tags 字段，添加空列表
                fields["Tags"] = []
            parsed_cards.append(fields)

        # 构建 JSON 数据结构
        json_data = {
            "cards": parsed_cards,
            "card_count": len(cards)
        }

        # 保存为格式化的 JSON 文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        logger.info(f"已导出 {len(cards)} 张解析后的卡片到 {output_path}")


class APIResponseExporter(BaseExporter):
    """API 响应 JSON 导出器"""

    def export(
        self, 
        api_responses: List[str], 
        output_path: Path, 
        **kwargs
    ) -> None:
        """
        导出 API 响应 JSON

        Args:
            api_responses: API 响应列表
            output_path: 输出文件路径
        """
        if not api_responses:
            logger.warning("没有 API 响应可导出")
            return

        # 确保输出目录存在
        ensure_output_dir(output_path)

        # 如果只有一个响应，直接保存
        if len(api_responses) == 1:
            response_data = {
                "response": api_responses[0],
                "response_count": 1
            }
        else:
            # 多个响应，保存为数组
            response_data = {
                "responses": api_responses,
                "response_count": len(api_responses)
            }

        # 保存为 JSON 文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(response_data, f, ensure_ascii=False, indent=2)

        logger.info(f"已导出 {len(api_responses)} 个 API 响应到 {output_path}")


class ItemsWithTypeTXTExporter(BaseExporter):
    """Items With Type TXT导出器（items.with_type.txt格式，包含Notetype列）"""

    def export(self, cards: List[Card], output_path: Path, **kwargs) -> None:
        """
        导出为items.with_type.txt格式

        Args:
            cards: 卡片列表
            output_path: 输出文件路径
        """
        if not cards:
            logger.warning("没有卡片可导出")
            return

        # 获取第一张卡片的模板信息
        first_card = cards[0]
        template_meta = get_template_meta(first_card.card_type)
        if not template_meta:
            logger.error(f"无法加载卡片类型 {first_card.card_type} 的模板")
            return

        template_name = template_meta.name

        # 构建列名（GUID + Notetype + 字段 + Tags）
        # Tags字段不在meta.yml的Fields中，需要显式添加
        columns = ["GUID", "Notetype"] + [
            f for f in template_meta.fields if f not in ("Tags", "标签")
        ]
        # Tags字段始终在最后
        columns.append("Tags")

        # 确定Tags列的位置
        tags_column_index = len(columns)

        # 写入文件头
        content_lines = [
            "#separator:tab",
            "#html:true",
            f"#columns:{chr(9).join(columns)}",
            "#guid column:1",
            "#notetype column:2",
            f"#tags column:{tags_column_index}",
        ]

        # 写入卡片数据
        for card in cards:
            fields = map_card_to_fields(card)
            # 生成GUID（排除Tags）
            guid_fields = {k: v for k, v in fields.items() if k.lower() not in ("tags", "标签")}
            guid = generate_guid_from_card_fields(guid_fields, get_card_type_string(card.card_type))

            # 获取模板名称
            card_template_name = get_template_name(card.card_type)

            # 构建数据行
            row_values = [guid, card_template_name]
            for field_name in columns[2:]:  # 跳过GUID和Notetype列
                if field_name == "Tags":
                    # Tags字段可能存储为"Tags"或"标签"
                    row_values.append(fields.get("Tags", fields.get("标签", "")))
                else:
                    row_values.append(fields.get(field_name, ""))

            # 用制表符连接
            content_lines.append(chr(9).join(row_values))

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content_lines))
            f.write("\n")

        logger.info(f"已导出 {len(cards)} 张卡片到 {output_path}")


def _add_type_count_suffix(output_path: Path, cards: List[Card]) -> Path:
    """
    在文件名中添加卡片类型和数量的后缀

    Args:
        output_path: 原始输出路径
        cards: 卡片列表

    Returns:
        修改后的输出路径
    """
    if not cards:
        return output_path

    # 获取卡片类型（假设所有卡片类型相同，取第一张卡片的类型）
    card_type = get_card_type_string(cards[0].card_type)
    card_count = len(cards)

    # 获取文件名和扩展名
    stem = output_path.stem
    suffix = output_path.suffix

    # 处理特殊扩展名（如 .with_type.txt）
    # 检查是否有多个点分隔的部分，且最后一部分是特殊后缀
    parts = stem.split(".")
    if len(parts) > 1 and parts[-1] == "with_type":
        # 保留特殊后缀（如 .with_type）
        base_name = ".".join(parts[:-1])
        special_suffix = parts[-1]
        # 构建新文件名：{base_name}.{special_suffix}.{type}.{count}.{ext}
        new_stem = f"{base_name}.{special_suffix}.{card_type}.{card_count}"
    else:
        # 普通文件名：{stem}.{type}.{count}.{ext}
        new_stem = f"{stem}.{card_type}.{card_count}"

    # 构建新路径
    new_path = output_path.parent / f"{new_stem}{suffix}"
    return new_path


def export_cards(
    cards: List[Card],
    output_path: Path,
    format: str = "apkg",  # noqa: A002
    deck_name: str = "Generated Deck",
    deck_description: str = "",
    add_type_count_suffix: bool = True,
) -> None:
    """
    导出卡片的便捷函数

    Args:
        cards: 卡片列表
        output_path: 输出文件路径
        format: 导出格式（apkg/txt/csv/json/jsonl），如果为"apkg"但文件扩展名不匹配，则根据文件扩展名自动判断
        deck_name: 牌组名称（仅用于apkg格式）
        deck_description: 牌组描述（仅用于apkg格式）
        add_type_count_suffix: 是否在文件名中添加类型和数量后缀（默认True）
    """
    export_format = format.lower()
    
    # 格式映射表
    format_map = {
        ".apkg": "apkg",
        ".txt": "txt",
        ".csv": "csv",
        ".json": "json",
        ".jsonl": "jsonl",
    }
    
    # 如果格式为默认值"apkg"，但文件扩展名不匹配，则根据文件扩展名自动判断
    ext = output_path.suffix.lower()
    if export_format == "apkg" and ext in format_map and format_map[ext] != "apkg":
        export_format = format_map[ext]
        logger.info(f"根据文件扩展名自动判断格式: {ext} -> {export_format}")
    elif not export_format or export_format == "auto":
        # 如果格式为空或"auto"，根据文件扩展名自动判断
        export_format = format_map.get(ext, "apkg")  # 默认使用apkg
        logger.info(f"根据文件扩展名自动判断格式: {ext} -> {export_format}")

    # 验证格式
    valid_formats = [
        "apkg",
        "txt",
        "csv",
        "json",
        "jsonl",
        "items_yml",
        "items_txt",
        "items_with_type_txt",
    ]
    if export_format not in valid_formats:
        raise ValueError(
            f"不支持的导出格式: {export_format}。支持的格式: {', '.join(valid_formats)}"
        )

    # 如果需要，添加类型和数量后缀
    final_output_path = output_path
    if add_type_count_suffix and cards:
        final_output_path = _add_type_count_suffix(output_path, cards)
        if final_output_path != output_path:
            logger.debug(f"文件名已修改: {output_path.name} -> {final_output_path.name}")

    # 根据格式选择导出器
    try:
        if export_format == "apkg":
            exporter = APKGExporter(deck_name=deck_name, deck_description=deck_description)
            exporter.export(cards, final_output_path)
        elif export_format == "txt":
            exporter = TextExporter()
            exporter.export(cards, final_output_path)
        elif export_format == "csv":
            exporter = CSVExporter()
            exporter.export(cards, final_output_path)
        elif export_format in ["json", "jsonl"]:
            exporter = JSONExporter()
            exporter.export(cards, final_output_path, export_format=export_format)
        elif export_format == "items_yml":
            exporter = ItemsYAMLExporter()
            exporter.export(cards, final_output_path)
        elif export_format == "items_txt":
            exporter = ItemsTXTExporter()
            exporter.export(cards, final_output_path)
        elif export_format == "items_with_type_txt":
            exporter = ItemsWithTypeTXTExporter()
            exporter.export(cards, final_output_path)
        else:
            # 这不应该发生，因为前面已经验证了格式
            raise ValueError(f"不支持的导出格式: {export_format}")
    except PermissionError as e:
        logger.exception(f"导出失败（权限错误）: {e}")
        raise Exception(f"导出失败（权限错误）: 无法写入文件 {final_output_path}。请检查文件权限")
    except FileNotFoundError as e:
        logger.exception(f"导出失败（路径错误）: {e}")
        raise Exception(f"导出失败（路径错误）: 输出目录不存在或无法创建。请检查路径: {final_output_path.parent}")
    except Exception as e:
        logger.exception(f"导出失败: {e}")
        raise Exception(f"导出失败: {e}。请检查卡片数据和输出路径")


def export_api_responses(
    api_responses: List[str],
    output_path: Path,
    add_type_count_suffix: bool = True,
    card_type: Optional[str] = None,
    card_count: Optional[int] = None,
) -> None:
    """
    导出 API 响应 JSON 的便捷函数

    Args:
        api_responses: API 响应列表
        output_path: 输出文件路径
        add_type_count_suffix: 是否在文件名中添加类型和数量后缀（默认True）
        card_type: 卡片类型（用于生成文件名）
        card_count: 卡片数量（用于生成文件名）
    """
    if not api_responses:
        logger.warning("没有 API 响应可导出")
        return

    # 如果需要，添加类型和数量后缀
    final_output_path = output_path
    if add_type_count_suffix and card_type is not None and card_count is not None:
        # 构建文件名：{stem}.{type}.{count}.api_response.json
        # 如果 output_path 已经是完整路径，使用其 stem
        # 如果是目录，需要构建文件名
        if output_path.is_dir() or (not output_path.suffix and not output_path.name.endswith('.json')):
            # 目录或没有扩展名，构建新文件名
            stem = "api_response"
            new_stem = f"{stem}.{card_type}.{card_count}.api_response"
            final_output_path = output_path / f"{new_stem}.json"
        else:
            # 有扩展名，替换 stem（移除可能的 .api_response 后缀）
            stem = output_path.stem
            # 如果 stem 已经包含 .api_response，先移除
            if stem.endswith('.api_response'):
                stem = stem[:-13]  # 移除 '.api_response'
            new_stem = f"{stem}.{card_type}.{card_count}.api_response"
            final_output_path = output_path.parent / f"{new_stem}.json"
    elif not output_path.suffix or output_path.suffix != ".json":
        # 如果没有扩展名或扩展名不是 .json，添加 .json
        if output_path.is_dir() or (not output_path.suffix and not output_path.name.endswith('.json')):
            final_output_path = output_path / "api_response.json"
        else:
            final_output_path = output_path.with_suffix(".json")

    exporter = APIResponseExporter()
    exporter.export(api_responses, final_output_path)


def export_parsed_cards_json(
    cards: List[Card],
    output_path: Path,
    add_type_count_suffix: bool = True,
    card_type: Optional[str] = None,
    card_count: Optional[int] = None,
) -> None:
    """
    导出解析后的卡片为格式化 JSON 的便捷函数

    Args:
        cards: 卡片列表
        output_path: 输出文件路径
        add_type_count_suffix: 是否在文件名中添加类型和数量后缀（默认True）
        card_type: 卡片类型（用于生成文件名）
        card_count: 卡片数量（用于生成文件名）
    """
    if not validate_cards(cards):
        return

    # 如果需要，添加类型和数量后缀
    final_output_path = output_path
    if add_type_count_suffix and card_type is not None and card_count is not None:
        # 构建文件名：{stem}.{type}.{count}.parsed.json
        if output_path.is_dir() or (not output_path.suffix and not output_path.name.endswith('.json')):
            # 目录或没有扩展名，构建新文件名
            stem = "parsed_cards"
            new_stem = f"{stem}.{card_type}.{card_count}.parsed"
            final_output_path = output_path / f"{new_stem}.json"
        else:
            # 有扩展名，替换 stem
            stem = output_path.stem
            # 如果 stem 已经包含 .parsed，先移除
            if stem.endswith('.parsed'):
                stem = stem[:-7]  # 移除 '.parsed'
            new_stem = f"{stem}.{card_type}.{card_count}.parsed"
            final_output_path = output_path.parent / f"{new_stem}.json"
    elif not output_path.suffix or output_path.suffix != ".json":
        # 如果没有扩展名或扩展名不是 .json，添加 .json
        if output_path.is_dir() or (not output_path.suffix and not output_path.name.endswith('.json')):
            final_output_path = output_path / "parsed_cards.json"
        else:
            final_output_path = output_path.with_suffix(".json")

    exporter = ParsedCardsJSONExporter()
    exporter.export(cards, final_output_path)
