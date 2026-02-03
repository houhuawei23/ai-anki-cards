"""
改进后的交互式CLI模块测试

测试菜单式交互、错误恢复、API密钥验证等功能。
"""

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ankigen.cli.interactive import (
    edit_params_menu,
    edit_single_param,
    get_available_models,
    get_configured_providers,
    get_default_config_path,
    get_provider_status,
    handle_command_error,
    select_model_name,
    show_config_file_content,
    show_error_info,
    validate_api_key_for_provider,
)


class TestAPIKeyValidation:
    """测试API密钥验证功能"""

    def test_get_provider_status_configured(self, monkeypatch):
        """测试获取已配置的提供商状态"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key_123")
        is_configured, api_key = get_provider_status("deepseek")
        assert is_configured is True
        assert api_key == "test_key_123"

    def test_get_provider_status_not_configured(self):
        """测试获取未配置的提供商状态"""
        is_configured, api_key = get_provider_status("openai")
        # 取决于环境变量是否设置
        assert isinstance(is_configured, bool)
        assert isinstance(api_key, (type(None), str))

    def test_get_configured_providers(self, monkeypatch):
        """测试获取所有提供商的配置状态"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
        providers_status = get_configured_providers()
        assert isinstance(providers_status, dict)
        assert "deepseek" in providers_status
        assert isinstance(providers_status["deepseek"], bool)

    def test_validate_api_key_format(self):
        """测试API密钥格式验证"""
        # OpenAI格式验证
        is_valid, error = validate_api_key_for_provider("openai", "sk-test123")
        assert is_valid is True

        is_valid, error = validate_api_key_for_provider("openai", "invalid")
        assert is_valid is False
        assert "格式不正确" in error

        # Anthropic格式验证
        is_valid, error = validate_api_key_for_provider("anthropic", "sk-ant-test123")
        assert is_valid is True

        is_valid, error = validate_api_key_for_provider("anthropic", "invalid")
        assert is_valid is False
        assert "格式不正确" in error

    def test_validate_api_key_empty(self):
        """测试空API密钥验证"""
        is_valid, error = validate_api_key_for_provider("deepseek", "")
        assert is_valid is False
        assert "不能为空" in error


class TestModelSelection:
    """测试模型选择功能"""

    @patch("ankigen.cli.interactive.load_model_info")
    def test_get_available_models_from_config(self, mock_load_model_info):
        """测试从配置文件加载模型列表"""
        mock_load_model_info.return_value = {
            "providers": {
                "deepseek": {
                    "models": [
                        {"name": "deepseek-chat"},
                        {"name": "deepseek-coder"},
                    ]
                }
            }
        }
        models = get_available_models("deepseek")
        assert "deepseek-chat" in models
        assert "deepseek-coder" in models

    def test_get_available_models_default(self):
        """测试获取默认模型列表"""
        models = get_available_models("deepseek")
        assert isinstance(models, list)
        assert len(models) > 0

    @patch("ankigen.cli.interactive.questionary.select")
    @patch("ankigen.cli.interactive.get_available_models")
    def test_select_model_name_from_list(self, mock_get_models, mock_select):
        """测试从列表选择模型"""
        mock_get_models.return_value = ["deepseek-chat", "deepseek-coder"]
        mock_select.return_value.ask.return_value = "deepseek-chat"
        result = select_model_name("deepseek", "deepseek-chat")
        assert result == "deepseek-chat"

    @patch("ankigen.cli.interactive.questionary.select")
    @patch("ankigen.cli.interactive.questionary.text")
    @patch("ankigen.cli.interactive.get_available_models")
    def test_select_model_name_custom(self, mock_get_models, mock_text, mock_select):
        """测试自定义输入模型名称"""
        mock_get_models.return_value = ["deepseek-chat"]
        mock_select.return_value.ask.return_value = "__custom__"
        mock_text.return_value.ask.return_value = "custom-model"
        result = select_model_name("deepseek", "deepseek-chat")
        assert result == "custom-model"


