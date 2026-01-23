#!/usr/bin/env python3
"""测试 MCQ-Card 功能"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ankigen.core.template_loader import get_template_meta, get_template_dir
from ankigen.core.card_generator import CardGenerator
from ankigen.models.card import CardType

def test_template_loading():
    """测试模板加载"""
    print("=== 测试模板加载 ===")
    
    # 测试 MCQ 模板目录
    mcq_dir = get_template_dir(CardType.MCQ)
    print(f"MCQ 模板目录: {mcq_dir}")
    assert mcq_dir is not None, "MCQ 模板目录不存在"
    assert mcq_dir.name == "MCQ-Card", f"模板目录名称错误: {mcq_dir.name}"
    
    # 测试 MCQ 模板元信息
    mcq_meta = get_template_meta(CardType.MCQ)
    assert mcq_meta is not None, "未找到 MCQ 模板元信息"
    print(f"MCQ 模板名称: {mcq_meta.name}")
    print(f"MCQ 模板字段数: {len(mcq_meta.fields)}")
    print(f"MCQ 模板字段: {mcq_meta.fields}")
    
    # 验证字段
    expected_fields = ["Question", "OptionA", "OptionB", "Answer", "Tags"]
    for field in expected_fields:
        assert field in mcq_meta.fields, f"缺少字段: {field}"
    
    print("✓ 模板加载测试通过\n")

def test_card_creation():
    """测试卡片创建"""
    print("=== 测试卡片创建 ===")
    
    generator = CardGenerator.__new__(CardGenerator)
    
    # 测试新格式的 MCQ 卡片数据（多选题）
    mcq_data = {
        "Question": "以下哪些是Python的特点？",
        "OptionA": "解释型语言",
        "OptionB": "编译型语言",
        "OptionC": "动态类型",
        "OptionD": "静态类型",
        "Answer": "AC",
        "Note": "Python是解释型语言，也是动态类型语言",
        "Tags": ["编程", "Python"],
    }
    
    card = generator._create_card_from_data(mcq_data, "mcq")
    assert card is not None, "MCQ卡片创建失败"
    print(f"✓ MCQ卡片创建成功")
    print(f"  问题: {card.front}")
    print(f"  选项数: {len(card.options)}")
    
    correct_count = 0
    for i, opt in enumerate(card.options):
        correct = "✓" if opt.is_correct else "○"
        print(f"  {correct} {chr(65+i)}: {opt.text}")
        if opt.is_correct:
            correct_count += 1
    
    assert correct_count == 2, f"正确答案数量错误: {correct_count}，应该是2"
    assert card.explanation == "Python是解释型语言，也是动态类型语言"
    assert len(card.tags) == 2
    
    # 测试单选题
    mcq_data_single = {
        "Question": "Python是什么类型的语言？",
        "OptionA": "编译型语言",
        "OptionB": "解释型语言",
        "OptionC": "汇编语言",
        "Answer": "B",
        "Note": "Python是解释型语言",
        "Tags": ["编程"],
    }
    
    card_single = generator._create_card_from_data(mcq_data_single, "mcq")
    assert card_single is not None, "单选题创建失败"
    correct_count_single = sum(1 for opt in card_single.options if opt.is_correct)
    assert correct_count_single == 1, f"单选题正确答案数量错误: {correct_count_single}"
    print(f"✓ 单选题创建成功，正确答案数: {correct_count_single}")
    
    print("✓ 卡片创建测试通过\n")

if __name__ == "__main__":
    try:
        test_template_loading()
        test_card_creation()
        print("=== 所有测试通过 ===")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
