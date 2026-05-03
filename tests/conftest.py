"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import asyncio
import datetime as dt
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.mocks import (
    MockAstrMessageEvent,
    MockDataFactory,
    MockHtmlRenderer,
)


@pytest.fixture
def event_loop():
    """创建事件循环."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_data_factory():
    """提供 MockDataFactory 实例."""
    return MockDataFactory()


@pytest.fixture
def mock_event():
    """提供默认的 MockAstrMessageEvent 实例."""
    return MockAstrMessageEvent()


@pytest.fixture
def mock_group_event():
    """提供群聊 MockAstrMessageEvent 实例."""
    return MockAstrMessageEvent(is_group=True)


@pytest.fixture
def mock_private_event():
    """提供私聊 MockAstrMessageEvent 实例."""
    return MockAstrMessageEvent(is_group=False)


@pytest.fixture
def mock_admin_event():
    """提供管理员 MockAstrMessageEvent 实例."""
    return MockAstrMessageEvent(is_admin_flag=True)


@pytest.fixture
def mock_html_renderer():
    """提供 MockHtmlRenderer 实例."""
    return MockHtmlRenderer()


@pytest.fixture
def plugin_config():
    """提供默认插件配置."""
    return MockDataFactory.create_plugin_config()


@pytest.fixture
def temp_db_path():
    """提供临时数据库路径."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    # 清理
    import os

    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def sample_calendar_data():
    """提供示例日历数据."""
    return {
        1: 1,
        3: 2,
        5: 1,
        10: 3,
        15: 1,
        20: 2,
        25: 1,
    }


@pytest.fixture
def sample_user_config():
    """提供示例用户配置."""
    return MockDataFactory.create_user_config(
        user_id="123456",
        allow_help=True,
    )


@pytest.fixture
def sample_export_data():
    """提供示例导出数据."""
    return MockDataFactory.create_export_data(
        user_count=3,
        record_count=15,
    )


@pytest.fixture
def custom_group_config():
    """提供自定义命令组配置."""
    return {
        "custom_groups": [
            {
                "group_name": "测试组1",
                "description": "测试命令组",
                "priority": 0,
                "show_in_menu": True,
                "commands": [
                    {
                        "command_name": "test_cmd",
                        "pattern": "",
                        "trigger_type": "command",
                        "sub_commands": ["tc", "测试"],
                        "is_admin": False,
                        "show_in_menu": True,
                    },
                    {
                        "command_name": "admin_cmd",
                        "pattern": "",
                        "trigger_type": "command",
                        "sub_commands": [],
                        "is_admin": True,
                        "show_in_menu": True,
                    },
                    {
                        "command_name": "regex_cmd",
                        "pattern": r"^test\d+$",
                        "trigger_type": "regex",
                        "sub_commands": [],
                        "is_admin": False,
                        "show_in_menu": False,
                    },
                ],
            },
            {
                "group_name": "测试组2",
                "description": "低优先级测试组",
                "priority": 10,
                "show_in_menu": True,
                "commands": [
                    {
                        "command_name": "low_priority",
                        "pattern": "",
                        "trigger_type": "command",
                        "sub_commands": [],
                        "is_admin": False,
                        "show_in_menu": True,
                    }
                ],
            },
        ]
    }


class AsyncContextManagerMock:
    """异步上下文管理器 mock."""

    def __init__(self, return_value: Any = None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_mock():
    """提供 AsyncContextManagerMock 工厂."""
    return AsyncContextManagerMock
