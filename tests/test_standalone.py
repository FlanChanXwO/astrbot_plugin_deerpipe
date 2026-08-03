"""Comprehensive standalone tests for DeerPipe plugin logic.

These tests do not depend on AstrBot and can be run independently.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass
from typing import Any

import pytest

# =============================================================================
# Core Logic Functions (copied from src for independent testing)
# =============================================================================


def normalize_user_id(user_id: Any) -> str:
    """将用户 ID 归一化为字符串."""
    return str(user_id)


def parse_allow_flag(text: Any) -> bool | None:
    """解析允许标志."""
    if text is None:
        return None

    if isinstance(text, bool):
        return text

    if isinstance(text, str):
        text_lower = text.lower().strip()
        if text_lower in ("true", "1", "yes", "on"):
            return True
        if text_lower in ("false", "0", "no", "off"):
            return False
        return None

    if isinstance(text, int):
        return bool(text)

    return None


def validate_day(day: int, year: int, month: int) -> tuple[bool, str]:
    """验证日期有效性."""
    if not isinstance(day, int) or day < 1:
        return False, f"日期必须 >= 1，当前: {day}"

    try:
        _, max_day = calendar.monthrange(year, month)
    except ValueError as e:
        return False, f"无效的月份: {e}"

    if day > max_day:
        return False, f"日期 {day} 超过了{month}月的最大天数 {max_day}"

    return True, ""


def extract_mention_user_ids(messages: list) -> set[str]:
    """从消息组件列表中提取 @ 的用户 ID."""
    user_ids = set()
    for msg in messages:
        if hasattr(msg, "qq"):
            user_ids.add(str(msg.qq))
    return user_ids


def calculate_consecutive_days(month_map: dict[int, int]) -> int:
    """计算连续打卡天数."""
    if not month_map:
        return 0

    sorted_days = sorted(month_map.keys())
    if not sorted_days:
        return 0

    consecutive = 1
    max_consecutive = 1

    for i in range(1, len(sorted_days)):
        if sorted_days[i] == sorted_days[i - 1] + 1:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 1

    return max_consecutive


def is_leap_year(year: int) -> bool:
    """判断是否为闰年."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def get_days_in_month(year: int, month: int) -> int:
    """获取指定月份的天数."""
    return calendar.monthrange(year, month)[1]


# =============================================================================
# Test Classes
# =============================================================================


class TestNormalizeUserId:
    """测试 normalize_user_id 函数."""

    def test_normalize_string_user_id(self):
        """测试字符串用户ID保持不变."""
        assert normalize_user_id("123456") == "123456"
        assert normalize_user_id("user_abc") == "user_abc"
        assert normalize_user_id("") == ""

    def test_normalize_int_user_id(self):
        """测试整数用户ID转为字符串."""
        assert normalize_user_id(123456) == "123456"
        assert normalize_user_id(0) == "0"
        assert normalize_user_id(-1) == "-1"

    def test_normalize_other_types(self):
        """测试其他类型转为字符串."""
        assert normalize_user_id(123.456) == "123.456"
        assert normalize_user_id([1, 2, 3]) == "[1, 2, 3]"


class TestParseAllowFlag:
    """测试 parse_allow_flag 函数."""

    def test_allow_true_values(self):
        """测试允许为 True 的值."""
        assert parse_allow_flag(True) is True
        assert parse_allow_flag(1) is True
        assert parse_allow_flag("1") is True
        assert parse_allow_flag("true") is True
        assert parse_allow_flag("True") is True
        assert parse_allow_flag("TRUE") is True
        assert parse_allow_flag("yes") is True
        assert parse_allow_flag("on") is True

    def test_allow_false_values(self):
        """测试允许为 False 的值."""
        assert parse_allow_flag(False) is False
        assert parse_allow_flag(0) is False
        assert parse_allow_flag("0") is False
        assert parse_allow_flag("false") is False
        assert parse_allow_flag("False") is False
        assert parse_allow_flag("FALSE") is False
        assert parse_allow_flag("no") is False
        assert parse_allow_flag("off") is False

    def test_allow_invalid_values(self):
        """测试无效值返回 None."""
        assert parse_allow_flag("invalid") is None
        assert parse_allow_flag(None) is None
        assert parse_allow_flag("") is None
        assert parse_allow_flag([]) is None


