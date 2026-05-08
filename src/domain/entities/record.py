"""Deer record entity.

打卡记录实体和值对象。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeerRecord:
    """🦌打卡记录实体.

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
