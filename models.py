"""Deer-pipe plugin data models.

定义插件使用的数据类，包括日历数据和用户配置。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class CalendarDay(TypedDict):
    """日历中单日数据类型."""

    day_of_month: int  # 日期 (0 表示该位置无日期)
    count: int  # 当日打卡次数


class CalendarAssets(TypedDict):
    """日历模板所需资源数据."""

    character: str  # 角色图片 base64 data URI
    deer_pipe: str  # deer pipe 图片 base64 data URI
    check: str  # 勾选图标 base64 data URI


@dataclass
class UserConfig:
    """用户配置数据模型.

    Attributes:
        user_id: 用户唯一标识
        allow_help: 是否允许他人帮🦌
        last_retro_date: 上次补🦌日期 (ISO格式字符串)
    """

    user_id: str
    allow_help: bool = True
    last_retro_date: str = ""


@dataclass
class DeerRecord:
    """🦌打卡记录数据模型.

    Attributes:
        user_id: 用户唯一标识
        year: 年份
        month: 月份
        day: 日期
        count: 当日打卡次数
    """

    user_id: str
    year: int
    month: int
    day: int
    count: int


@dataclass
class CalendarPayload:
    """日历渲染所需的数据负载.

    Attributes:
        css_style: 内联 CSS 样式
        year: 年份
        month: 月份
        calendar: 日历数据 (按周分组)
        avatar_base64: 用户头像 base64 data URI
        assets: 图片资源字典
    """

    css_style: str
    year: int
    month: int
    calendar: list[list[CalendarDay]]
    avatar_base64: str
    assets: CalendarAssets


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
