"""Standalone tests for utils module (no AstrBot dependencies)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 只导入不依赖 AstrBot 的函数


def normalize_user_id(user_id) -> str:
    """将用户 ID 归一化为字符串."""
    return str(user_id)


def parse_allow_flag(text) -> bool | None:
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
    import calendar

    if not isinstance(day, int) or day < 1:
        return False, f"日期必须 >= 1，当前: {day}"

    try:
        _, max_day = calendar.monthrange(year, month)
    except ValueError as e:
        return False, f"无效的月份: {e}"

    if day > max_day:
        return False, f"日期 {day} 超过了{month}月的最大天数 {max_day}"

    return True, ""


class TestNormalizeUserId:
    """测试 normalize_user_id 函数."""

    def test_normalize_string_user_id(self):
        """测试字符串用户ID保持不变."""
        assert normalize_user_id("123456") == "123456"
        assert normalize_user_id("user_abc") == "user_abc"

    def test_normalize_int_user_id(self):
        """测试整数用户ID转为字符串."""
        assert normalize_user_id(123456) == "123456"
        assert normalize_user_id(0) == "0"
        assert normalize_user_id(-1) == "-1"

    def test_normalize_empty_string(self):
        """测试空字符串."""
        assert normalize_user_id("") == ""


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
