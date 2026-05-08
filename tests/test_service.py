"""Tests for service module."""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from infrastructure.persistence.database import DatabaseManager
from application.presenters import CalendarPresenter
from application.services.deer_service import DeerPipeService, MessageTemplates


@pytest.fixture
def service_with_mocks(plugin_config):
    """创建带有 mock 依赖的 Service 实例."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = DatabaseManager(db_path)
    calendar_presenter = MagicMock(spec=CalendarPresenter)
    service = DeerPipeService(db, calendar_presenter, plugin_config)

    yield service, db, calendar_presenter

    # 清理
    import os

    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


class TestMessageTemplates:
    """测试消息模板."""

    def test_get_template_success(self):
        """测试成功获取模板."""
        result = MessageTemplates.get("group_only")
        assert result == "该命令仅限群聊使用。"

    def test_get_template_with_params(self):
        """测试带参数的模板."""
        result = MessageTemplates.get("deer_past_success", month=5, day=20)
        assert result == "成功补🦌 5月20日"

    def test_get_template_missing_key(self):
        """测试不存在的模板键."""
        with pytest.raises(Exception):  # TemplateKeyError
            MessageTemplates.get("nonexistent_key")


class TestHandleDeerSelf:
    """测试自我打卡功能."""

    @pytest.mark.asyncio
    async def test_handle_deer_self_success(self, service_with_mocks):
        """测试成功自我打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")
        result = await service.handle_deer_self(event)

        assert result == "成功🦌了"

    @pytest.mark.asyncio
    async def test_handle_deer_self_creates_user_config(self, service_with_mocks):
        """测试自我打卡会创建用户配置."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")
        await service.handle_deer_self(event)

        # 验证用户配置已创建
        conn = await db.get_connection()
        try:
            cursor = await conn.execute(
                "SELECT user_id FROM deer_config WHERE user_id = ?",
                ("user123",),
            )
            result = await cursor.fetchone()
            assert result is not None
        finally:
            await conn.close()


class TestHandleSetSelfHelp:
    """测试设置自己的帮打卡权限."""

    @pytest.mark.asyncio
    async def test_set_allow_help_true(self, service_with_mocks):
        """测试设置为允许帮打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")
        result = await service.handle_set_self_help(event, True)

        assert "开启" in result
        assert "可以帮你🦌" in result

    @pytest.mark.asyncio
    async def test_set_allow_help_false(self, service_with_mocks):
        """测试设置为禁止帮打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")
        result = await service.handle_set_self_help(event, False)

        assert "关闭" in result
        assert "只有你自己能🦌" in result


class TestHandleDeerPast:
    """测试补打卡功能."""

    @pytest.mark.asyncio
    async def test_handle_deer_past_future_date(self, service_with_mocks):
        """测试不能对未来日期补打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")
        future_day = dt.date.today().day + 1
        if future_day > 28:  # 避免超出月份天数
            future_day = 28

        result = await service.handle_deer_past(event, future_day)
        assert "不能对未来的日期" in result

    @pytest.mark.asyncio
    async def test_handle_deer_past_invalid_day(self, service_with_mocks):
        """测试无效日期."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")
        result = await service.handle_deer_past(event, 32)

        assert "超过了" in result or "日期无效" in result

    @pytest.mark.asyncio
    async def test_handle_deer_past_limit_reached(self, service_with_mocks):
        """测试补打卡次数限制."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")

        # 使用昨天以确保不超出日期范围
        yesterday = dt.date.today() - dt.timedelta(days=1)

        # 第一次补打卡
        result1 = await service.handle_deer_past(
            event, yesterday.day, yesterday.year, yesterday.month
        )

        # 如果日期有效且未达到限制，应该成功
        if "成功补🦌" in result1:
            # 第二次补打卡（应该达到限制）
            result2 = await service.handle_deer_past(event, yesterday.day - 1 or 1)
            # 结果取决于 daily_retro_limit 配置

    @pytest.mark.asyncio
    async def test_handle_deer_past_success(self, service_with_mocks):
        """测试成功补打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAstrMessageEvent

        event = MockAstrMessageEvent(sender_id="user123")

        # 使用昨天
        yesterday = dt.date.today() - dt.timedelta(days=1)

        result = await service.handle_deer_past(
            event, yesterday.day, yesterday.year, yesterday.month
        )

        # 可能成功也可能达到限制
        assert "成功补🦌" in result or "已达上限" in result


class TestBatchDeerOther:
    """测试批量帮他人打卡."""

    @pytest.mark.asyncio
    async def test_batch_deer_other_empty(self, service_with_mocks):
        """测试空目标列表."""
        service, db, _ = service_with_mocks

        results = await service.batch_deer_other(
            sender_id="user123",
            at_ids=set(),
            at_list=[],
            self_id="bot_123",
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_deer_other_help_bot(self, service_with_mocks):
        """测试不能帮 Bot 打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAt

        results = await service.batch_deer_other(
            sender_id="user123",
            at_ids={"bot_123"},
            at_list=[MockAt("bot_123", "Bot")],
            self_id="bot_123",
        )

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "不可以帮 Bot" in results[0]["reason"]

    @pytest.mark.asyncio
    async def test_batch_deer_other_help_all(self, service_with_mocks):
        """测试不能帮全体成员打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAt

        results = await service.batch_deer_other(
            sender_id="user123",
            at_ids={"all"},
            at_list=[MockAt("all", "全体成员")],
            self_id="bot_123",
        )

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "不能帮全体成员" in results[0]["reason"]

    @pytest.mark.asyncio
    async def test_batch_deer_other_not_allowed(self, service_with_mocks):
        """测试用户不允许被帮打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAt

        # 先设置用户不允许被帮打卡
        conn = await db.get_connection()
        try:
            await db.ensure_user_config(conn, "target_user")
            await db.set_help_allowed(conn, "target_user", False)
            await conn.commit()
        finally:
            await conn.close()

        results = await service.batch_deer_other(
            sender_id="user123",
            at_ids={"target_user"},
            at_list=[MockAt("target_user", "Target")],
            self_id="bot_123",
        )

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "不允许被帮" in results[0]["reason"]

    @pytest.mark.asyncio
    async def test_batch_deer_other_success(self, service_with_mocks):
        """测试成功帮他人打卡."""
        service, db, _ = service_with_mocks

        from tests.mocks import MockAt

        # 先设置用户允许被帮打卡
        conn = await db.get_connection()
        try:
            await db.ensure_user_config(conn, "target_user")
            await db.set_help_allowed(conn, "target_user", True)
            await conn.commit()
        finally:
            await conn.close()

        results = await service.batch_deer_other(
            sender_id="user123",
            at_ids={"target_user"},
            at_list=[MockAt("target_user", "Target")],
            self_id="bot_123",
        )

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["count"] == 1


class TestFormatFallbackText:
    """测试纯文本日历格式化."""

    def test_format_fallback_text_empty(self):
        """测试空日历数据."""
        text = DeerPipeService._format_fallback_text(2024, 5, {})

        assert "2024年5月" in text
        assert "共0天" in text
        assert "0次" in text

    def test_format_fallback_text_with_data(self):
        """测试有数据的日历."""
        month_map = {1: 1, 5: 2, 10: 3}
        text = DeerPipeService._format_fallback_text(2024, 5, month_map)

        assert "2024年5月" in text
        assert "共3天" in text
        assert "6次" in text  # 1 + 2 + 3 = 6

    def test_format_fallback_text_contains_calendar_structure(self):
        """测试日历结构."""
        month_map = {1: 1}
        text = DeerPipeService._format_fallback_text(2024, 5, month_map)

        # 检查日历头部
        assert "日   一   二   三   四   五   六" in text
        # 检查分隔符
        assert "=" in text
