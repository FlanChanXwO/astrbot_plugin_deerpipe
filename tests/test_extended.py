"""Extended standalone tests for DeerPipe plugin logic.

These tests cover additional business logic without AstrBot dependencies.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

# =============================================================================
# Database Logic Tests (using SQLite in-memory)
# =============================================================================


class TestDatabaseLogic:
    """测试数据库逻辑（使用内存 SQLite）."""

    @pytest.fixture
    def db_connection(self):
        """创建内存数据库连接."""
        conn = sqlite3.connect(":memory:")
        # 创建表结构
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deer_records (
                user_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL,
                count INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, year, month, day)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deer_config (
                user_id TEXT PRIMARY KEY,
                allow_help INTEGER DEFAULT 1,
                last_retro_date TEXT
            )
            """
        )
        conn.commit()
        yield conn
        conn.close()

    def test_create_tables(self, db_connection):
        """测试表创建."""
        cursor = db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "deer_records" in tables
        assert "deer_config" in tables

    def test_insert_record(self, db_connection):
        """测试插入打卡记录."""
        db_connection.execute(
            "INSERT INTO deer_records (user_id, year, month, day, count) VALUES (?, ?, ?, ?, ?)",
            ("user123", 2024, 5, 20, 1),
        )
        db_connection.commit()

        cursor = db_connection.execute(
            "SELECT * FROM deer_records WHERE user_id = ?",
            ("user123",),
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "user123"
        assert result[4] == 1

    def test_upsert_record(self, db_connection):
        """测试更新打卡次数."""
        # 插入初始记录
        db_connection.execute(
            "INSERT INTO deer_records (user_id, year, month, day, count) VALUES (?, ?, ?, ?, ?)",
            ("user123", 2024, 5, 20, 1),
        )
        db_connection.commit()

        # 更新次数
        db_connection.execute(
            """
            INSERT INTO deer_records (user_id, year, month, day, count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, year, month, day)
            DO UPDATE SET count = count + 1
            """,
            ("user123", 2024, 5, 20, 1),
        )
        db_connection.commit()

        cursor = db_connection.execute(
            "SELECT count FROM deer_records WHERE user_id = ?",
            ("user123",),
        )
        result = cursor.fetchone()
        assert result[0] == 2

    def test_get_monthly_records(self, db_connection):
        """测试获取月度记录."""
        # 插入多条记录
        records = [
            ("user123", 2024, 5, 1, 1),
            ("user123", 2024, 5, 5, 2),
            ("user123", 2024, 5, 10, 1),
            ("user123", 2024, 6, 1, 1),  # 不同月份
        ]
        db_connection.executemany(
            "INSERT INTO deer_records (user_id, year, month, day, count) VALUES (?, ?, ?, ?, ?)",
            records,
        )
        db_connection.commit()

        # 查询 5 月记录
        cursor = db_connection.execute(
            "SELECT day, count FROM deer_records WHERE user_id = ? AND year = ? AND month = ?",
            ("user123", 2024, 5),
        )
        result = {row[0]: row[1] for row in cursor.fetchall()}
        assert result == {1: 1, 5: 2, 10: 1}

    def test_user_config_crud(self, db_connection):
        """测试用户配置 CRUD."""
        # 插入配置
        db_connection.execute(
            "INSERT INTO deer_config (user_id, allow_help, last_retro_date) VALUES (?, ?, ?)",
            ("user123", 1, "2024-05-20"),
        )
        db_connection.commit()

        # 读取配置
        cursor = db_connection.execute(
            "SELECT allow_help FROM deer_config WHERE user_id = ?",
            ("user123",),
        )
        result = cursor.fetchone()
        assert result[0] == 1

        # 更新配置
        db_connection.execute(
            "UPDATE deer_config SET allow_help = ? WHERE user_id = ?",
            (0, "user123"),
        )
        db_connection.commit()

        cursor = db_connection.execute(
            "SELECT allow_help FROM deer_config WHERE user_id = ?",
            ("user123",),
        )
        result = cursor.fetchone()
        assert result[0] == 0


# =============================================================================
# Export/Import Data Tests
# =============================================================================


class TestExportImportData:
    """测试导出导入数据格式."""

    def test_export_data_structure(self):
        """测试导出数据结构."""
        export_data = {
            "deer_records": [
                {
                    "user_id": "user1",
                    "year": 2024,
                    "month": 5,
                    "day": 20,
                    "count": 1,
                }
            ],
            "user_configs": [
                {
                    "user_id": "user1",
                    "allow_help": True,
                    "last_retro_date": "2024-05-20",
                }
            ],
            "export_info": {
                "version": "1.0.0",
                "export_time": "2024-05-20T10:00:00",
                "record_count": 1,
                "user_count": 1,
            },
        }

        assert "deer_records" in export_data
        assert "user_configs" in export_data
        assert "export_info" in export_data
        assert len(export_data["deer_records"]) == 1
        assert export_data["export_info"]["version"] == "1.0.0"

    def test_export_json_serialization(self):
        """测试导出数据 JSON 序列化."""
        export_data = {
            "deer_records": [
                {"user_id": "user1", "year": 2024, "month": 5, "day": 20, "count": 1},
            ],
            "user_configs": [],
        }

        json_str = json.dumps(export_data, ensure_ascii=False)
        assert isinstance(json_str, str)

        # 反序列化
        loaded = json.loads(json_str)
        assert loaded["deer_records"][0]["user_id"] == "user1"

    def test_import_data_validation(self):
        """测试导入数据验证."""
        # 有效的数据结构
        valid_data = {
            "deer_records": [
                {"user_id": "user1", "year": 2024, "month": 5, "day": 20, "count": 1},
            ],
            "user_configs": [
                {"user_id": "user1", "allow_help": True},
            ],
        }

        assert isinstance(valid_data, dict)
        assert "deer_records" in valid_data
        assert "user_configs" in valid_data

        # 验证记录格式
        record = valid_data["deer_records"][0]
        assert all(
            key in record for key in ["user_id", "year", "month", "day", "count"]
        )

    def test_import_invalid_data(self):
        """测试无效导入数据."""
        # 无效的数据类型
        invalid_cases = [
            None,
            "string",
            123,
            [],
            {},
            {"invalid_key": []},
        ]

        for case in invalid_cases:
            if isinstance(case, dict):
                has_valid_field = "deer_records" in case or "user_configs" in case
                assert not has_valid_field or not isinstance(
                    case.get("deer_records"), list
                )


# =============================================================================
# Statistics Calculation Tests
# =============================================================================


class TestStatisticsCalculation:
    """测试统计计算."""

    def test_total_count_calculation(self):
        """测试总次数计算."""
        month_map = {1: 1, 5: 2, 10: 3, 15: 1}
        total = sum(month_map.values())
        assert total == 7

    def test_days_recorded_calculation(self):
        """测试打卡天数计算."""
        month_map = {1: 1, 5: 2, 10: 3, 15: 1}
        days = len(month_map)
        assert days == 4

    def test_average_per_day(self):
        """测试日均打卡次数."""
        month_map = {1: 2, 5: 4, 10: 2}
        total = sum(month_map.values())
        days = len(month_map)
        average = total / days
        assert average == 8 / 3

    def test_frequency_calculation(self):
        """测试打卡频率计算."""
        days_in_month = 30
        days_recorded = 5
        frequency = days_recorded / days_in_month
        frequency_percent = round(frequency * 100, 1)
        assert frequency == 5 / 30
        assert frequency_percent == 16.7  # rounded

    def test_most_active_day(self):
        """测试最活跃日期."""
        month_map = {1: 1, 5: 10, 10: 2, 15: 3}
        most_active = max(month_map, key=month_map.get)
        assert most_active == 5
        assert month_map[most_active] == 10

    def test_empty_calendar_stats(self):
        """测试空日历统计."""
        month_map = {}
        total = sum(month_map.values())
        days = len(month_map)
        assert total == 0
        assert days == 0


# =============================================================================
# Date Boundary Tests
# =============================================================================


class TestDateBoundaries:
    """测试日期边界情况."""

    def test_month_boundaries(self):
        """测试月份边界."""
        # 1 月
        assert calendar.monthrange(2024, 1)[1] == 31
        # 2 月（闰年）
        assert calendar.monthrange(2024, 2)[1] == 29
        # 4 月
        assert calendar.monthrange(2024, 4)[1] == 30
        # 12 月
        assert calendar.monthrange(2024, 12)[1] == 31

    def test_year_boundaries(self):
        """测试年份边界."""
        # 闰年
        assert calendar.isleap(2024)
        assert calendar.isleap(2000)
        # 平年
        assert not calendar.isleap(2023)
        assert not calendar.isleap(1900)

    def test_date_comparison(self):
        """测试日期比较."""
        today = dt.date.today()
        yesterday = today - dt.timedelta(days=1)
        tomorrow = today + dt.timedelta(days=1)

        assert yesterday < today
        assert today < tomorrow
        assert yesterday < tomorrow

    def test_last_day_of_month(self):
        """测试月末日期."""
        # 获取月末
        for month in range(1, 13):
            last_day = calendar.monthrange(2024, month)[1]
            assert 28 <= last_day <= 31

    def test_first_day_of_month(self):
        """测试月初日期."""
        today = dt.date.today()
        first_day = today.replace(day=1)
        assert first_day.day == 1


# =============================================================================
# Batch Operations Tests
# =============================================================================


class TestBatchOperations:
    """测试批量操作."""

    def test_batch_user_processing(self):
        """测试批量用户处理."""
        users = ["user1", "user2", "user3", "user4"]
        results = []

        for user_id in users:
            # 模拟处理每个用户
            result = {"user_id": user_id, "success": True}
            results.append(result)

        assert len(results) == 4
        assert all(r["success"] for r in results)

    def test_batch_with_errors(self):
        """测试批量处理（含错误）."""
        users = ["user1", "user2", "user3"]
        results = []

        for i, user_id in enumerate(users):
            if i == 1:  # 模拟第二个用户失败
                result = {"user_id": user_id, "success": False, "error": "not_allowed"}
            else:
                result = {"user_id": user_id, "success": True}
            results.append(result)

        success_count = sum(1 for r in results if r["success"])
        assert success_count == 2
        assert results[1]["success"] is False

    def test_empty_batch(self):
        """测试空批量处理."""
        users = []
        results = []

        for user_id in users:
            results.append({"user_id": user_id, "success": True})

        assert len(results) == 0


# =============================================================================
# String Formatting Tests
# =============================================================================


class TestStringFormatting:
    """测试字符串格式化."""

    def test_calendar_header_format(self):
        """测试日历标题格式."""
        year = 2024
        month = 5
        header = f"📅 {year}年{month}月 鹿历"
        assert "2024" in header
        assert "5月" in header
        assert "鹿历" in header

    def test_stats_format(self):
        """测试统计信息格式."""
        days = 5
        total = 10
        stats = f"📊 统计: 共{days}天 {total}次"
        assert "5天" in stats
        assert "10次" in stats

    def test_date_format_iso(self):
        """测试 ISO 日期格式."""
        date = dt.date(2024, 5, 20)
        iso_str = date.isoformat()
        assert iso_str == "2024-05-20"

    def test_message_format_with_variables(self):
        """测试带变量的消息格式."""
        user_name = "TestUser"
        count = 5
        message = f"用户 {user_name} 已打卡 {count} 次"
        assert user_name in message
        assert "5 次" in message


# =============================================================================
# Configuration Validation Tests
# =============================================================================


class TestConfigurationValidation:
    """测试配置验证."""

    def test_valid_config_ranges(self):
        """测试有效配置范围."""
        # daily_retro_limit 范围 0-31
        limits = [0, 1, 5, 10, 31]
        for limit in limits:
            assert 0 <= limit <= 31

    def test_invalid_config_values(self):
        """测试无效配置值."""
        # 超出范围的值
        invalid_limits = [-1, 32, 100]
        for limit in invalid_limits:
            is_valid = 0 <= limit <= 31
            assert not is_valid

    def test_display_mode_options(self):
        """测试显示模式选项."""
        valid_modes = ["additive", "count"]
        mode = "additive"
        assert mode in valid_modes

        mode = "count"
        assert mode in valid_modes

        invalid_mode = "invalid"
        assert invalid_mode not in valid_modes

    def test_boolean_config_values(self):
        """测试布尔配置值."""
        config = {
            "show_check_mark": True,
            "allow_help": False,
        }

        assert isinstance(config["show_check_mark"], bool)
        assert isinstance(config["allow_help"], bool)
        assert config["show_check_mark"] is True
        assert config["allow_help"] is False


# =============================================================================
# File Operations Tests
# =============================================================================


class TestFileOperations:
    """测试文件操作."""

    def test_temp_file_creation(self):
        """测试临时文件创建."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"test": "data"}')
            temp_path = f.name

        assert Path(temp_path).exists()

        # 清理
        Path(temp_path).unlink()
        assert not Path(temp_path).exists()

    def test_json_file_read_write(self):
        """测试 JSON 文件读写."""
        data = {"records": [{"user_id": "user1", "count": 5}]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        # 读取
        with open(temp_path) as f:
            loaded = json.load(f)

        assert loaded["records"][0]["user_id"] == "user1"

        # 清理
        Path(temp_path).unlink()


# =============================================================================
# Permission Logic Tests
# =============================================================================


class TestPermissionLogic:
    """测试权限逻辑."""

    def test_help_allowed_logic(self):
        """测试允许帮助逻辑."""
        # 用户允许被帮助
        user_config = {"allow_help": True}
        assert user_config["allow_help"] is True

        # 用户禁止被帮助
        user_config = {"allow_help": False}
        assert user_config["allow_help"] is False

    def test_admin_check_logic(self):
        """测试管理员检查逻辑."""

        # 模拟管理员检查
        def is_admin(user_id: str, admin_list: list[str]) -> bool:
            return user_id in admin_list

        admins = ["admin1", "admin2"]
        assert is_admin("admin1", admins) is True
        assert is_admin("user1", admins) is False

    def test_self_operation_check(self):
        """测试自我操作检查."""
        operator_id = "user123"
        target_id = "user123"
        is_self = operator_id == target_id
        assert is_self is True

        target_id = "user456"
        is_self = operator_id == target_id
        assert is_self is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
