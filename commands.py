"""Deer-pipe plugin command handlers.

业务逻辑处理模块，封装所有命令的具体实现。
"""

from __future__ import annotations

import datetime as dt
import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.platform.message_type import MessageType

from .database import DatabaseManager
from .renderer import CalendarRenderer
from .utils import extract_mention_user_ids, validate_day


class DeerPipeService:
    """鹿管业务逻辑服务.

    封装所有命令的业务逻辑，独立于消息事件处理。
    """

    def __init__(
        self,
        db: DatabaseManager,
        renderer: CalendarRenderer,
        config: dict | None = None,
    ) -> None:
        """初始化服务.

        Args:
            db: 数据库管理器实例
            renderer: 日历渲染器实例
            config: 插件配置字典
        """
        self.db = db
        self.renderer = renderer
        self.config = config or {}

    def _get_template(self, key: str) -> str:
        """获取文本模板.

        Args:
            key: 模板键名

        Returns:
            模板字符串
        """
        templates = {
            "group_only": "该命令仅限群聊使用。",
            "operation_failed": "操作失败，请稍后重试。",
            "deer_past_limit": "今日补🦌次数已达上限。",
            "deer_past_success": "成功补🦌 {month}月{day}日",
            "calendar_load_failed": "日历数据加载失败。",
            "fallback_calendar_header": "📅 {year}年{month}月 鹿历",
            "fallback_calendar_stats": "📊 统计: 共{days}天 {total}次",
        }
        return templates.get(key, "")

    async def handle_deer_self(self, event: AstrMessageEvent) -> str:
        """处理自我打卡.

        Args:
            event: 消息事件

        Returns:
            操作结果消息
        """
        user_id = event.get_sender_id()
        today = dt.date.today()

        db = await self.db.get_connection()
        try:
            await self.db.ensure_user_config(db, user_id)
            await self.db.record_attendance(
                db, user_id, today.year, today.month, today.day
            )
            await db.commit()
        except Exception as exc:
            logger.error(f"deer_self failed: {exc}")
            return "操作失败，请稍后重试。"
        finally:
            await db.close()

        return "成功🦌了"

    async def handle_deer_other(self, event: AstrMessageEvent) -> str | None:
        """处理帮他人打卡.

        Args:
            event: 消息事件

        Returns:
            操作结果消息，None 表示不处理
        """
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return "该命令仅限群聊使用。"

        at_ids = extract_mention_user_ids(event.message_str)
        if not at_ids:
            return None

        # 禁止帮 bot 自己打卡
        self_id = event.get_self_id()
        if self_id and self_id in at_ids:
            return "不可以帮 Bot🦌哦~"

        today = dt.date.today()
        db = await self.db.get_connection()
        try:
            results: list[str] = []
            for target_id in at_ids:
                allowed = await self.db.is_help_allowed(db, target_id)
                if not allowed:
                    results.append(f"用户 {target_id} 不允许被帮🦌")
                    continue
                await self.db.record_attendance(
                    db, target_id, today.year, today.month, today.day
                )
                results.append(f"成功帮{target_id}🦌了")
            await db.commit()
        except Exception as exc:
            logger.error(f"deer_other failed: {exc}")
            return "操作失败，请稍后重试。"
        finally:
            await db.close()

        return "\n".join(results)

    async def handle_set_self_help(self, event: AstrMessageEvent, allowed: bool) -> str:
        """处理设置自己的帮 deer 权限.

        Args:
            event: 消息事件
            allowed: 是否允许

        Returns:
            操作结果消息
        """
        user_id = event.get_sender_id()

        db = await self.db.get_connection()
        try:
            await self.db.set_help_allowed(db, user_id, allowed)
            await db.commit()
        except Exception as exc:
            logger.error(f"set_self_help_status failed: {exc}")
            return "操作失败，请稍后重试。"
        finally:
            await db.close()

        return (
            "已开启，现在别人可以帮你🦌了~"
            if allowed
            else "已关闭，现在只有你自己能🦌了！"
        )

    async def handle_set_other_help(
        self, event: AstrMessageEvent, allowed: bool
    ) -> str | None:
        """处理管理员设置他人的帮 deer 权限.

        Args:
            event: 消息事件
            allowed: 是否允许他人帮 deer

        Returns:
            操作结果消息，None 表示不处理
        """
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return self._get_template("group_only").format()

        # 提取提及的用户
        at_ids = extract_mention_user_ids(event.message_str)
        if not at_ids:
            return "请 @目标用户。"

        db = await self.db.get_connection()
        try:
            logs: list[str] = []
            for target_id in at_ids:
                await self.db.set_help_allowed(db, target_id, allowed)
                status_str = "允许" if allowed else "禁止"
                logs.append(f"用户 {target_id} 被🦌策略设置为: {status_str}")
            await db.commit()
        except Exception as exc:
            logger.error(f"set_other_help_status failed: {exc}")
            return self._get_template("operation_failed").format()
        finally:
            await db.close()

        return "\n".join(logs) if logs else "没有成功设置任何用户。"

    async def handle_deer_past(self, event: AstrMessageEvent) -> str | None:
        """处理补🦌.

        Args:
            event: 消息事件

        Returns:
            操作结果消息，None 表示不处理
        """
        # 提取日期数字
        match = re.search(r"(\d+)$", event.message_str.strip())
        if not match:
            return None
        day = int(match.group(1))

        today = dt.date.today()

        # 验证日期有效性
        valid, error_msg = validate_day(day, today.year, today.month)
        if not valid:
            return error_msg

        user_id = event.get_sender_id()
        db = await self.db.get_connection()
        try:
            # 检查今日是否已补过
            last_retro = await self.db.get_last_retro_date(db, user_id)
            if last_retro == today.isoformat():
                return self._get_template("deer_past_limit").format()

            # 执行补 deer
            await self.db.record_attendance(db, user_id, today.year, today.month, day)
            await self.db.set_last_retro_date(db, user_id, today.isoformat())
            await db.commit()
        except Exception as exc:
            logger.error(f"deer_past failed: {exc}")
            return self._get_template("operation_failed").format()
        finally:
            await db.close()

        return self._get_template("deer_past_success").format(
            month=today.month, day=day
        )

    async def render_calendar(
        self, event: AstrMessageEvent, month_date: dt.date, html_render_func, user_id: str | None = None
    ):
        """渲染日历.

        Args:
            event: 消息事件
            month_date: 目标月份
            html_render_func: HTML 渲染函数
            user_id: 可选，指定用户ID（默认为发送者）

        Yields:
            渲染结果 (图片 URL 或纯文本, 是否为文本)
        """
        if user_id is None:
            user_id = event.get_sender_id()

        # 从数据库获取日历数据
        db = await self.db.get_connection()
        try:
            month_map = await self.db.get_calendar_data(
                db, user_id, month_date.year, month_date.month
            )
        except Exception as exc:
            logger.error(f"Failed to load calendar data: {exc}")
            yield self._get_template("calendar_load_failed").format(), True
            return
        finally:
            await db.close()

        # 尝试渲染图片
        try:
            image_url = await self.renderer.render(
                html_render_func,
                user_id,
                month_date.year,
                month_date.month,
                month_map,
            )
            yield image_url, False
        except Exception as exc:
            logger.error(f"Calendar render failed: {exc}")
            # 降级：返回纯文本日历
            fallback_text = self._format_fallback_text(
                month_date.year, month_date.month, month_map
            )
            yield fallback_text, True

    def _format_fallback_text(
        self, year: int, month: int, month_map: dict[int, int]
    ) -> str:
        """生成纯文本日历.

        Args:
            year: 年份
            month: 月份
            month_map: 日期到打卡次数的映射

        Returns:
            格式化的纯文本日历
        """
        import calendar

        total = sum(month_map.values())
        days_recorded = len(month_map)

        # 构建日历表头
        header = self._get_template("fallback_calendar_header").format(
            year=year, month=month
        )
        separator = "=" * 28

        # 星期标题
        weekday_header = " 日   一   二   三   四   五   六 "

        # 构建日历主体
        cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
        lines: list[str] = []

        for week in cal.monthdayscalendar(year, month):
            week_strs: list[str] = []
            for day in week:
                if day == 0:
                    week_strs.append("    ")  # 空位
                elif day in month_map:
                    count = month_map[day]
                    # 有记录的日期显示次数
                    if count >= 10:
                        week_strs.append(f"{count:>3} ")
                    else:
                        week_strs.append(f" {count}  ")
                else:
                    week_strs.append(f"{day:>3} ")
            lines.append("".join(week_strs))

        calendar_body = "\n".join(lines)

        # 统计信息
        stats = self._get_template("fallback_calendar_stats").format(
            days=days_recorded, total=total
        )

        return (
            f"{header}\n"
            f"{separator}\n"
            f"{weekday_header}\n"
            f"{calendar_body}\n"
            f"{separator}\n"
            f"{stats}\n"
            f"💡 带数字的日期为已打卡次数"
        )
