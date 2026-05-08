"""Leaderboard presenter.

排行榜展示器，负责协调领域服务和基础设施。
"""

from __future__ import annotations

import base64
from datetime import date
from pathlib import Path
from typing import Any

from ...domain.services import LeaderboardDataBuilder
from ...infrastructure import (
    ResourceLoader,
    TemplateRenderer,
    get_logger,
)

logger = get_logger()


class LeaderboardPresenter:
    """排行榜展示器.

    负责组装排行榜展示所需的数据并调用渲染。
    """

    def __init__(
        self,
        resource_loader: ResourceLoader,
        template_renderer: TemplateRenderer,
    ) -> None:
        """初始化排行榜展示器.

        Args:
            resource_loader: 资源加载器
            template_renderer: 模板渲染器
        """
        self.resource_loader = resource_loader
        self.template_renderer = template_renderer
        self.data_builder = LeaderboardDataBuilder()
        self.logger = logger

    async def present_leaderboard(
        self,
        html_render_func,
        leaderboard_data: list[tuple[str, int]],
        title: str,
        date_str: str,
        user_id: str | None = None,
        user_rank: int | None = None,
        user_count: int = 0,
    ) -> str:
        """展示排行榜图片.

        协调流程：
        1. 使用 domain service 构建业务数据
        2. 使用 infrastructure 加载资源
        3. 使用 infrastructure 渲染模板

        Args:
            html_render_func: HTML渲染函数
            leaderboard_data: 原始排行榜数据
            title: 标题
            date_str: 日期字符串
            user_id: 当前用户ID
            user_rank: 当前用户排名
            user_count: 当前用户打卡次数

        Returns:
            渲染后的图片URL
        """
        # 1. 加载模板和CSS
        html = self.resource_loader.load_template("leaderboard")
        css_content = self.resource_loader.load_css("leaderboard")

        # 2. 使用 domain service 构建业务数据
        leaderboard = self.data_builder.build_display_data(leaderboard_data)
        total_count, total_users = self.data_builder.calculate_statistics(
            leaderboard_data
        )

        # 3. 构建当前用户信息
        current_user = None
        if user_id:
            current_user = {
                "rank": user_rank,
                "count": user_count,
                "on_leaderboard": user_rank is not None,
            }

        # 4. 组装渲染数据
        payload = {
            "css_style": css_content,
            "title": title,
            "date_str": date_str,
            "leaderboard": leaderboard,
            "total_count": total_count,
            "total_users": total_users,
            "current_user": current_user,
        }

        # 5. 调用渲染器
        return await self.template_renderer.render(html, payload, html_render_func)

    def format_fallback_text(
        self,
        leaderboard_data: list[tuple[str, int]] | list[tuple[str, int, int]],
        title_prefix: str,
        date_obj: date,
        is_monthly: bool = False,
    ) -> str:
        """格式化排行榜文本.

        Args:
            leaderboard_data: 排行榜数据
            title_prefix: 标题前缀
            date_obj: 日期对象
            is_monthly: 是否是月排行榜

        Returns:
            格式化的文本
        """
        # 构建日期字符串
        date_str = (
            f"{date_obj.year}年{date_obj.month}月"
            if is_monthly
            else f"{date_obj.year}年{date_obj.month}月{date_obj.day}日"
        )

        # 构建标题和头部
        lines = [
            f"📊 {title_prefix}群鹿排行榜",
            f"📅 {date_str}",
            "",
        ]

        # 显示前10名，使用 domain service 格式化奖牌
        for i, item in enumerate(leaderboard_data[:10]):
            medal = self.data_builder.format_leaderboard_medals(i)

            if is_monthly:
                user_id, total_count, days_count = item
                lines.append(f"{medal} {user_id}: {total_count}次 / {days_count}天")
            else:
                user_id, count = item
                lines.append(f"{medal} {user_id}: {count}次")

        # 使用 domain service 计算统计信息
        if is_monthly:
            total_count = sum(count for _, count, _ in leaderboard_data)
        else:
            total_count = sum(count for _, count in leaderboard_data)
        total_users = len(leaderboard_data)

        lines.extend([
            "",
            f"📈 总计: {total_users}人参与，累计打卡 {total_count}次",
        ])

        return "\n".join(lines)
