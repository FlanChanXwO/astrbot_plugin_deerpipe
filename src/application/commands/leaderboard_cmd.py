"""Leaderboard command handlers.

处理群排行榜相关命令。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from enum import Enum, auto
from pathlib import Path
from typing import Any

from astrbot.api.event import AstrMessageEvent
from astrbot.core.platform.message_type import MessageType

from ...application.services import DeerPipeService
from ...application.presenters import LeaderboardPresenter
from ...domain import TEMPLATE_GROUP_ONLY
from ...infrastructure import (
    get_logger,
    ResourceLoader,
    TemplateRenderer,
)
from ...infrastructure.persistence import DatabaseManager
from ...domain.services import LeaderboardDataBuilder

logger = get_logger()


class LeaderboardType(Enum):
    """排行榜类型枚举."""

    DAILY = auto()
    YESTERDAY = auto()
    MONTHLY = auto()


class LeaderboardCommandHandler:
    """排行榜命令处理器.

    使用展示器模式，专注于命令路由和参数准备。
    """

    def __init__(
        self,
        service: DeerPipeService,
        db: DatabaseManager,
        base_dir: Path,
    ) -> None:
        """初始化命令处理器.

        Args:
            service: 鹿管业务服务实例
            db: 数据库管理器实例
            base_dir: 插件根目录
        """
        self.service = service
        self.db = db
        self.base_dir = base_dir
        self.logger = logger

        # 初始化基础设施
        resource_loader = ResourceLoader(base_dir)
        template_renderer = TemplateRenderer()

        # 初始化展示器
        self.presenter = LeaderboardPresenter(resource_loader, template_renderer)

        # 用于查找用户排名
        self.data_builder = LeaderboardDataBuilder()

    async def handle_leaderboard(
        self,
        event: AstrMessageEvent,
        html_render,
        leaderboard_type: LeaderboardType,
    ) -> AsyncGenerator[Any, None]:
        """处理群排行榜查询 (统一入口).

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            leaderboard_type: 排行榜类型

        Yields:
            发送给用户的响应
        """
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            yield event.plain_result(TEMPLATE_GROUP_ONLY)
            return

        group_id = str(event.get_group_id()) if event.get_group_id() else None
        if not group_id:
            yield event.plain_result("无法获取群ID，请在群聊中使用此命令。")
            return

        today = dt.date.today()

        match leaderboard_type:
            case LeaderboardType.DAILY:
                async for result in self._render_daily_leaderboard(
                    event, html_render, group_id, today
                ):
                    yield result

            case LeaderboardType.YESTERDAY:
                yesterday = today - dt.timedelta(days=1)
                async for result in self._render_daily_leaderboard(
                    event, html_render, group_id, yesterday, is_yesterday=True
                ):
                    yield result

            case LeaderboardType.MONTHLY:
                async for result in self._render_monthly_leaderboard(
                    event, html_render, group_id, today.year, today.month
                ):
                    yield result

    async def _render_daily_leaderboard(
        self,
        event: AstrMessageEvent,
        html_render,
        group_id: str,
        date: dt.date,
        is_yesterday: bool = False,
    ) -> AsyncGenerator[Any, None]:
        """渲染日排行榜.

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            group_id: 群组ID
            date: 日期
            is_yesterday: 是否是昨日

        Yields:
            发送给用户的响应
        """
        title_prefix = "昨日" if is_yesterday else "今日"
        db = await self.db.get_connection()
        try:
            leaderboard_data = await self.db.get_group_daily_leaderboard(
                db, group_id, date.year, date.month, date.day
            )

            if not leaderboard_data:
                yield event.plain_result(
                    f"📊 {title_prefix}群鹿排行榜\n\n"
                    "暂无打卡记录~\n\n"
                    "快发送 🦌 来打卡吧！"
                )
                return

            # 获取当前用户信息（使用 domain service）
            user_id = str(event.get_sender_id()) if event.get_sender_id() else None
            user_rank = None
            user_count = 0
            if user_id:
                user_rank, user_count = self.data_builder.find_user_rank(
                    leaderboard_data, user_id
                )

            # 使用展示器渲染
            image_url = await self.presenter.present_leaderboard(
                html_render,
                leaderboard_data,
                f"{title_prefix}群鹿排行榜",
                f"{date.year}年{date.month}月{date.day}日",
                user_id,
                user_rank,
                user_count,
            )

            if image_url:
                TemplateRenderer.schedule_temp_cleanup(html_render, image_url)
                yield event.image_result(image_url)
            else:
                yield event.plain_result(
                    self.presenter.format_fallback_text(
                        leaderboard_data, title_prefix, date, False
                    )
                )
        except Exception as e:
            self.logger.error(f"获取排行榜失败: {e}")
            yield event.plain_result("获取排行榜失败，请稍后重试。")
        finally:
            await db.close()

    async def _render_monthly_leaderboard(
        self,
        event: AstrMessageEvent,
        html_render,
        group_id: str,
        year: int,
        month: int,
    ) -> AsyncGenerator[Any, None]:
        """渲染月排行榜图片.

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            group_id: 群组ID
            year: 年份
            month: 月份

        Yields:
            发送给用户的响应
        """
        title_prefix = "本月"
        db = await self.db.get_connection()
        try:
            leaderboard_data = await self.db.get_group_monthly_leaderboard(
                db, group_id, year, month
            )

            if not leaderboard_data:
                yield event.plain_result(
                    f"📊 {title_prefix}群鹿排行榜\n\n"
                    "暂无打卡记录~\n\n"
                    "快发送 🦌 来打卡吧！"
                )
                return

            # 转换数据格式
            display_data = [
                (user_id, total_count) for user_id, total_count, _ in leaderboard_data
            ]

            # 获取当前用户信息（使用 domain service）
            user_id = str(event.get_sender_id()) if event.get_sender_id() else None
            user_rank = None
            user_count = 0
            if user_id:
                user_rank, user_count = self.data_builder.find_user_rank(
                    display_data, user_id
                )

            # 使用展示器渲染
            image_url = await self.presenter.present_leaderboard(
                html_render,
                display_data,
                f"{title_prefix}群鹿排行榜",
                f"{year}年{month}月",
                user_id,
                user_rank,
                user_count,
            )

            if image_url:
                TemplateRenderer.schedule_temp_cleanup(html_render, image_url)
                yield event.image_result(image_url)
            else:
                date_obj = dt.date(year, month, 1)
                yield event.plain_result(
                    self.presenter.format_fallback_text(
                        leaderboard_data, title_prefix, date_obj, True
                    )
                )
        except Exception as e:
            self.logger.error(f"获取月排行榜失败: {e}")
            yield event.plain_result("获取月排行榜失败，请稍后重试。")
        finally:
            await db.close()
