from __future__ import annotations

import datetime as dt
from typing import TypedDict

from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import At
from astrbot.core.platform.message_type import MessageType

from ...domain import (
    TEMPLATE_CALENDAR_LOAD_FAILED,
    TEMPLATE_DEER_PAST_LIMIT,
    TEMPLATE_DEER_PAST_SUCCESS,
    TEMPLATE_FALLBACK_CALENDAR_HEADER,
    TEMPLATE_FALLBACK_CALENDAR_STATS,
    TEMPLATE_GROUP_ONLY,
    TEMPLATE_OPERATION_FAILED,
    TemplateKeyError,
)
from ...infrastructure import (
    DatabaseManager,
    extract_mention_user_ids,
    get_logger,
    normalize_user_id,
    validate_day,
)
from ..presenters import CalendarPresenter

logger = get_logger()


class DeerResult(TypedDict):
    """打卡结果数据类型."""

    user_id: str
    nickname: str
    success: bool
    count: int
    is_new: bool
    reason: str | None


class MessageTemplates:
    """消息模板管理器.

    统一管理所有文本模板，支持严格格式化检查。
    """

    _TEMPLATES = {
        TEMPLATE_GROUP_ONLY: "该命令仅限群聊使用。",
        TEMPLATE_OPERATION_FAILED: "操作失败，请稍后重试。",
        TEMPLATE_DEER_PAST_LIMIT: "今日补🦌次数已达上限。",
        TEMPLATE_DEER_PAST_SUCCESS: "成功补🦌 {month}月{day}日",
        TEMPLATE_CALENDAR_LOAD_FAILED: "日历数据加载失败。",
        TEMPLATE_FALLBACK_CALENDAR_HEADER: "📅 {year}年{month}月 鹿历",
        TEMPLATE_FALLBACK_CALENDAR_STATS: "📊 统计: 共{days}天 {total}次",
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
        calendar_presenter: CalendarPresenter,
        config: dict | None = None,
    ) -> None:
        """初始化服务.

        Args:
            db: 数据库管理器实例
            calendar_presenter: 日历展示器实例
            config: 插件配置字典
        """
        self.db = db
        self.calendar_presenter = calendar_presenter
        self.config = config or {}

    async def batch_deer_other(
        self,
        event: AstrMessageEvent,
        sender_id: str,
        at_ids: set[str],
        at_list: list[At],
        self_id: str | None = None,
    ) -> list[DeerResult]:
        """批量帮他人打卡.

        Args:
            event: 消息事件（用于获取 group_id）
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

        # 获取群ID（如果不是群聊则设为 None）
        group_id = None
        if event.get_message_type() == MessageType.GROUP_MESSAGE:
            group_id = str(event.get_group_id()) if event.get_group_id() else None

        # 检查是否帮Bot自己打卡
        if self_id and self_id in at_ids:
            results.append(
                {
                    "user_id": self_id,
                    "nickname": "Bot",
                    "success": False,
                    "count": 0,
                    "is_new": False,
                    "reason": "不可以帮 Bot🦌哦~",
                }
            )
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
                    results.append(
                        {
                            "user_id": target_id,
                            "nickname": target_name,
                            "success": False,
                            "count": 0,
                            "is_new": False,
                            "reason": "不能帮全体成员🦌",
                        }
                    )
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
                        results.append(
                            {
                                "user_id": target_id,
                                "nickname": target_name,
                                "success": False,
                                "count": 0,
                                "is_new": False,
                                "reason": "不允许被帮🦌",
                            }
                        )
                        continue

                # 记录打卡前检查是否已有记录（用于判断 is_new）
                has_record_before = await self.db.has_record_today(db, target_id)

                await self.db.record_attendance(
                    db, target_id, today.year, today.month, today.day, group_id
                )

                # 获取更新后的次数
                month_map = await self.db.get_calendar_data(
                    db, target_id, today.year, today.month
                )
                today_count = month_map.get(today.day, 0)

                results.append(
                    {
                        "user_id": target_id,
                        "nickname": target_name,
                        "success": True,
                        "count": today_count,
                        "is_new": not has_record_before,
                        "reason": None,
                    }
                )

            await db.commit()
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

        # 获取群ID（如果不是群聊则设为 None）
        group_id = None
        if event.get_message_type() == MessageType.GROUP_MESSAGE:
            group_id = str(event.get_group_id()) if event.get_group_id() else None

        db = await self.db.get_connection()
        try:
            await self.db.ensure_user_config(db, user_id)
            await self.db.record_attendance(
                db, user_id, today.year, today.month, today.day, group_id
            )
            await db.commit()
        except (OSError, RuntimeError) as exc:
            logger.error(f"deer_self failed: {exc}")
            return "操作失败，请稍后重试。"
        finally:
            await db.close()

        return "成功🦌了"

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
            f"handle_set_self_help: raw user_id={user_id}, name={sender_name}, allowed={allowed}"
        )

        db = await self.db.get_connection()
        try:
            await self.db.set_help_allowed(db, user_id, allowed)
            await db.commit()
            logger.debug(f"用户 {user_id} 设置 allow_help={allowed} 成功")
        except (OSError, RuntimeError) as exc:
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
            try:
                return MessageTemplates.get("group_only")
            except TemplateKeyError as e:
                logger.error(f"Template error: {e}")
                return "该命令仅限群聊使用。"
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
                logger.debug(f"管理员设置用户 {target_id} allow_help={allowed}")
            await db.commit()
        except (OSError, RuntimeError) as exc:
            logger.error(f"set_other_help_status failed: {exc}")
            try:
                return MessageTemplates.get("operation_failed")
            except TemplateKeyError as e:
                logger.error(f"Template error: {e}")
                return "操作失败，请稍后重试。"
        finally:
            await db.close()

        return "\n".join(logs) if logs else "没有成功设置任何用户。"

    async def handle_deer_past(
        self,
        event: AstrMessageEvent,
        day: int,
        year: int | None = None,
        month: int | None = None,
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
                try:
                    return MessageTemplates.get("deer_past_limit")
                except TemplateKeyError as e:
                    logger.error(f"Template error: {e}")
                    return "操作失败，请稍后重试。"

            # 执行补 deer
            await self.db.record_attendance(db, user_id, target_year, target_month, day)
            await self.db.increment_retro_count(db, user_id, today.isoformat())
            await db.commit()
        except (OSError, RuntimeError) as exc:
            logger.error(f"deer_past failed: {exc}")
            try:
                return MessageTemplates.get("operation_failed")
            except TemplateKeyError as e:
                logger.error(f"Template error: {e}")
                return "操作失败，请稍后重试。"
        finally:
            await db.close()

        try:
            return MessageTemplates.get(
                "deer_past_success", month=target_month, day=day
            )
        except TemplateKeyError as e:
            logger.error(f"Template error: {e}")
            return f"成功补🦌 {target_month}月{day}日"

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

        # 获取平台名称，用于头像获取
        platform_name = event.get_platform_name()

        # 从数据库获取日历数据
        db = await self.db.get_connection()
        try:
            month_map = await self.db.get_calendar_data(
                db, user_id, month_date.year, month_date.month
            )
        except (OSError, RuntimeError) as exc:
            logger.error(f"Failed to load calendar data ({type(exc).__name__})")
            try:
                yield MessageTemplates.get("calendar_load_failed"), True
            except TemplateKeyError as e:
                logger.error(f"Template error: {e}")
                yield "日历数据加载失败。", True
            return
        finally:
            await db.close()

        # 尝试渲染图片
        try:
            # 从配置获取显示模式
            calendar_config = self.config.get("calendar", {})
            count_display_mode = calendar_config.get("count_display_mode", "additive")
            show_check_mark = calendar_config.get("show_check_mark", True)

            image_url = await self.calendar_presenter.present_calendar(
                html_render_func,
                user_id,
                month_date.year,
                month_date.month,
                month_map,
                platform_name,
                count_display_mode,
                show_check_mark,
            )
            yield image_url, False
        except (OSError, RuntimeError, ValueError) as exc:
            logger.error(f"Calendar render failed ({type(exc).__name__})")
            # 降级：返回纯文本日历
            fallback_text = self.calendar_presenter.format_fallback_text(
                month_date.year, month_date.month, month_map
            )
            yield fallback_text, True
        except TemplateKeyError as e:
            logger.error(f"Template error: {e}")
            fallback_text = self.calendar_presenter.format_fallback_text(
                month_date.year, month_date.month, month_map
            )
            yield fallback_text, True
