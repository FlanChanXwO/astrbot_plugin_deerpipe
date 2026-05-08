"""Deermap command handlers.

处理年度鹿力图相关命令。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from astrbot.api.event import AstrMessageEvent

from ...application.presenters import DeermapPresenter
from ...infrastructure import (
    get_logger,
    ResourceLoader,
    TemplateRenderer,
)
from ...infrastructure.persistence import DatabaseManager

logger = get_logger()


class DeermapCommandHandler:
    """年度鹿力图命令处理器.

    使用展示器模式，专注于命令路由和参数准备。
    """

    def __init__(self, db: DatabaseManager, base_dir: Path) -> None:
        """初始化命令处理器.

        Args:
            db: 数据库管理器实例
            base_dir: 插件根目录
        """
        self.db = db
        self.base_dir = base_dir
        self.logger = logger

        # 初始化基础设施
        resource_loader = ResourceLoader(base_dir)
        template_renderer = TemplateRenderer()

        # 初始化展示器
        self.presenter = DeermapPresenter(resource_loader, template_renderer, base_dir)

    async def handle_deermap(
        self, event: AstrMessageEvent, html_render, year: int | None = None
    ) -> AsyncGenerator[Any, None]:
        """处理年度鹿力图查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            year: 年份, None表示今年

        Yields:
            发送给用户的响应
        """
        target_year = year if year else dt.date.today().year
        user_id = str(event.get_sender_id())

        db = await self.db.get_connection()
        try:
            stats_data = await self.db.get_yearly_stats(db, user_id, target_year)

            platform_name = event.get_platform_name()

            # 使用展示器渲染
            image_url = await self.presenter.present_deermap(
                html_render,
                stats_data,
                target_year,
                user_id,
                platform_name,
            )

            if image_url:
                TemplateRenderer.schedule_temp_cleanup(html_render, image_url)
                yield event.image_result(image_url)
            else:
                yield event.plain_result(
                    self.presenter.format_fallback_text(stats_data, target_year)
                )
        except Exception as e:
            self.logger.error(f"获取鹿力图失败: {e}")
            yield event.plain_result("获取鹿力图失败，请稍后重试。")
        finally:
            await db.close()
