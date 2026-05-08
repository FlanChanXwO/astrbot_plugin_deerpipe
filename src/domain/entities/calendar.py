"""Calendar entity.

日历相关实体和值对象。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


class CalendarDay(TypedDict):
    """日历中单日数据类型."""

    day_of_month: int  # 日期 (0 表示该位置无日期)
    count: int  # 当日打卡次数


class CalendarAssets(TypedDict):
    """日历模板所需资源数据."""

    character: str  # 角色图片 base64 data URI
    deer_pipe: str  # deer pipe 图片 base64 data URI
    undeer_pipe: str  # undeer pipe 图片 base64 data URI（用于未签到日期）
    check: str  # 勾选图标 base64 data URI


@dataclass
class CalendarPayload:
    """日历渲染所需的数据负载.

    Attributes:
        css_style: 内联 CSS 样式
        year: 年份
        month: 月份
        is_current_month: 是否是当前月份
        calendar: 日历数据 (按周分组)
        avatar_base64: 用户头像 base64 data URI
        assets: 图片资源字典
        count_display_mode: 打卡次数显示模式 (additive/count)
        show_check_mark: 是否显示打勾图标
    """

    css_style: str
    year: int
    month: int
    calendar: list[list[CalendarDay]]
    avatar_base64: str
    assets: CalendarAssets
    count_display_mode: Literal["additive", "count"] = "additive"
    show_check_mark: bool = True
    is_current_month: bool = False


@dataclass
class MonthStats:
    """月度统计数据.

    Attributes:
        year: 年份
        month: 月份
        total_count: 当月总打卡次数
        days: 日期到次数的映射
    """

    year: int
    month: int
    total_count: int
    days: dict[int, int]
