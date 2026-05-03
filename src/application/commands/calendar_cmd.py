"""Calendar query command handlers.

处理与日历查看相关的命令。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from astrbot.core.message.components import At

from ...infrastructure import extract_mention_user_ids, get_logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ...application.services import DeerPipeService

logger = get_logger()


class CalendarCommandHandler:
    """日历查询命令处理器.

    轻量级处理器，通过构造函数接收必要的依赖。
    """

    def __init__(self, service: DeerPipeService) -> None:
        """初始化命令处理器.

        Args:
            service: 鹿管业务服务实例
        """
        self.service = service
        self.logger = logger

    async def handle_calendar_query(
        self,
        event: AstrMessageEvent,
        html_render,
        target_date: dt.date,
        title: str | None = None,
    ) -> AsyncGenerator[Any, None]:
        """处理指定月份日历查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数
            target_date: 目标月份日期（只需年月有效）
            title: 自定义标题，None则使用默认标题

        Yields:
            发送给用户的响应
        """
        year = target_date.year
        month = target_date.month

        # 构建标题
        display_title = title if title else f"📅 {year}年{month}月鹿历"

        async for result in self._run_calendar_query(
            event,
            target_date,
            html_render,
            "calendar",
            self_title=display_title,
        ):
            yield result

    async def handle_current_month_calendar(
        self, event: AstrMessageEvent, html_render
    ) -> AsyncGenerator[Any, None]:
        """处理本月日历查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数

        Yields:
            发送给用户的响应
        """
        async for result in self._run_calendar_query(
            event, dt.date.today(), html_render, "calendar"
        ):
            yield result

    async def handle_last_month_calendar(
        self, event: AstrMessageEvent, html_render
    ) -> AsyncGenerator[Any, None]:
        """处理上月日历查询.

        Args:
            event: 消息事件
            html_render: HTML渲染函数

        Yields:
            发送给用户的响应
        """
        first = dt.date.today().replace(day=1)
        last_month = (first - dt.timedelta(days=1)).replace(day=1)

        async for result in self._run_calendar_query(
            event,
            last_month,
            html_render,
            "last_month_calendar",
            self_title="📅 上月鹿历",
            other_title_suffix="的上月鹿历",
        ):
            yield result

    async def _run_calendar_query(
        self,
        event: AstrMessageEvent,
        month_date: dt.date,
        html_render,
        dedup_key: str,
        self_title: str | None = None,
        other_title_suffix: str = "的鹿历",
    ) -> AsyncGenerator[Any, None]:
        """运行日历查询流程.

        Args:
            event: 消息事件
            month_date: 目标月份日期
            html_render: HTML渲染函数
            dedup_key: 去重键
            self_title: 自我查看时的标题
            other_title_suffix: 查看他人时的标题后缀

        Yields:
            发送给用户的响应
        """
        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)
        at_map = {str(m.qq): m.name for m in at_list if m.name}

        if at_ids:
            target_id = str(at_list[0].qq)
            target_name = at_map.get(target_id, target_id)
            async for result, is_text in self.service.render_calendar(
                event, month_date, html_render, user_id=target_id
            ):
                if is_text:
                    yield event.plain_result(
                        f"{target_name} {other_title_suffix}：\n{result}"
                    )
                else:
                    yield event.image_result(result)
            return

        async for result, is_text in self.service.render_calendar(
            event, month_date, html_render
        ):
            if is_text:
                prefix = f"{self_title}\n" if self_title else ""
                yield event.plain_result(f"{prefix}{result}")
            else:
                yield event.image_result(result)
