#!/usr/bin/env python3
"""测试导出文件名后缀功能"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ankigen.core.exporter import _add_type_count_suffix
from ankigen.models.card import BasicCard, ClozeCard, MCQCard, MCQOption, CardType

def test_suffix_adding():
    """测试文件名后缀添加"""
    print("=== 测试文件名后缀添加 ===\n")
    
    test_cases = [
        (Path("notes.txt"), [BasicCard(front="test", back="answer")] * 5, "notes.basic.5.txt"),
        (
            Path("notes.with_type.txt"),
            [ClozeCard(front="test{{c1::cloze}}", back="test")] * 10,
            "notes.with_type.cloze.10.txt",
        ),
        (Path("notes.yml"), [BasicCard(front="test", back="answer")] * 3, "notes.basic.3.yml"),
        (
            Path("items.txt"),
            [
                MCQCard(
                    front="Q",
                    back="",
                    card_type=CardType.MCQ,
                    options=[MCQOption(text="A", is_correct=True)],
                )
            ]
            * 7,
            "items.mcq.7.txt",
        ),
        (
            Path("items.with_type.txt"),
            [ClozeCard(front="test{{c1::cloze}}", back="test")] * 20,
            "items.with_type.cloze.20.txt",
        ),
    ]

    all_passed = True
    for original, cards, expected in test_cases:
        result = _add_type_count_suffix(original, cards)
        print(f"原始: {original.name}")
        print(f"结果: {result.name}")
        print(f"期望: {expected}")
        match = result.name == expected
        status = "✓" if match else "✗"
        print(f"匹配: {status}")
        if not match:
            print(f"  差异: 结果={result.name}, 期望={expected}")
            all_passed = False
        print()

    if all_passed:
        print("=== 所有测试通过 ===")
    else:
        print("=== 部分测试失败 ===")
        sys.exit(1)

if __name__ == "__main__":
    test_suffix_adding()
