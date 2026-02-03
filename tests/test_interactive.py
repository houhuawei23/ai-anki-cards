"""
交互式CLI模块单元测试

测试交互式命令选择和参数收集功能。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ankigen.cli.interactive import (
    collect_config_params,
    collect_convert_params,
    collect_generate_params,
    execute_config,
    execute_convert,
    execute_generate,
    select_command,
    validate_card_type,
    validate_export_format,
    validate_file_path,
    validate_integer,
    validate_provider,
)


class TestValidationFunctions:
    """测试验证函数"""

    def test_validate_file_path_exists(self, tmp_path):
        """测试文件路径验证（必须存在）"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        assert validate_file_path(str(test_file), must_exist=True) is True
        assert isinstance(validate_file_path("nonexistent.txt", must_exist=True), str)

    def test_validate_file_path_not_exists(self):
        """测试文件路径验证（不需要存在）"""
        assert validate_file_path("any/path.txt", must_exist=False) is True
        assert isinstance(validate_file_path("", must_exist=False), str)

    def test_validate_integer(self):
        """测试整数验证"""
        assert validate_integer("123") is True
        assert validate_integer("0") is True
        assert validate_integer("") is True  # 允许空值
        assert isinstance(validate_integer("abc"), str)
        assert isinstance(validate_integer("-5", min_value=0), str)
        assert isinstance(validate_integer("100", max_value=50), str)
        assert validate_integer("25", min_value=10, max_value=50) is True

    def test_validate_card_type(self):
        """测试卡片类型验证"""
        assert validate_card_type("basic") is True
        assert validate_card_type("cloze") is True
        assert validate_card_type("mcq") is True
        assert isinstance(validate_card_type("invalid"), str)
        assert isinstance(validate_card_type("BASIC"), str)  # 大小写敏感

    def test_validate_export_format(self):
        """测试导出格式验证"""
        assert validate_export_format("apkg") is True
        assert validate_export_format("txt") is True
        assert validate_export_format("csv") is True
        assert validate_export_format("json") is True
        assert validate_export_format("jsonl") is True
        assert isinstance(validate_export_format("invalid"), str)

    def test_validate_provider(self):
        """测试提供商验证"""
        assert validate_provider("openai") is True
        assert validate_provider("deepseek") is True
        assert validate_provider("ollama") is True
        assert validate_provider("anthropic") is True
        assert validate_provider("custom") is True
        assert isinstance(validate_provider("invalid"), str)


class TestCommandSelection:
    """测试命令选择"""

    @patch("ankigen.cli.interactive.questionary.select")
    def test_select_command_generate(self, mock_select):
        """测试选择 generate 命令"""
        mock_select.return_value.ask.return_value = "generate"
        result = select_command()
        assert result == "generate"

    @patch("ankigen.cli.interactive.questionary.select")
    def test_select_command_config(self, mock_select):
        """测试选择 config 命令"""
        mock_select.return_value.ask.return_value = "config"
        result = select_command()
        assert result == "config"

    @patch("ankigen.cli.interactive.questionary.select")
    def test_select_command_convert(self, mock_select):
        """测试选择 convert 命令"""
        mock_select.return_value.ask.return_value = "convert"
        result = select_command()
        assert result == "convert"

    @patch("ankigen.cli.interactive.questionary.select")
    def test_select_command_cancelled(self, mock_select):
        """测试取消选择"""
        mock_select.return_value.ask.return_value = None
        result = select_command()
        assert result is None


