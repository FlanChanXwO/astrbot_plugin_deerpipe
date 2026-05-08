"""Leaderboard renderer.

排行榜渲染器，统一处理排行榜的图片渲染和文本回退。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .base_renderer import BaseTemplateRenderer


class LeaderboardRenderer(BaseTemplateRenderer):
    """排行榜渲染器.

    处理日榜和月榜的渲染。
    """

    def __init__(self, base_dir: Path) -> None:
        """初始化排行榜渲染器.

        Args:
            base_dir: 插件根目录
        """
        super().__init__(
            base_dir=base_dir,
            template_name="leaderboard",
            css_name="leaderboard",
        )

    async def build_payload(
        self,
        leaderboard_data: list[tuple[str, int]],
        title: str,
        date_str: str,
        user_id: str | None = None,
        user_rank: int | None = None,
        user_count: int = 0,
    ) -> dict[str, Any]:
        """构建排行榜渲染数据.

        Args:
            leaderboard_data: 排行榜数据 [(user_id, count), ...]
            title: 标题
            date_str: 日期字符串
            user_id: 当前用户ID (可选)
            user_rank: 当前用户排名 (可选)
            user_count: 当前用户打卡次数 (可选)

        Returns:
            渲染数据字典
        """
        # 准备排行榜显示数据（只取前10名）
        leaderboard = []
        for i, (uid, count) in enumerate(leaderboard_data[:10]):
            # 匿名化用户名：只显示后4位
            name = f"用户{uid[-4:] if len(uid) > 4 else uid}"
            leaderboard.append({"name": name, "count": count})

        # 计算统计信息
        total_count = sum(count for _, count in leaderboard_data)
        total_users = len(leaderboard_data)

        # 构建当前用户信息
        current_user = None
        if user_id:
            current_user = {
                "rank": user_rank,
                "count": user_count,
                "on_leaderboard": user_rank is not None,
            }

        return {
            "title": title,
            "date_str": date_str,
            "leaderboard": leaderboard,
            "total_count": total_count,
            "total_users": total_users,
            "current_user": current_user,
        }

    def format_fallback_text(
        self,
        leaderboard_data: list[tuple[str, int]] | list[tuple[str, int, int]],
        title_prefix: str,
        date: date,
        is_monthly: bool = False,
    ) -> str:
        """格式化排行榜文本.

        Args:
            leaderboard_data: 排行榜数据
            title_prefix: 标题前缀（如"今日"、"本月"）
            date: 日期
            is_monthly: 是否是月排行榜

        Returns:
            格式化的文本
        """
        # 构建日期字符串
        date_str = (
            f"{date.year}年{date.month}月"
            if is_monthly
            else f"{date.year}年{date.month}月{date.day}日"
        )

        # 构建标题和头部
        lines = [
            f"📊 {title_prefix}群鹿排行榜",
            f"📅 {date_str}",
            "",
        ]

        # 排名奖牌
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        # 显示前10名
        for i, item in enumerate(leaderboard_data[:10]):
            medal = medals[i] if i < len(medals) else f"{i + 1}."
            if is_monthly:
                user_id, total_count, days_count = item
                lines.append(f"{medal} {user_id}: {total_count}次 / {days_count}天")
            else:
                user_id, count = item
                lines.append(f"{medal} {user_id}: {count}次")

        # 统计信息
        if is_monthly:
            total_count = sum(count for _, count, _ in leaderboard_data)
        else:
            total_count = sum(count for _, count in leaderboard_data)
        total_users = len(leaderboard_data)

        lines.extend(
            [
                "",
                f"📈 总计: {total_users}人参与，累计打卡 {total_count}次",
            ]
        )

        return "\n".join(lines)
