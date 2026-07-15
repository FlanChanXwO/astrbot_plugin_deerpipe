"""Tests for database module."""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

import pytest

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from infrastructure.persistence.database import DatabaseManager


@pytest.fixture
def db_manager():
    """创建临时的 DatabaseManager 实例."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    manager = DatabaseManager(db_path)

    yield manager

    # 清理
    import os

    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


class TestDatabaseInitialization:
    """测试数据库初始化."""

    @pytest.mark.asyncio
    async def test_database_tables_created(self, db_manager):
        """测试数据库表是否正确创建."""
        db = await db_manager.get_connection()
        try:
            # 检查 deer_records 表是否存在
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='deer_records'"
            )
            result = await cursor.fetchone()
            assert result is not None

            # 检查 deer_config 表是否存在
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='deer_config'"
            )
            result = await cursor.fetchone()
            assert result is not None
        finally:
            await db.close()


class TestUserConfig:
    """测试用户配置相关操作."""

    @pytest.mark.asyncio
    async def test_ensure_user_config_creates_new(self, db_manager):
        """测试确保用户配置会创建新用户."""
        db = await db_manager.get_connection()
        try:
            await db_manager.ensure_user_config(db, "user123")

            cursor = await db.execute(
                "SELECT user_id, allow_help FROM deer_config WHERE user_id = ?",
                ("user123",),
            )
            result = await cursor.fetchone()
            assert result is not None
            assert result[0] == "user123"
            assert result[1] == 1  # 默认 allow_help = True
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_ensure_user_config_idempotent(self, db_manager):
        """测试确保用户配置是幂等的."""
        db = await db_manager.get_connection()
        try:
            await db_manager.ensure_user_config(db, "user123")
            await db_manager.ensure_user_config(db, "user123")

            cursor = await db.execute(
                "SELECT COUNT(*) FROM deer_config WHERE user_id = ?",
                ("user123",),
            )
            result = await cursor.fetchone()
            assert result[0] == 1  # 只应有一条记录
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_is_help_allowed_default(self, db_manager):
        """测试默认允许帮助设置."""
        db = await db_manager.get_connection()
        try:
            # 未创建用户时应该返回默认 True
            result = await db_manager.is_help_allowed(db, "new_user")
            assert result is True
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_set_help_allowed(self, db_manager):
        """测试设置允许帮助."""
        db = await db_manager.get_connection()
        try:
            await db_manager.ensure_user_config(db, "user123")

            # 设置为不允许
            await db_manager.set_help_allowed(db, "user123", False)
            result = await db_manager.is_help_allowed(db, "user123")
            assert result is False

            # 设置为允许
            await db_manager.set_help_allowed(db, "user123", True)
            result = await db_manager.is_help_allowed(db, "user123")
            assert result is True
        finally:
            await db.close()


class TestAttendanceRecording:
    """测试打卡记录相关操作."""

    @pytest.mark.asyncio
    async def test_record_attendance_new(self, db_manager):
        """测试新打卡记录."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, today.day
            )

            cursor = await db.execute(
                "SELECT count FROM deer_records WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
                ("user123", today.year, today.month, today.day),
            )
            result = await cursor.fetchone()
            assert result is not None
            assert result[0] == 1
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_record_attendance_increment(self, db_manager):
        """测试打卡次数累加."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()

            # 第一次打卡
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, today.day
            )
            # 第二次打卡
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, today.day
            )

            cursor = await db.execute(
                "SELECT count FROM deer_records WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
                ("user123", today.year, today.month, today.day),
            )
            result = await cursor.fetchone()
            assert result[0] == 2
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_has_record_today(self, db_manager):
        """测试检查今日是否有记录."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()

            # 没有记录时
            has_record = await db_manager.has_record_today(db, "user123")
            assert has_record is False

            # 添加记录后
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, today.day
            )
            has_record = await db_manager.has_record_today(db, "user123")
            assert has_record is True
        finally:
            await db.close()


class TestCalendarData:
    """测试日历数据相关操作."""

    @pytest.mark.asyncio
    async def test_get_calendar_data_empty(self, db_manager):
        """测试获取空的日历数据."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()
            data = await db_manager.get_calendar_data(
                db, "user123", today.year, today.month
            )
            assert data == {}
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_get_calendar_data_with_records(self, db_manager):
        """测试获取有记录的日历数据."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()

            # 添加多条记录
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, 1
            )
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, 5
            )
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, 5
            )  # 同一天两次
            await db_manager.record_attendance(
                db, "user123", today.year, today.month, 10
            )

            data = await db_manager.get_calendar_data(
                db, "user123", today.year, today.month
            )
            assert data == {1: 1, 5: 2, 10: 1}
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_get_calendar_data_different_months(self, db_manager):
        """测试不同月份的日历数据隔离."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()

            # 添加1月的记录
            await db_manager.record_attendance(db, "user123", today.year, 1, 1)
            # 添加2月的记录
            await db_manager.record_attendance(db, "user123", today.year, 2, 1)

            # 查询1月
            data_jan = await db_manager.get_calendar_data(db, "user123", today.year, 1)
            assert data_jan == {1: 1}

            # 查询2月
            data_feb = await db_manager.get_calendar_data(db, "user123", today.year, 2)
            assert data_feb == {1: 1}
        finally:
            await db.close()


class TestRetroCount:
    """测试补打卡次数相关操作."""

    @pytest.mark.asyncio
    async def test_get_today_retro_count_empty(self, db_manager):
        """测试获取空的今日补打卡次数."""
        db = await db_manager.get_connection()
        try:
            count = await db_manager.get_today_retro_count(db, "user123")
            assert count == 0
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_increment_retro_count(self, db_manager):
        """测试增加补打卡次数."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()

            # 增加一次
            await db_manager.increment_retro_count(db, "user123", today.isoformat())
            count = await db_manager.get_today_retro_count(db, "user123")
            assert count == 1

            # 再增加一次
            await db_manager.increment_retro_count(db, "user123", today.isoformat())
            count = await db_manager.get_today_retro_count(db, "user123")
            assert count == 2
        finally:
            await db.close()


class TestBatchOperations:
    """测试批量操作."""

    @pytest.mark.asyncio
    async def test_get_calendar_data_batch(self, db_manager):
        """测试批量获取日历数据."""
        db = await db_manager.get_connection()
        try:
            today = dt.date.today()

            # 为多个用户添加记录
            await db_manager.record_attendance(db, "user1", today.year, today.month, 1)
            await db_manager.record_attendance(db, "user1", today.year, today.month, 2)
            await db_manager.record_attendance(db, "user2", today.year, today.month, 1)
            await db_manager.record_attendance(db, "user3", today.year, today.month, 5)

            # 批量查询
            data_map = await db_manager.get_calendar_data_batch(
                db, ["user1", "user2", "user3"], today.year, today.month
            )

            assert data_map["user1"] == {1: 1, 2: 1}
            assert data_map["user2"] == {1: 1}
            assert data_map["user3"] == {5: 1}
        finally:
            await db.close()
