"""Calendar presenter.

日历展示器，负责协调领域服务和基础设施，组装展示数据。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable
from pathlib import Path
from typing import Literal

from ...domain.services import CalendarDataBuilder
from ...infrastructure import (
    ResourceLoader,
    TemplateRenderer,
    get_cached_avatar,
    get_logger,
)

logger = get_logger()


class CalendarPresenter:
    """日历展示器.

    负责组装日历展示所需的数据并调用渲染。
    """

    def __init__(
        self,
        resource_loader: ResourceLoader,
        template_renderer: TemplateRenderer,
    ) -> None:
        """初始化日历展示器.

        Args:
            resource_loader: 资源加载器
            template_renderer: 模板渲染器
        """
        self.resource_loader = resource_loader
        self.template_renderer = template_renderer
        self.data_builder = CalendarDataBuilder()
        self.logger = logger

    async def present_calendar(
        self,
        html_render_func,
        user_id: str,
        year: int,
        month: int,
        month_map: dict[int, int],
        platform_name: str | None = None,
        count_display_mode: Literal["additive", "count"] = "additive",
        show_check_mark: bool = True,
    ) -> str:
        """展示日历图片.

        协调流程：
        1. 使用 domain service 构建业务数据
        2. 使用 infrastructure 加载资源
        3. 使用 infrastructure 渲染模板

        Args:
            html_render_func: HTML渲染函数
            user_id: 用户ID
            year: 年份
            month: 月份
            month_map: 日期到打卡次数的映射
            platform_name: 平台名称
            count_display_mode: 打卡次数显示模式
            show_check_mark: 是否显示打勾图标

        Returns:
            渲染后的图片URL
        """
        # 1. 加载模板和CSS
        html = self.resource_loader.load_template("calendar")
        css_content = self.resource_loader.load_css("calendar")

        # 2. 使用 domain service 构建业务数据
        calendar_weeks = self.data_builder.build_weeks(month_map, year, month)
        character_index = self.data_builder.select_character_index(
            sum(month_map.values()), user_id
        )
        count_mode = self.data_builder.validate_count_display_mode(
            count_display_mode
        )

        # 3. 加载资源（基础设施）
        avatar_b64 = await get_cached_avatar(user_id, platform_name)

        # 根据业务逻辑选择的角色图片
        character_image = self.resource_loader.load_image_as_data_uri(
            f"character_{character_index}.png"
        )
        deer_pipe_image = self.resource_loader.load_image_as_data_uri("deerpipe.png")
        check_image = self.resource_loader.load_image_as_data_uri("check.png")
        undeer_pipe_image = self.resource_loader.load_image_as_data_uri(
            "undeerpipe.png"
        )

        # 4. 判断是否为本月
        today = dt.date.today()
        is_current_month = year == today.year and month == today.month

        # 5. 组装渲染数据
        payload = {
            "css_style": css_content,
            "year": year,
            "month": month,
            "is_current_month": is_current_month,
            "calendar": calendar_weeks,
            "avatar_base64": avatar_b64,
            "assets": {
                "character": character_image,
                "deer_pipe": deer_pipe_image,
                "check": check_image,
                "undeer_pipe": undeer_pipe_image,
            },
            "count_display_mode": count_mode,
            "show_check_mark": show_check_mark,
        }

        # 6. 调用渲染器
        return await self.template_renderer.render(html, payload, html_render_func)

    def format_fallback_text(
        self,
        year: int,
        month: int,
        month_map: dict[int, int],
    ) -> str:
        """生成渲染失败时的纯文本日历.

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
        header = f"📅 {year}年{month}月 鹿历"
        separator = "=" * 28

        # 星期标题
        weekday_header = " 日   一   二   三   四   五   六 "

        # 使用 domain service 构建日历数据
        weeks = self.data_builder.build_weeks(month_map, year, month)

        # 构建日历主体
        lines: list[str] = []

        for week in weeks:
            week_strs: list[str] = []
            for day_data in week:
                day = day_data["day_of_month"]
                count = day_data["count"]

                if day == 0:
                    week_strs.append("    ")  # 空位
                elif count > 0:
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
        stats = f"📊 统计: 共{days_recorded}天 {total}次\n💡 带数字的日期为已打卡次数"

        return (
            f"{header}\n"
            f"{separator}\n"
            f"{weekday_header}\n"
            f"{calendar_body}\n"
            f"{separator}\n"
            f"{stats}"
        )
