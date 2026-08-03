"""Tests for utils module."""

from __future__ import annotations

from src.infrastructure.utils import (
    extract_mention_user_ids,
    normalize_user_id,
    parse_allow_flag,
    validate_day,
)
from tests.mocks import MockAt


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


class TestExtractMentionUserIds:
    """测试 extract_mention_user_ids 函数."""

    def test_extract_single_at(self):
        """测试提取单个 @."""
        at_list = [MockAt("123456", "User1")]
        result = extract_mention_user_ids(at_list)
        assert result == {"123456"}

    def test_extract_multiple_ats(self):
        """测试提取多个 @."""
        at_list = [
            MockAt("123456", "User1"),
            MockAt("789012", "User2"),
            MockAt("345678", "User3"),
        ]
        result = extract_mention_user_ids(at_list)
        assert result == {"123456", "789012", "345678"}

    def test_extract_empty_list(self):
        """测试空列表."""
        result = extract_mention_user_ids([])
        assert result == set()

    def test_extract_duplicates(self):
        """测试重复的 @ 用户."""
        at_list = [
            MockAt("123456", "User1"),
            MockAt("123456", "User1"),  # 重复
            MockAt("789012", "User2"),
        ]
        result = extract_mention_user_ids(at_list)
        assert result == {"123456", "789012"}

    def test_extract_with_all(self):
        """测试 @全体成员."""
        at_list = [MockAt("all", "全体成员")]
        result = extract_mention_user_ids(at_list)
        assert result == {"all"}


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
        """测试无效值默认为 True."""
        assert parse_allow_flag("invalid") is True
        assert parse_allow_flag(None) is True
        assert parse_allow_flag("") is True
        assert parse_allow_flag([]) is True


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
        assert "超过了1月的最大天数" in error

        is_valid, error = validate_day(30, 2023, 2)
        assert not is_valid
        assert "超过了2月的最大天数" in error

        is_valid, error = validate_day(31, 2024, 4)
        assert not is_valid
        assert "超过了4月的最大天数" in error

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

    def test_day_out_of_range_error_message(self):
        """测试错误消息格式."""
        is_valid, error = validate_day(32, 2024, 1)
        assert not is_valid
        assert "1月" in error
        assert "31" in error