class TestParameterCollection:
    """测试参数收集"""

    @patch("ankigen.cli.interactive.questionary.path")
    @patch("ankigen.cli.interactive.questionary.select")
    @patch("ankigen.cli.interactive.questionary.text")
    @patch("ankigen.cli.interactive.questionary.confirm")
    def test_collect_generate_params(
        self, mock_confirm, mock_text, mock_select, mock_path, tmp_path
    ):
        """测试收集 generate 参数"""
        # 设置 mock 返回值
        test_input = tmp_path / "input.txt"
        test_input.write_text("test")
        test_output = tmp_path / "output.apkg"

        mock_path.side_effect = [str(test_input), str(test_output), "", ""]
        mock_select.side_effect = ["basic", "deepseek", "apkg"]
        mock_text.side_effect = ["", "deepseek-chat", "", "", ""]
        mock_confirm.side_effect = [False, False, False, False]

        params = collect_generate_params()

        assert params is not None
        assert params["input"] == test_input
        assert params["output"] == test_output
        assert params["card_type"] == "basic"
        assert params["num_cards"] is None
        assert params["provider"] == "deepseek"
        assert params["model_name"] == "deepseek-chat"
        assert params["config"] is None
        assert params["prompt"] is None
        assert params["export_format"] == "apkg"
        assert params["dry_run"] is False
        assert params["verbose"] is False
        assert params["all_formats"] is False
        assert params["tags_file"] is None
        assert params["show_prompt"] is False

    @patch("ankigen.cli.interactive.questionary.select")
    @patch("ankigen.cli.interactive.questionary.path")
    def test_collect_config_params(self, mock_path, mock_select, tmp_path):
        """测试收集 config 参数"""
        test_config = tmp_path / "config.yaml"

        mock_select.return_value.ask.return_value = "init"
        mock_path.return_value.ask.return_value = str(test_config)

        params = collect_config_params()

        assert params is not None
        assert params["init"] is True
        assert params["show"] is False
        assert params["config_path"] == test_config

    @patch("ankigen.cli.interactive.questionary.path")
    @patch("ankigen.cli.interactive.questionary.select")
    @patch("ankigen.cli.interactive.questionary.text")
    @patch("ankigen.cli.interactive.questionary.confirm")
    def test_collect_convert_params(
        self, mock_confirm, mock_text, mock_select, mock_path, tmp_path
    ):
        """测试收集 convert 参数"""
        test_input = tmp_path / "input.txt"
        test_input.write_text("test")
        test_output = tmp_path / "output.apkg"

        mock_path.side_effect = [str(test_input), str(test_output)]
        mock_select.return_value.ask.return_value = "auto"
        mock_text.side_effect = ["", ""]
        mock_confirm.return_value.ask.return_value = False

        params = collect_convert_params()

        assert params is not None
        assert params["input"] == test_input
        assert params["output"] == test_output
        assert params["card_type"] is None  # auto 转换为 None
        assert params["template"] is None
        assert params["deck_name"] is None
        assert params["verbose"] is False


class TestCommandExecution:
    """测试命令执行"""

    @patch("ankigen.cli.interactive.generate")
    def test_execute_generate(self, mock_generate, tmp_path):
        """测试执行 generate 命令"""
        test_input = tmp_path / "input.txt"
        test_output = tmp_path / "output.apkg"

        execute_generate(
            input=test_input,
            output=test_output,
            card_type="basic",
            num_cards=None,
            provider="deepseek",
            model_name="deepseek-chat",
            config=None,
            prompt=None,
            export_format="apkg",
            deck_name=None,
            dry_run=False,
            verbose=False,
            all_formats=False,
            tags_file=None,
            show_prompt=False,
        )

        mock_generate.assert_called_once()

    @patch("ankigen.cli.interactive.config")
    def test_execute_config(self, mock_config, tmp_path):
        """测试执行 config 命令"""
        test_config = tmp_path / "config.yaml"

        execute_config(init=True, show=False, config_path=test_config)

        mock_config.assert_called_once_with(init=True, show=False, config_path=test_config)

    @patch("ankigen.cli.interactive.convert")
    def test_execute_convert(self, mock_convert, tmp_path):
        """测试执行 convert 命令"""
        test_input = tmp_path / "input.txt"
        test_output = tmp_path / "output.apkg"

        execute_convert(
            input=test_input,
            output=test_output,
            card_type=None,
            template=None,
            deck_name=None,
            verbose=False,
        )

        mock_convert.assert_called_once()