class TestConfigFile:
    """测试配置文件功能"""

    def test_get_default_config_path(self, tmp_path, monkeypatch):
        """测试获取默认配置文件路径"""
        # 测试项目根目录的config.yaml
        with patch("ankigen.cli.interactive.find_project_root", return_value=tmp_path):
            config_path = get_default_config_path()
            assert isinstance(config_path, Path)

    def test_show_config_file_content(self, tmp_path):
        """测试显示配置文件内容"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("test: value\nkey: data")

        with patch("ankigen.cli.interactive.console") as mock_console:
            show_config_file_content(config_file)
            # 验证console.print被调用
            assert mock_console.print.called

    def test_show_config_file_content_not_exists(self):
        """测试显示不存在的配置文件"""
        with patch("ankigen.cli.interactive.console") as mock_console:
            show_config_file_content(Path("nonexistent.yaml"))
            # 应该显示警告信息
            assert mock_console.print.called


class TestErrorHandling:
    """测试错误处理功能"""

    def test_handle_command_error(self):
        """测试命令错误处理"""
        error = ValueError("测试错误")
        with patch("ankigen.cli.interactive.questionary.select") as mock_select:
            mock_select.return_value.ask.return_value = "retry"
            result = handle_command_error(error, "generate", {})
            assert result == "retry"

    def test_show_error_info(self):
        """测试显示错误信息"""
        error = ValueError("测试错误")
        with patch("ankigen.cli.interactive.console") as mock_console:
            show_error_info(error, "/path/to/log.log")
            assert mock_console.print.called


class TestMenuSystem:
    """测试菜单系统"""

    def test_format_param_value(self):
        """测试参数值格式化"""
        from ankigen.cli.interactive import format_param_value

        # 测试Path对象
        value = format_param_value("input", Path("/test/path"), {})
        assert value == "/test/path"

        # 测试布尔值
        value = format_param_value("verbose", True, {})
        assert value == "是"

        value = format_param_value("verbose", False, {})
        assert value == "否"

        # 测试None值
        value = format_param_value("input", None, {"input": "default"})
        assert "默认" in value

    @patch("ankigen.cli.interactive.show_params_menu")
    @patch("ankigen.cli.interactive.questionary.select")
    def test_edit_params_menu_back(self, mock_select, mock_show_menu):
        """测试参数编辑菜单返回"""
        mock_select.return_value.ask.return_value = "back"
        result = edit_params_menu("generate", {}, {})
        assert result is None

    @patch("ankigen.cli.interactive.show_params_menu")
    @patch("ankigen.cli.interactive.questionary.select")
    def test_edit_params_menu_confirm(self, mock_select, mock_show_menu):
        """测试参数编辑菜单确认"""
        params = {"input": Path("/test")}
        mock_select.return_value.ask.return_value = "confirm"
        result = edit_params_menu("generate", params, {})
        assert result == params

    @patch("ankigen.cli.interactive.questionary.path")
    def test_edit_single_param_input(self, mock_path):
        """测试编辑单个参数 - input"""
        mock_path.return_value.ask.return_value = "/test/input.txt"
        result = edit_single_param("generate", "input", None, {})
        assert isinstance(result, Path)
        assert str(result) == "/test/input.txt"

    @patch("ankigen.cli.interactive.questionary.select")
    def test_edit_single_param_card_type(self, mock_select):
        """测试编辑单个参数 - card_type"""
        mock_select.return_value.ask.return_value = "cloze"
        result = edit_single_param("generate", "card_type", "basic", {})
        assert result == "cloze"

    @patch("ankigen.cli.interactive.get_configured_providers")
    @patch("ankigen.cli.interactive.questionary.select")
    def test_edit_single_param_provider(self, mock_select, mock_get_providers):
        """测试编辑单个参数 - provider"""
        mock_get_providers.return_value = {"deepseek": True, "openai": False}
        mock_select.return_value.ask.return_value = "deepseek"
        result = edit_single_param("generate", "provider", "deepseek", {}, {"provider": "deepseek"})
        assert result == "deepseek"


class TestIntegration:
    """集成测试"""

    @patch("ankigen.cli.interactive.select_command")
    @patch("ankigen.cli.interactive.edit_params_menu")
    @patch("ankigen.cli.interactive.execute_generate")
    @patch("ankigen.cli.interactive.questionary.confirm")
    def test_interactive_mode_flow(
        self, mock_confirm, mock_execute, mock_edit_menu, mock_select_command
    ):
        """测试交互式模式流程"""
        from ankigen.cli.interactive import interactive_mode

        mock_select_command.return_value = "generate"
        mock_edit_menu.return_value = {"input": Path("/test"), "output": Path("/out")}
        mock_execute.return_value = (True, None)
        mock_confirm.return_value.ask.return_value = False  # 不继续

        with contextlib.suppress(SystemExit):
            interactive_mode()  # 可能因为退出而抛出异常

        mock_select_command.assert_called()
        mock_edit_menu.assert_called()
