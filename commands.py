"""Deer-pipe plugin command handlers.

业务逻辑处理模块，封装所有命令的具体实现。
"""

from __future__ import annotations

import calendar
import datetime as dt
from typing import TypedDict

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import At
from astrbot.core.platform.message_type import MessageType

from .database import DatabaseManager
from .renderer import CalendarRenderer
from .utils import extract_mention_user_ids, normalize_user_id, validate_day


class DeerResult(TypedDict):
    """打卡结果数据类型."""

    user_id: str
    nickname: str
    success: bool
    count: int
    is_new: bool
    reason: str | None


class TemplateKeyError(KeyError):
    """模板键缺失错误."""

    pass


class MessageTemplates:
    """消息模板管理器.

    统一管理所有文本模板，支持严格格式化检查。
    """

    _TEMPLATES = {
        "group_only": "该命令仅限群聊使用。",
        "operation_failed": "操作失败，请稍后重试。",
        "deer_past_limit": "今日补🦌次数已达上限。",
        "deer_past_success": "成功补🦌 {month}月{day}日",
        "calendar_load_failed": "日历数据加载失败。",
        "fallback_calendar_header": "📅 {year}年{month}月 鹿历",
        "fallback_calendar_stats": "📊 统计: 共{days}天 {total}次",
    }

    @classmethod
    def get(cls, key: str, **kwargs) -> str:
        """获取格式化后的模板.

        Args:
            key: 模板键名
            **kwargs: 格式化参数

        Returns:
            格式化后的模板字符串

        Raises:
            TemplateKeyError: 模板键不存在或格式化参数缺失
        """
        template = cls._TEMPLATES.get(key)
        if template is None:
            raise TemplateKeyError(f"模板键 '{key}' 不存在")

        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise TemplateKeyError(f"模板 '{key}' 缺少参数: {e}") from e


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

    async def batch_deer_other(
        self,
        sender_id: str,
        at_ids: set[str],
        at_list: list[At],
        self_id: str | None = None,
    ) -> list[DeerResult]:
        """批量帮他人打卡.

        Args:
            sender_id: 发送者ID
            at_ids: 要帮打卡的用户ID集合
            at_list: At组件列表，用于获取昵称
            self_id: Bot自身的ID，用于检查是否帮Bot打卡

        Returns:
            每个目标的打卡结果列表
        """
        results: list[DeerResult] = []
        today = dt.date.today()
        sender_id = normalize_user_id(sender_id)

        # 检查是否帮Bot自己打卡
        if self_id and self_id in at_ids:
            results.append({
                "user_id": self_id,
                "nickname": "Bot",
                "success": False,
                "count": 0,
                "is_new": False,
                "reason": "不可以帮 Bot🦌哦~",
            })
            at_ids = at_ids - {self_id}

        # 构建 user_id -> At 组件的映射，用于获取昵称
        at_map = {str(m.qq): m for m in at_list}

        db = await self.db.get_connection()
        try:
            for target_id in at_ids:
                # 跳过 AT 全体成员的非法目标
                if target_id == "all":
                    at_component = at_map.get(target_id)
                    target_name = (
                        at_component.name
                        if at_component and at_component.name
                        else "全体成员"
                    )
                    results.append({
                        "user_id": target_id,
                        "nickname": target_name,
                        "success": False,
                        "count": 0,
                        "is_new": False,
                        "reason": "不能帮全体成员🦌",
                    })
                    continue

                # 获取用户名称（优先使用 At 组件中的 name）
                at_component = at_map.get(target_id)
                target_name = (
                    at_component.name
                    if at_component and at_component.name
                    else target_id
                )

                # 用户自己🦌自己总是允许的
                if target_id != sender_id:
                    allowed = await self.db.is_help_allowed(db, target_id)
                    if not allowed:
                        results.append({
                            "user_id": target_id,
                            "nickname": target_name,
                            "success": False,
                            "count": 0,
                            "is_new": False,
                            "reason": "不允许被帮🦌",
                        })
                        continue

                # 记录打卡前检查是否已有记录（用于判断 is_new）
                has_record_before = await self.db.has_record_today(db, target_id)

                await self.db.record_attendance(
                    db, target_id, today.year, today.month, today.day
                )

                # 获取更新后的次数
                month_map = await self.db.get_calendar_data(
                    db, target_id, today.year, today.month
                )
                today_count = month_map.get(today.day, 0)

                results.append({
                    "user_id": target_id,
                    "nickname": target_name,
                    "success": True,
                    "count": today_count,
                    "is_new": not has_record_before,
                    "reason": None,
                })

            await db.commit()
        except Exception as exc:
            logger.error(f"batch_deer_other failed: {exc}")
            raise
        finally:
            await db.close()

        return results

    async def handle_deer_self(self, event: AstrMessageEvent) -> str:
        """处理自我打卡.

        Args:
            event: 消息事件

        Returns:
            操作结果消息
        """
        user_id = normalize_user_id(event.get_sender_id())
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

    async def handle_deer_other(
        self, event: AstrMessageEvent, at_ids: set[str]
    ) -> str | None:
        """处理帮他人打卡.

        Args:
            event: 消息事件
            at_ids: 要帮打卡的用户ID集合

        Returns:
            操作结果消息，None 表示不处理
        """
        if event.get_message_type() != MessageType.GROUP_MESSAGE:
            return "该命令仅限群聊使用。"

        if not at_ids:
            return None

        # 禁止帮 bot 自己打卡
        self_id = event.get_self_id()
        if self_id and self_id in at_ids:
            return "不可以帮 Bot🦌哦~"

        today = dt.date.today()
        sender_id = normalize_user_id(event.get_sender_id())
        db = await self.db.get_connection()
        try:
            results: list[str] = []
            has_success = False
            has_failure = False
            for raw_target_id in at_ids:
                target_id = normalize_user_id(raw_target_id)
                # 跳过 AT 全体成员的非法目标
                if target_id == "all":
                    results.append("❌ 不能帮全体成员🦌")
                    has_failure = True
                    continue
                # 用户自己🦌自己总是允许的，不需要检查 allow_help
                logger.debug("target_id = %s ; sender_id = %s", target_id, sender_id)
                if target_id != sender_id:
                    allowed = await self.db.is_help_allowed(db, target_id)
                    logger.debug(
                        f"[DeerPipe] handle_deer_other 检查用户 {target_id}: allowed={allowed}, not_allowed={not allowed}"
                    )
                    if not allowed:
                        results.append(f"❌ 用户 {target_id} 不允许被帮🦌")
                        has_failure = True
                        continue
                await self.db.record_attendance(
                    db, target_id, today.year, today.month, today.day
                )
                results.append(f"✅ 成功帮 {target_id} 🦌了")
                has_success = True
            await db.commit()

            # 如果全部失败，添加提示信息
            if has_failure and not has_success:
                results.append("\n提示：用户已设置禁止被🦌，无法帮其打卡。")
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
        user_id = normalize_user_id(event.get_sender_id())
        sender_name = event.get_sender_name()
        logger.debug(
            f"[DeerPipe] handle_set_self_help: raw user_id={user_id}, name={sender_name}, allowed={allowed}"
        )

        db = await self.db.get_connection()
        try:
            await self.db.set_help_allowed(db, user_id, allowed)
            await db.commit()
            logger.debug(f"[DeerPipe] 用户 {user_id} 设置 allow_help={allowed} 成功")
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
            return MessageTemplates.get("group_only")
        # 提取提及的用户
        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)
        if not at_ids:
            return "请 @目标用户。"

        db = await self.db.get_connection()
        try:
            logs: list[str] = []
            for raw_target_id in at_ids:
                target_id = normalize_user_id(raw_target_id)
                await self.db.set_help_allowed(db, target_id, allowed)
                status_str = "允许" if allowed else "禁止"
                logs.append(f"用户 {target_id} 被🦌策略设置为: {status_str}")
                logger.debug(
                    f"[DeerPipe] 管理员设置用户 {target_id} allow_help={allowed}"
                )
            await db.commit()
        except Exception as exc:
            logger.error(f"set_other_help_status failed: {exc}")
            return MessageTemplates.get("operation_failed")
        finally:
            await db.close()

        return "\n".join(logs) if logs else "没有成功设置任何用户。"

    async def handle_deer_past(
        self, event: AstrMessageEvent, day: int, year: int | None = None, month: int | None = None
    ) -> str | None:
        """处理补🦌.

        Args:
            event: 消息事件
            day: 要补签的日期（日）
            year: 要补签的年份，默认为当前年份
            month: 要补签的月份，默认为当前月份

        Returns:
            操作结果消息，None 表示不处理
        """
        today = dt.date.today()
        target_year = year or today.year
        target_month = month or today.month

        # 验证日期有效性
        valid, error_msg = validate_day(day, target_year, target_month)
        if not valid:
            return error_msg

        # 检查不能对未来日期补签
        try:
            target_date = dt.date(target_year, target_month, day)
        except ValueError:
            return "日期无效"

        if target_date > today:
            return "不能对未来的日期补🦌哦~"

        user_id = normalize_user_id(event.get_sender_id())
        db = await self.db.get_connection()
        try:
            # 检查今日补签次数是否已达上限
            limits_config = self.config.get("limits", {})
            daily_retro_limit = limits_config.get("daily_retro_limit", 1)

            retro_count_today = await self.db.get_today_retro_count(db, user_id)
            if retro_count_today >= daily_retro_limit:
                return MessageTemplates.get("deer_past_limit")

            # 执行补 deer
            await self.db.record_attendance(db, user_id, target_year, target_month, day)
            await self.db.increment_retro_count(db, user_id, today.isoformat())
            await db.commit()
        except Exception as exc:
            logger.error(f"deer_past failed: {exc}")
            return MessageTemplates.get("operation_failed")
        finally:
            await db.close()

        return MessageTemplates.get("deer_past_success", month=target_month, day=day)

    async def render_calendar(
        self,
        event: AstrMessageEvent,
        month_date: dt.date,
        html_render_func,
        user_id: str | None = None,
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
            user_id = normalize_user_id(event.get_sender_id())
        else:
            user_id = normalize_user_id(user_id)

        # 从数据库获取日历数据
        db = await self.db.get_connection()
        try:
            month_map = await self.db.get_calendar_data(
                db, user_id, month_date.year, month_date.month
            )
        except Exception as exc:
            logger.error(f"Failed to load calendar data: {exc}")
            yield MessageTemplates.get("calendar_load_failed"), True
            return
        finally:
            await db.close()

        # 尝试渲染图片
        try:
            # 从配置获取显示模式
            calendar_config = self.config.get("calendar", {})
            count_display_mode = calendar_config.get("count_display_mode", "additive")
            show_check_mark = calendar_config.get("show_check_mark", True)

            image_url = await self.renderer.render(
                html_render_func,
                user_id,
                month_date.year,
                month_date.month,
                month_map,
                count_display_mode,
                show_check_mark,
            )
            yield image_url, False
        except Exception as exc:
            logger.error(f"Calendar render failed: {exc}")
            # 降级：返回纯文本日历
            fallback_text = self._format_fallback_text(
                month_date.year, month_date.month, month_map
            )
            yield fallback_text, True

    @staticmethod
    def _format_fallback_text(
            year: int, month: int, month_map: dict[int, int]
    ) -> str:
        """生成纯文本日历.

        Args:
            year: 年份
            month: 月份
            month_map: 日期到打卡次数的映射

        Returns:
            格式化的纯文本日历
        """
        total = sum(month_map.values())
        days_recorded = len(month_map)

        # 构建日历表头
        header = MessageTemplates.get("fallback_calendar_header", year=year, month=month)
        separator = "=" * 29

        # 星期标题 - 使用固定宽度
        weekday_header = "  日   一   二   三   四   五   六"

        # 构建日历主体
        cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
        lines: list[str] = []

        for week in cal.monthdayscalendar(year, month):
            week_strs: list[str] = []
            for day in week:
                if day == 0:
                    week_strs.append("    ")  # 空位 4空格
                elif day in month_map:
                    count = month_map[day]
                    # 有记录的日期显示 ✓+次数，居中在4字符宽度内
                    if count == 1:
                        week_strs.append(" ✓  ")  # 单次打卡
                    else:
                        # 多次打卡显示 ✓数字
                        mark = f"✓{count}"
                        week_strs.append(f"{mark:>4}")
                else:
                    # 未签到日期显示日期数字，右对齐
                    week_strs.append(f"{day:>3} ")
            lines.append("".join(week_strs))

        calendar_body = "\n".join(lines)

        # 统计信息
        stats = MessageTemplates.get("fallback_calendar_stats", days=days_recorded, total=total)

        return (
            f"{header}\n"
            f"{separator}\n"
            f"{weekday_header}\n"
            f"{calendar_body}\n"
            f"{separator}\n"
            f"{stats}\n"
            f"💡 带 ✓ 的为已签到日期，✓数字表示当日打卡次数"
        )
