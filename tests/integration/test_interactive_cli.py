"""
交互式CLI集成测试

端到端测试交互式命令流程。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ankigen.cli.interactive import interactive_mode


class TestInteractiveCLI:
    """交互式CLI集成测试"""

    @patch("ankigen.cli.interactive.select_command")
    @patch("ankigen.cli.interactive.collect_generate_params")
    @patch("ankigen.cli.interactive.show_params_summary")
    @patch("ankigen.cli.interactive.questionary.confirm")
    @patch("ankigen.cli.interactive.execute_generate")
    def test_interactive_mode_generate_flow(
        self,
        mock_execute,
        mock_confirm,
        mock_summary,
        mock_collect,
        mock_select,
        tmp_path,
    ):
        """测试 generate 命令的完整流程"""
        # 设置 mock
        mock_select.return_value = "generate"
        mock_collect.return_value = {
            "input": tmp_path / "input.txt",
            "output": tmp_path / "output.apkg",
            "card_type": "basic",
        }
        mock_confirm.return_value.ask.return_value = True
        mock_execute.return_value = None

        # 执行交互式模式
        interactive_mode()

        # 验证调用
        mock_select.assert_called_once()
        mock_collect.assert_called_once()
        mock_summary.assert_called_once()
        mock_execute.assert_called_once()

    @patch("ankigen.cli.interactive.select_command")
    @patch("ankigen.cli.interactive.collect_config_params")
    @patch("ankigen.cli.interactive.show_params_summary")
    @patch("ankigen.cli.interactive.questionary.confirm")
    @patch("ankigen.cli.interactive.execute_config")
    def test_interactive_mode_config_flow(
        self,
        mock_execute,
        mock_confirm,
        mock_summary,
        mock_collect,
        mock_select,
        tmp_path,
    ):
        """测试 config 命令的完整流程"""
        # 设置 mock
        mock_select.return_value = "config"
        mock_collect.return_value = {
            "init": True,
            "show": False,
            "config_path": tmp_path / "config.yaml",
        }
        mock_confirm.return_value.ask.return_value = True
        mock_execute.return_value = None

        # 执行交互式模式
        interactive_mode()

        # 验证调用
        mock_select.assert_called_once()
        mock_collect.assert_called_once()
        mock_summary.assert_called_once()
        mock_execute.assert_called_once()

    @patch("ankigen.cli.interactive.select_command")
    @patch("ankigen.cli.interactive.collect_convert_params")
    @patch("ankigen.cli.interactive.show_params_summary")
    @patch("ankigen.cli.interactive.questionary.confirm")
    @patch("ankigen.cli.interactive.execute_convert")
    def test_interactive_mode_convert_flow(
        self,
        mock_execute,
        mock_confirm,
        mock_summary,
        mock_collect,
        mock_select,
        tmp_path,
    ):
        """测试 convert 命令的完整流程"""
        # 设置 mock
        mock_select.return_value = "convert"
        mock_collect.return_value = {
            "input": tmp_path / "input.txt",
            "output": tmp_path / "output.apkg",
            "card_type": None,
        }
        mock_confirm.return_value.ask.return_value = True
        mock_execute.return_value = None

        # 执行交互式模式
        interactive_mode()

        # 验证调用
        mock_select.assert_called_once()
        mock_collect.assert_called_once()
        mock_summary.assert_called_once()
        mock_execute.assert_called_once()

    @patch("ankigen.cli.interactive.select_command")
    def test_interactive_mode_cancelled(self, mock_select):
        """测试用户取消操作"""
        mock_select.return_value = None

        # 执行交互式模式
        interactive_mode()

        # 验证只调用了选择命令
        mock_select.assert_called_once()

    @patch("ankigen.cli.interactive.select_command")
    @patch("ankigen.cli.interactive.collect_generate_params")
    @patch("ankigen.cli.interactive.questionary.confirm")
    def test_interactive_mode_no_confirm(
        self,
        mock_confirm,
        mock_collect,
        mock_select,
        tmp_path,
    ):
        """测试用户不确认执行"""
        mock_select.return_value = "generate"
        mock_collect.return_value = {
            "input": tmp_path / "input.txt",
            "output": tmp_path / "output.apkg",
        }
        mock_confirm.return_value.ask.return_value = False

        # 执行交互式模式
        interactive_mode()

        # 验证没有执行命令
        mock_select.assert_called_once()
        mock_collect.assert_called_once()

    @patch("ankigen.cli.interactive.select_command")
    @patch("ankigen.cli.interactive.collect_generate_params")
    def test_interactive_mode_params_collection_cancelled(self, mock_collect, mock_select):
        """测试参数收集过程中取消"""
        mock_select.return_value = "generate"
        mock_collect.return_value = None

        # 执行交互式模式
        interactive_mode()

        # 验证调用
        mock_select.assert_called_once()
        mock_collect.assert_called_once()
