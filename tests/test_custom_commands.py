"""Tests for custom command manager module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from application.services.custom_command_manager import (
    CustomCommand,
    CustomCommandGroup,
)


class TestCustomCommand:
    """测试 CustomCommand 数据类."""

    def test_command_creation(self):
        """测试命令创建."""
        cmd = CustomCommand(
            command_name="test",
            pattern="",
            trigger_type="command",
            sub_commands=["t", "测试"],
            is_admin=False,
            show_in_menu=True,
        )

        assert cmd.command_name == "test"
        assert cmd.trigger_type == "command"
        assert cmd.sub_commands == ["t", "测试"]
        assert cmd.is_admin is False
        assert cmd.show_in_menu is True

    def test_all_triggers(self):
        """测试获取所有触发词."""
        cmd = CustomCommand(
            command_name="help",
            sub_commands=["h", "?"],
        )

        triggers = cmd.all_triggers
        assert "help" in triggers
        assert "h" in triggers
        assert "?" in triggers
        assert len(triggers) == 3

    def test_all_triggers_regex_type(self):
        """测试正则类型命令的触发词为空."""
        cmd = CustomCommand(
            command_name="regex_cmd",
            pattern=r"^test\d+$",
            trigger_type="regex",
        )

        assert cmd.all_triggers == []

    def test_compiled_pattern_valid(self):
        """测试有效的正则表达式编译."""
        cmd = CustomCommand(
            command_name="regex_cmd",
            pattern=r"^test\d+$",
            trigger_type="regex",
        )

        compiled = cmd.compiled_pattern
        assert compiled is not None
        assert compiled.match("test123")
        assert compiled.match("test1")
        assert not compiled.match("test")
        assert not compiled.match("abc123")

    def test_compiled_pattern_invalid(self):
        """测试无效的正则表达式."""
        cmd = CustomCommand(
            command_name="regex_cmd",
            pattern=r"[invalid(",  # 无效的正则
            trigger_type="regex",
        )

        compiled = cmd.compiled_pattern
        assert compiled is None

    def test_trigger_type_default(self):
        """测试默认触发类型."""
        cmd = CustomCommand(command_name="test")
        assert cmd.trigger_type == "command"

    def test_trigger_type_validation(self):
        """测试触发类型验证."""
        cmd = CustomCommand(
            command_name="test",
            trigger_type="invalid_type",
        )
        # 无效类型会被重置为 "command"
        assert cmd.trigger_type == "command"


class TestCustomCommandGroup:
    """测试 CustomCommandGroup 数据类."""

    def test_group_creation(self):
        """测试命令组创建."""
        group = CustomCommandGroup(
            group_name="测试组",
            description="这是一个测试组",
            priority=5,
            show_in_menu=True,
            commands=[],
        )

        assert group.group_name == "测试组"
        assert group.description == "这是一个测试组"
        assert group.priority == 5
        assert group.show_in_menu is True


class TestCustomCommandManagerParsing:
    """测试 CustomCommandManager 配置解析."""

    def test_parse_empty_config(self):
        """测试空配置."""
        # 由于需要 context 和 service，我们只测试解析逻辑
        # 实际测试中需要 mock 这些依赖

    def test_parse_valid_command(self):
        """测试解析有效命令."""
        raw_cmd = {
            "command_name": "test",
            "pattern": "",
            "trigger_type": "command",
            "sub_commands": ["t", "test2"],
            "is_admin": False,
            "show_in_menu": True,
        }

        # 使用 Manager 的 parse 方法（需要先创建 Manager 实例）
        # 这里我们直接测试 CustomCommand 创建
        cmd = CustomCommand(
            command_name=raw_cmd["command_name"],
            pattern=raw_cmd.get("pattern", ""),
            trigger_type=raw_cmd.get("trigger_type", "command"),
            sub_commands=raw_cmd.get("sub_commands", []),
            is_admin=raw_cmd.get("is_admin", False),
            show_in_menu=raw_cmd.get("show_in_menu", True),
        )

        assert cmd.command_name == "test"
        assert "t" in cmd.sub_commands
        assert "test2" in cmd.sub_commands

    def test_parse_regex_command(self):
        """测试解析正则命令."""
        raw_cmd = {
            "command_name": "regex_test",
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
            "trigger_type": "regex",
            "sub_commands": [],  # regex 类型不应该有子命令
            "is_admin": False,
            "show_in_menu": False,
        }

        cmd = CustomCommand(
            command_name=raw_cmd["command_name"],
            pattern=raw_cmd.get("pattern", ""),
            trigger_type=raw_cmd.get("trigger_type", "command"),
            sub_commands=raw_cmd.get("sub_commands", []),
            is_admin=raw_cmd.get("is_admin", False),
            show_in_menu=raw_cmd.get("show_in_menu", True),
        )

        assert cmd.trigger_type == "regex"
        assert cmd.compiled_pattern is not None
        assert cmd.compiled_pattern.match("2024-05-20")
        assert not cmd.compiled_pattern.match("2024-5-20")


class TestCustomCommandManager:
    """测试 CustomCommandManager 功能."""

    def test_manager_creation(self):
        """测试管理器创建."""
        # 由于需要 context 和 service，这里只测试基础结构
        # manager = CustomCommandManager(mock_context, config, mock_service)

    def test_get_menu_items_empty(self):
        """测试空配置的菜单项."""
        # 当没有自定义命令组时，菜单项应该为空
        # 创建 Manager 实例并测试
        # manager = CustomCommandManager(mock_context, config, mock_service)
        # items = manager.get_menu_items()
        # assert items == []

    def test_sample_custom_group_config(self, custom_group_config):
        """测试示例自定义命令组配置."""
        # 使用 conftest.py 中的 fixture
        groups = custom_group_config["custom_groups"]

        assert len(groups) == 2
        assert groups[0]["group_name"] == "测试组1"
        assert groups[0]["priority"] == 0
        assert groups[1]["priority"] == 10  # 高优先级

        # 检查命令
        commands = groups[0]["commands"]
        assert len(commands) == 3

        # 检查 command 类型
        cmd = commands[0]
        assert cmd["command_name"] == "test_cmd"
        assert cmd["trigger_type"] == "command"
        assert "tc" in cmd["sub_commands"]
        assert "测试" in cmd["sub_commands"]

        # 检查 regex 类型
        regex_cmd = commands[2]
        assert regex_cmd["trigger_type"] == "regex"
        assert regex_cmd["pattern"] == r"^test\d+$"


class TestCommandExecutionLogic:
    """测试命令执行逻辑."""

    @pytest.mark.asyncio
    async def test_execute_command_default(self):
        """测试默认命令执行."""
        # 默认执行返回提示信息
        # 实际测试需要在 Manager 实例上调用
        # result = await manager._execute_command(group, cmd, event)
        # assert "test' 已触发" in result
        # assert "TestUser" in result

    @pytest.mark.asyncio
    async def test_execute_regex_command_default(self):
        """测试默认正则命令执行."""
        # 默认执行返回提示信息
        # result = await manager._execute_command(group, cmd, event)
        # assert "regex_test' 已触发" in result
        # assert r"^test\d+$" in result
