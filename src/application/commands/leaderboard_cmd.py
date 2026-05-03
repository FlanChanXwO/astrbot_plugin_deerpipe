"""Leaderboard command handlers.

处理群排行榜相关命令。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from astrbot.api.event import AstrMessageEvent
from astrbot.core.platform.message_type import MessageType

from ...application.services import DeerPipeService
from ...domain import TEMPLATE_GROUP_ONLY
from ...infrastructure import get_logger
from ...infrastructure.persistence import DatabaseManager
from ...infrastructure.utils.http_utils import fetch_avatar_base64
from ...shared import ResourcePaths

logger = get_logger()


class LeaderboardCommandHandler:
    """排行榜命令处理器.

    轻量级处理器，通过构造函数接收必要的依赖。
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

        # 模板路径
        paths = ResourcePaths(base_dir)
        self.leaderboard_template = paths.template("leaderboard")
        self.deermap_template = paths.template("deermap")
        self.leaderboard_css = paths.style("leaderboard")
        self.deermap_css = paths.style("deermap")

    async def handle_daily_leaderboard(
        self, event: AstrMessageEvent, html_render
    ) -> AsyncGenerator[Any, None]:
        """处理今日群排行榜查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数

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
        async for result in self._render_leaderboard(
            event, html_render, group_id, today, "今日"
        ):
            yield result

    async def handle_yesterday_leaderboard(
        self, event: AstrMessageEvent, html_render
    ) -> AsyncGenerator[Any, None]:
        """处理昨日群排行榜查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数

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

        yesterday = dt.date.today() - dt.timedelta(days=1)
        async for result in self._render_leaderboard(
            event, html_render, group_id, yesterday, "昨日"
        ):
            yield result

    async def handle_monthly_leaderboard(
        self, event: AstrMessageEvent, html_render
    ) -> AsyncGenerator[Any, None]:
        """处理本月群排行榜查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数

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
        async for result in self._render_monthly_leaderboard(
            event, html_render, group_id, today.year, today.month, "本月"
        ):
            yield result

    async def _render_leaderboard(
        self,
        event: AstrMessageEvent,
        html_render,
        group_id: str,
        date: dt.date,
        title_prefix: str,
    ) -> AsyncGenerator[Any, None]:
        """渲染排行榜图片.

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            group_id: 群组ID
            date: 日期
            title_prefix: 标题前缀

        Yields:
            发送给用户的响应
        """
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

            # 获取当前用户信息（用于显示在排行榜底部）
            user_id = str(event.get_sender_id()) if event.get_sender_id() else None
            user_rank = None
            user_count = 0
            if user_id:
                for i, (uid, count) in enumerate(leaderboard_data):
                    if uid == user_id:
                        user_rank = i + 1
                        user_count = count
                        break

            # 渲染排行榜图片
            image_url = await self._render_leaderboard_image(
                html_render,
                leaderboard_data,
                f"{title_prefix}群鹿排行榜",
                f"{date.year}年{date.month}月{date.day}日",
                is_monthly=False,
                user_id=user_id,
                user_rank=user_rank,
                user_count=user_count,
            )

            if image_url:
                yield event.image_result(image_url)
            else:
                # 渲染失败，返回文本
                yield event.plain_result(
                    self._format_leaderboard_text(
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
        title_prefix: str,
    ) -> AsyncGenerator[Any, None]:
        """渲染月排行榜图片.

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            group_id: 群组ID
            year: 年份
            month: 月份
            title_prefix: 标题前缀

        Yields:
            发送给用户的响应
        """
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

            # 转换数据格式为 (user_id, count, days_count) -> 统一为显示用的格式
            display_data = [
                (user_id, total_count) for user_id, total_count, _ in leaderboard_data
            ]

            # 获取当前用户信息（用于显示在排行榜底部）
            user_id = str(event.get_sender_id()) if event.get_sender_id() else None
            user_rank = None
            user_count = 0
            if user_id:
                for i, (uid, total_count, _) in enumerate(leaderboard_data):
                    if uid == user_id:
                        user_rank = i + 1
                        user_count = total_count
                        break

            # 渲染排行榜图片
            image_url = await self._render_leaderboard_image(
                html_render,
                display_data,
                f"{title_prefix}群鹿排行榜",
                f"{year}年{month}月",
                is_monthly=True,
                user_id=user_id,
                user_rank=user_rank,
                user_count=user_count,
            )

            if image_url:
                yield event.image_result(image_url)
            else:
                # 渲染失败，返回文本
                date = dt.date(year, month, 1)
                yield event.plain_result(
                    self._format_leaderboard_text(
                        leaderboard_data, title_prefix, date, True
                    )
                )
        except Exception as e:
            self.logger.error(f"获取月排行榜失败: {e}")
            yield event.plain_result("获取排行榜失败，请稍后重试。")
        finally:
            await db.close()

    async def _render_leaderboard_image(
        self,
        html_render,
        leaderboard_data: list[tuple[str, int]],
        title: str,
        date_str: str,
        is_monthly: bool = False,
        user_id: str | None = None,
        user_rank: int | None = None,
        user_count: int = 0,
    ) -> str | None:
        """渲染排行榜图片.

        Args:
            html_render: HTML渲染函数
            leaderboard_data: 排行榜数据 [(user_id, count), ...]
            title: 标题
            date_str: 日期字符串
            is_monthly: 是否是月排行榜
            user_id: 当前用户ID（可选）
            user_rank: 当前用户排名（可选）
            user_count: 当前用户打卡次数（可选）

        Returns:
            图片URL或None
        """
        if not self.leaderboard_template.exists():
            self.logger.error(f"排行榜模板不存在: {self.leaderboard_template}")
            return None

        try:
            # 读取模板和CSS
            html = self.leaderboard_template.read_text(encoding="utf-8")
            css_content = ""
            if self.leaderboard_css.exists():
                css_content = self.leaderboard_css.read_text(encoding="utf-8")

            # 准备排行榜数据
            leaderboard = []
            for i, (uid, count) in enumerate(leaderboard_data[:10]):
                name = f"用户{uid[-4:] if len(uid) > 4 else uid}"
                leaderboard.append({"name": name, "count": count})

            # 计算统计信息
            total_count = sum(count for _, count in leaderboard_data)
            total_users = len(leaderboard_data)

            # 构建当前用户信息（仅在 user_id 不为空时）
            current_user = None
            if user_id:
                current_user = {
                    "rank": user_rank,
                    "count": user_count,
                    "on_leaderboard": user_rank is not None,
                }

            # 构建渲染数据
            payload = {
                "css_style": css_content,
                "title": title,
                "date_str": date_str,
                "leaderboard": leaderboard,
                "total_count": total_count,
                "total_users": total_users,
                "current_user": current_user,
            }

            # 调用渲染服务
            image_url = await html_render(
                html,
                payload,
                return_url=True,
                options={
                    "type": "png",
                    "full_page": True,
                    "scale": "device",
                },
            )
            return image_url

        except Exception as e:
            self.logger.error(f"排行榜渲染失败: {e}")
            return None

    def _format_leaderboard_text(
        self,
        leaderboard_data,
        title_prefix: str,
        date: dt.date,
        is_monthly: bool = False,
    ) -> str:
        """格式化排行榜文本.

        Args:
            leaderboard_data: 排行榜数据
            title_prefix: 标题前缀
            date: 日期
            is_monthly: 是否是月排行榜

        Returns:
            格式化的文本
        """
        date_str = (
            f"{date.year}年{date.month}月"
            if is_monthly
            else f"{date.year}年{date.month}月{date.day}日"
        )
        lines = [f"📊 {title_prefix}群鹿排行榜", f"📅 {date_str}", ""]

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, item in enumerate(leaderboard_data[:10]):
            medal = medals[i] if i < len(medals) else f"{i + 1}."
            if is_monthly:
                user_id, total_count, days_count = item
                lines.append(f"{medal} {user_id}: {total_count}次 / {days_count}天")
            else:
                user_id, count = item
                lines.append(f"{medal} {user_id}: {count}次")

        if is_monthly:
            total_count = sum(count for _, count, _ in leaderboard_data)
        else:
            total_count = sum(count for _, count in leaderboard_data)
        total_users = len(leaderboard_data)

        lines.append("")
        lines.append(f"📈 总计: {total_users}人参与，累计打卡 {total_count}次")

        return "\n".join(lines)

    async def handle_deermap(
        self, event: AstrMessageEvent, html_render, year: int | None = None
    ) -> AsyncGenerator[Any, None]:
        """处理年度鹿力图查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            year: 年份，None表示今年

        Yields:
            发送给用户的响应
        """
        target_year = year if year else dt.date.today().year
        user_id = str(event.get_sender_id())

        db = await self.db.get_connection()
        try:
            # 获取年度数据
            stats_data = await self.db.get_yearly_stats(db, user_id, target_year)

            # 渲染热力图
            image_url = await self._render_heatmap(
                html_render, stats_data, target_year, user_id, event
            )

            if image_url:
                yield event.image_result(image_url)
            else:
                yield event.plain_result(
                    self._format_deermap_text(stats_data, target_year)
                )
        except Exception as e:
            self.logger.error(f"获取热力图失败: {e}")
            yield event.plain_result("获取热力图失败，请稍后重试。")
        finally:
            await db.close()

    async def _render_heatmap(
        self,
        html_render,
        stats_data: dict[str, int],
        year: int,
        user_id: str,
        event: AstrMessageEvent,
    ) -> str | None:
        """渲染热力图.

        Args:
            html_render: HTML渲染函数
            stats_data: 日期到打卡次数的映射 {YYYY-MM-DD: count}
            year: 年份
            user_id: 用户ID
            event: 消息事件（用于获取头像）

        Returns:
            图片URL或None
        """
        if not self.deermap_template.exists():
            self.logger.error(f"热力图模板不存在: {self.deermap_template}")
            return None

        try:
            # 读取模板和CSS
            html = self.deermap_template.read_text(encoding="utf-8")
            css_content = ""
            if self.deermap_css.exists():
                css_content = self.deermap_css.read_text(encoding="utf-8")

            # 构建热力图数据
            weeks_data, months, month_start_indices, week_to_month = self._build_deermap_data(stats_data, year)

            # 计算统计信息
            total_days = len(stats_data)
            total_count = sum(stats_data.values())
            max_count = max(stats_data.values()) if stats_data else 0
            # 日均次数 = 总次数 / 实际打卡天数（不是365天）
            avg_count = round(total_count / total_days, 1) if total_days > 0 else 0
            self.logger.debug(f"[Heatmap] Stats: total_days={total_days}, total_count={total_count}, max_count={max_count}, avg_count={avg_count}")

            # 获取用户头像
            platform_name = event.get_platform_name()
            avatar_b64 = await fetch_avatar_base64(user_id, platform_name)

            # 读取 shot.png 图片为 base64
            shot_path = self.base_dir / "resources" / "images" / "shot.png"
            shot_b64 = ""
            if shot_path.exists():
                import base64
                shot_b64 = f"data:image/png;base64,{base64.b64encode(shot_path.read_bytes()).decode()}"

            # 构建渲染数据
            payload = {
                "css_style": css_content,
                "title": f"{year}年鹿力图",
                "year": year,
                "months": months,
                "week_to_month": week_to_month,
                "weeks": weeks_data,
                "total_days": total_days,
                "total_count": total_count,
                "max_count": max_count,
                "avg_count": avg_count,
                "avatar_base64": avatar_b64,
                "shot_image": shot_b64,
            }
            self.logger.debug(f"[Heatmap] Payload avg_count: {payload.get('avg_count')}")

            # 调用渲染服务
            image_url = await html_render(
                html,
                payload,
                return_url=True,
                options={
                    "type": "png",
                    "full_page": True,
                    "scale": "device",
                },
            )
            return image_url

        except Exception as e:
            self.logger.error(f"热力图渲染失败: {e}")
            return None

    @staticmethod
    def _build_deermap_data(
            stats_data: dict[str, int], year: int
    ) -> tuple[list[list[dict]], list[str], list[int], list[int]]:
        """构建鹿力图数据.

        Args:
            stats_data: 日期到打卡次数的映射
            year: 年份

        Returns:
            (weeks_data, months, month_start_indices, week_to_month) 周数据、月份名称列表、每月起始周索引、每周所属月份索引
        """
        import calendar

        # 计算颜色等级
        max_count = max(stats_data.values()) if stats_data else 1
        levels = [
            0,
            max_count * 0.2,
            max_count * 0.4,
            max_count * 0.6,
            max_count * 0.8,
            max_count,
        ]

        def get_level(count: int) -> str:
            """根据次数获取颜色等级."""
            if count == 0:
                return "level-0"
            for i, threshold in enumerate(levels[1:], 1):
                if count <= threshold:
                    return f"level-{i}"
            return "level-5"

        # 构建周数据
        weeks_data: list[list[dict]] = []
        cal = calendar.Calendar(firstweekday=0)  # 周一为第一天

        # 按周组织数据，同时记录每月开始的周索引和每周对应的月份
        week_index = 0
        month_start_indices: list[int] = []
        week_to_month: list[int] = []  # 每周对应的月份索引(0-11)

        for month in range(1, 13):
            month_start_indices.append(week_index)
            for week in cal.monthdayscalendar(year, month):
                if all(day == 0 for day in week):
                    continue

                week_to_month.append(month - 1)  # 记录该周属于哪个月

                week_data: list[dict] = []
                for weekday, day in enumerate(week):
                    if day == 0:
                        week_data.append({"date": "", "count": 0, "level": "level-0"})
                    else:
                        date_key = f"{year}-{month:02d}-{day:02d}"
                        count = stats_data.get(date_key, 0)
                        week_data.append({"date": date_key, "count": count, "level": get_level(count)})

                weeks_data.append(week_data)
                week_index += 1

        # 月份名称
        month_names = ["1月", "2月", "3月", "4月", "5月", "6月",
                       "7月", "8月", "9月", "10月", "11月", "12月"]

        return weeks_data, month_names, month_start_indices, week_to_month

    @staticmethod
    def _format_deermap_text(stats_data: dict[str, int], year: int) -> str:
        """格式化鹿力图文本.

        Args:
            stats_data: 日期到打卡次数的映射
            year: 年份

        Returns:
            格式化的文本
        """
        total_days = len(stats_data)
        total_count = sum(stats_data.values())
        max_count = max(stats_data.values()) if stats_data else 0

        lines = [
            f"🔥 {year}年鹿力图",
            "",
            "📊 统计信息:",
            f"  • 鹿天数: {total_days}天",
            f"  • 总鹿次数: {total_count}次",
            f"  • 单日最多: {max_count}次",
        ]

        return "\n".join(lines)