class TestValidateDay:
    """测试 validate_day 函数."""

    def test_valid_days(self):
        """测试有效的日期."""
        # 2024年1月（31天）
        assert validate_day(1, 2024, 1) == (True, "")
        assert validate_day(31, 2024, 1) == (True, "")
        assert validate_day(15, 2024, 1) == (True, "")

        # 2024年2月（闰年，29天）
        assert validate_day(29, 2024, 2) == (True, "")

        # 2023年2月（平年，28天）
        assert validate_day(28, 2023, 2) == (True, "")

        # 4月（30天）
        assert validate_day(30, 2024, 4) == (True, "")

    def test_invalid_days(self):
        """测试无效的日期."""
        # 小于1
        is_valid, error = validate_day(0, 2024, 1)
        assert not is_valid
        assert "必须 >= 1" in error

        # 大于当月天数
        is_valid, error = validate_day(32, 2024, 1)
        assert not is_valid
        assert "超过了" in error

        is_valid, error = validate_day(30, 2023, 2)
        assert not is_valid
        assert "超过了" in error

        is_valid, error = validate_day(31, 2024, 4)
        assert not is_valid
        assert "超过了" in error

    def test_leap_year(self):
        """测试闰年判断."""
        # 闰年
        assert validate_day(29, 2024, 2)[0] is True
        # 平年
        assert validate_day(29, 2023, 2)[0] is False

    def test_century_leap_year(self):
        """测试世纪闰年."""
        # 1900 不是闰年（能被100但不能被400整除）
        assert validate_day(29, 1900, 2)[0] is False
        # 2000 是闰年（能被400整除）
        assert validate_day(29, 2000, 2)[0] is True

    def test_invalid_month(self):
        """测试无效月份."""
        is_valid, error = validate_day(15, 2024, 13)
        assert not is_valid

        is_valid, error = validate_day(15, 2024, 0)
        assert not is_valid


class TestExtractMentionUserIds:
    """测试 extract_mention_user_ids 函数."""

    def test_extract_single_at(self):
        """测试提取单个 @."""

        @dataclass
        class MockAt:
            qq: str

        at_list = [MockAt("123456")]
        result = extract_mention_user_ids(at_list)
        assert result == {"123456"}

    def test_extract_multiple_ats(self):
        """测试提取多个 @."""

        @dataclass
        class MockAt:
            qq: str

        at_list = [MockAt("123456"), MockAt("789012"), MockAt("345678")]
        result = extract_mention_user_ids(at_list)
        assert result == {"123456", "789012", "345678"}

    def test_extract_empty_list(self):
        """测试空列表."""
        result = extract_mention_user_ids([])
        assert result == set()

    def test_extract_with_all(self):
        """测试 @全体成员."""

        @dataclass
        class MockAt:
            qq: str

        at_list = [MockAt("all")]
        result = extract_mention_user_ids(at_list)
        assert result == {"all"}


class TestCalculateConsecutiveDays:
    """测试计算连续打卡天数."""

    def test_empty_calendar(self):
        """测试空日历."""
        assert calculate_consecutive_days({}) == 0

    def test_single_day(self):
        """测试单日."""
        assert calculate_consecutive_days({5: 1}) == 1

    def test_consecutive_days(self):
        """测试连续打卡."""
        # 连续 3 天
        month_map = {1: 1, 2: 1, 3: 1}
        assert calculate_consecutive_days(month_map) == 3

    def test_non_consecutive_days(self):
        """测试非连续打卡."""
        # 第1天和第3天，不连续
        month_map = {1: 1, 3: 1}
        assert calculate_consecutive_days(month_map) == 1

    def test_multiple_consecutive_segments(self):
        """测试多段连续."""
        # 1-3 连续，5-7 连续，取最大
        month_map = {1: 1, 2: 1, 3: 1, 5: 1, 6: 1, 7: 1}
        assert calculate_consecutive_days(month_map) == 3

    def test_mixed_consecutive(self):
        """测试混合连续."""
        # 1-4(连续), 6  -> 1-4是4天连续，6是1天连续
        month_map = {1: 1, 2: 2, 3: 1, 4: 1, 6: 1}
        assert calculate_consecutive_days(month_map) == 4


class TestIsLeapYear:
    """测试闰年判断."""

    def test_common_leap_years(self):
        """测试普通闰年."""
        assert is_leap_year(2024) is True
        assert is_leap_year(2020) is True
        assert is_leap_year(2004) is True

    def test_common_non_leap_years(self):
        """测试普通平年."""
        assert is_leap_year(2023) is False
        assert is_leap_year(2022) is False
        assert is_leap_year(2021) is False

    def test_century_years(self):
        """测试世纪年."""
        assert is_leap_year(1900) is False  # 能被100但不能被400整除
        assert is_leap_year(2100) is False
        assert is_leap_year(2000) is True  # 能被400整除
        assert is_leap_year(2400) is True


