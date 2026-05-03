"""Mock data and fixtures for tests."""

from __future__ import annotations

import datetime as dt
from typing import Any


class MockDataFactory:
    """Mock 数据工厂，用于生成测试数据."""

    @staticmethod
    def create_user_config(
        user_id: str = "123456",
        allow_help: bool = True,
        last_retro_date: str | None = None,
    ) -> dict[str, Any]:
        """创建用户配置数据.

        Args:
            user_id: 用户ID
            allow_help: 是否允许被帮打卡
            last_retro_date: 上次补打卡日期

        Returns:
            用户配置字典
        """
        return {
            "user_id": user_id,
            "allow_help": allow_help,
            "last_retro_date": last_retro_date or dt.date.today().isoformat(),
        }

    @staticmethod
    def create_deer_record(
        user_id: str = "123456",
        year: int | None = None,
        month: int | None = None,
        day: int | None = None,
        count: int = 1,
    ) -> dict[str, Any]:
        """创建打卡记录数据.

        Args:
            user_id: 用户ID
            year: 年份，默认为当前年
            month: 月份，默认为当前月
            day: 日期，默认为今天
            count: 打卡次数

        Returns:
            打卡记录字典
        """
        today = dt.date.today()
        return {
            "user_id": user_id,
            "year": year or today.year,
            "month": month or today.month,
            "day": day or today.day,
            "count": count,
        }

    @staticmethod
    def create_calendar_data(
        year: int | None = None,
        month: int | None = None,
        records: dict[int, int] | None = None,
    ) -> dict[int, int]:
        """创建日历数据.

        Args:
            year: 年份
            month: 月份
            records: 日期到打卡次数的映射

        Returns:
            日历数据字典
        """
        if records is not None:
            return records

        today = dt.date.today()
        # 默认生成一些随机的打卡记录
        return {
            1: 1,
            3: 2,
            5: 1,
            10: 3,
            15: 1,
            today.day: 1,
        }

    @staticmethod
    def create_plugin_config(
        ai_behavior: dict | None = None,
        limits: dict | None = None,
        calendar: dict | None = None,
        custom_groups: list | None = None,
    ) -> dict[str, Any]:
        """创建插件配置数据.

        Args:
            ai_behavior: AI 行为配置
            limits: 限制配置
            calendar: 日历配置
            custom_groups: 自定义命令组配置

        Returns:
            插件配置字典
        """
        return {
            "ai_behavior": ai_behavior
            or {
                "allow_ai_help_deer": True,
                "allow_ai_be_deered": False,
                "allow_ai_help_self": True,
                "custom_prompt": "",
            },
            "limits": limits or {"daily_retro_limit": 1},
            "calendar": calendar
            or {
                "count_display_mode": "additive",
                "show_check_mark": True,
            },
            "custom_groups": custom_groups or [],
        }

    @staticmethod
    def create_export_data(
        user_count: int = 2,
        record_count: int = 10,
    ) -> dict[str, Any]:
        """创建导出数据.

        Args:
            user_count: 用户数量
            record_count: 记录数量

        Returns:
            导出数据字典
        """
        today = dt.date.today()

        user_configs = []
        for i in range(user_count):
            user_configs.append(
                {
                    "user_id": f"user_{i}",
                    "allow_help": True,
                    "last_retro_date": today.isoformat(),
                }
            )

        deer_records = []
        for i in range(record_count):
            user_idx = i % user_count
            deer_records.append(
                {
                    "user_id": f"user_{user_idx}",
                    "year": today.year,
                    "month": today.month,
                    "day": (i % 28) + 1,
                    "count": (i % 3) + 1,
                }
            )

        return {
            "deer_records": deer_records,
            "user_configs": user_configs,
            "export_info": {
                "version": "1.0.0",
                "export_time": dt.datetime.now().isoformat(),
                "record_count": record_count,
                "user_count": user_count,
            },
        }


class MockAstrMessageEvent:
    """模拟 AstrMessageEvent 消息事件."""

    def __init__(
        self,
        sender_id: str = "123456",
        sender_name: str = "TestUser",
        message_text: str = "",
        is_group: bool = True,
        is_admin_flag: bool = False,
    ):
        self._sender_id = sender_id
        self._sender_name = sender_name
        self._message_text = message_text
        self._is_group = is_group
        self._is_admin_flag = is_admin_flag
        self._platform_name = "aiocqhttp"
        self._self_id = "bot_123"
        self.message_obj = MockMessageObject(message_text)

    def get_sender_id(self) -> str:
        return self._sender_id

    def get_sender_name(self) -> str:
        return self._sender_name

    def get_platform_name(self) -> str:
        return self._platform_name

    def get_self_id(self) -> str | None:
        return self._self_id

    def is_admin(self) -> bool:
        return self._is_admin_flag

    def get_message_type(self):
        from astrbot.core.platform.message_type import MessageType

        return (
            MessageType.GROUP_MESSAGE
            if self._is_group
            else MessageType.FRIEND_MESSAGE
        )

    def get_messages(self):
        return [MockPlain(self._message_text)]

    def plain_result(self, text: str):
        return MockResult(text)

    def image_result(self, url: str):
        return MockResult(f"[Image: {url}]")

    def chain_result(self, components: list):
        return MockResult(f"[Chain: {len(components)} components]")

    def make_result(self):
        return MockResultBuilder()

    def set_extra(self, key: str, value: Any) -> None:
        pass

    def get_extra(self, key: str) -> Any:
        return None


class MockMessageObject:
    """模拟消息对象."""

    def __init__(self, text: str = ""):
        self.message = [MockPlain(text)]


class MockPlain:
    """模拟纯文本消息组件."""

    def __init__(self, text: str):
        self.text = text

    def __repr__(self):
        return f"Plain({self.text!r})"


class MockAt:
    """模拟 @ 消息组件."""

    def __init__(self, qq: str, name: str = ""):
        self.qq = qq
        self.name = name

    def __repr__(self):
        return f"At(qq={self.qq!r}, name={self.name!r})"


class MockResult:
    """模拟发送结果."""

    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return self.text


class MockResultBuilder:
    """模拟结果构建器."""

    def __init__(self):
        self._message = ""
        self._image_url = ""

    def message(self, text: str):
        self._message = text
        return self

    def url_image(self, url: str):
        self._image_url = url
        return self

    def build(self):
        return f"{self._message} [Image: {self._image_url}]"


class MockHtmlRenderer:
    """模拟 HTML 渲染器."""

    async def render(
        self,
        html: str,
        payload: dict | None = None,
        return_url: bool = True,
        options: dict | None = None,
    ) -> str:
        """模拟渲染 HTML 为图片.

        实际返回一个模拟的图片 URL，而不是真正渲染。
        """
        return "mock://rendered_image.png"