class TestGetDaysInMonth:
    """测试获取月份天数."""

    def test_31_day_months(self):
        """测试31天的月份."""
        assert get_days_in_month(2024, 1) == 31  # 一月
        assert get_days_in_month(2024, 3) == 31  # 三月
        assert get_days_in_month(2024, 5) == 31  # 五月
        assert get_days_in_month(2024, 7) == 31  # 七月
        assert get_days_in_month(2024, 8) == 31  # 八月
        assert get_days_in_month(2024, 10) == 31  # 十月
        assert get_days_in_month(2024, 12) == 31  # 十二月

    def test_30_day_months(self):
        """测试30天的月份."""
        assert get_days_in_month(2024, 4) == 30  # 四月
        assert get_days_in_month(2024, 6) == 30  # 六月
        assert get_days_in_month(2024, 9) == 30  # 九月
        assert get_days_in_month(2024, 11) == 30  # 十一月

    def test_february(self):
        """测试二月."""
        assert get_days_in_month(2024, 2) == 29  # 闰年
        assert get_days_in_month(2023, 2) == 28  # 平年
        assert get_days_in_month(2000, 2) == 29  # 世纪闰年
        assert get_days_in_month(1900, 2) == 28  # 世纪平年


# =============================================================================
# Business Logic Tests
# =============================================================================


@dataclass
class DeerRecord:
    """打卡记录数据类."""

    user_id: str
    year: int
    month: int
    day: int
    count: int = 1


@dataclass
class UserConfig:
    """用户配置数据类."""

    user_id: str
    allow_help: bool = True
    last_retro_date: str | None = None


class TestDeerRecordLogic:
    """测试打卡记录业务逻辑."""

    def test_record_creation(self):
        """测试记录创建."""
        today = dt.date.today()
        record = DeerRecord(
            user_id="123456",
            year=today.year,
            month=today.month,
            day=today.day,
        )

        assert record.user_id == "123456"
        assert record.year == today.year
        assert record.month == today.month
        assert record.day == today.day
        assert record.count == 1

    def test_record_with_count(self):
        """测试带次数的记录."""
        record = DeerRecord(
            user_id="123456",
            year=2024,
            month=5,
            day=20,
            count=5,
        )

        assert record.count == 5


class TestUserConfigLogic:
    """测试用户配置业务逻辑."""

    def test_default_config(self):
        """测试默认配置."""
        config = UserConfig(user_id="123456")

        assert config.user_id == "123456"
        assert config.allow_help is True
        assert config.last_retro_date is None

    def test_custom_config(self):
        """测试自定义配置."""
        today = dt.date.today().isoformat()
        config = UserConfig(
            user_id="123456",
            allow_help=False,
            last_retro_date=today,
        )

        assert config.allow_help is False
        assert config.last_retro_date == today


# =============================================================================
# Configuration Tests
# =============================================================================


class TestPluginConfigStructure:
    """测试插件配置结构."""

    def test_default_config(self):
        """测试默认配置结构."""
        config = {
            "ai_behavior": {
                "allow_ai_help_deer": True,
                "allow_ai_be_deered": False,
                "allow_ai_help_self": True,
                "custom_prompt": "",
            },
            "limits": {
                "daily_retro_limit": 1,
            },
            "calendar": {
                "count_display_mode": "additive",
                "show_check_mark": True,
            },
            "custom_groups": [],
        }

        assert config["ai_behavior"]["allow_ai_help_deer"] is True
        assert config["limits"]["daily_retro_limit"] == 1
        assert config["calendar"]["count_display_mode"] == "additive"

    def test_custom_groups_structure(self):
        """测试自定义命令组配置结构."""
        config = {
            "custom_groups": [
                {
                    "group_name": "测试组",
                    "description": "测试命令组",
                    "priority": 0,
                    "show_in_menu": True,
                    "commands": [
                        {
                            "command_name": "test",
                            "pattern": "",
                            "trigger_type": "command",
                            "sub_commands": ["t"],
                            "is_admin": False,
                            "show_in_menu": True,
                        }
                    ],
                }
            ]
        }

        group = config["custom_groups"][0]
        assert group["group_name"] == "测试组"
        assert group["priority"] == 0
        assert len(group["commands"]) == 1

        cmd = group["commands"][0]
        assert cmd["command_name"] == "test"
        assert cmd["trigger_type"] == "command"
        assert "t" in cmd["sub_commands"]


# =============================================================================
# Calendar Logic Tests
# =============================================================================


class TestCalendarLogic:
    """测试日历逻辑."""

    def test_calendar_stats_calculation(self):
        """测试日历统计计算."""
        month_map = {1: 1, 2: 2, 3: 1, 5: 3}

        total_count = sum(month_map.values())
        days_recorded = len(month_map)

        assert total_count == 7  # 1+2+1+3
        assert days_recorded == 4

    def test_frequency_calculation(self):
        """测试打卡频率计算."""
        month_map = {1: 1, 15: 1}
        days_in_month = 30

        frequency = len(month_map) / days_in_month
        assert frequency == 2 / 30

    def test_most_active_day(self):
        """测试最活跃日期."""
        month_map = {1: 1, 5: 5, 10: 2, 15: 3}

        most_active = max(month_map, key=month_map.get)
        assert most_active == 5
        assert month_map[most_active] == 5


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
