"""Calendar domain services.

日历相关的领域服务，包含纯业务逻辑。
"""

from __future__ import annotations

import calendar
import hashlib
from typing import Literal

from ..entities import CalendarDay
from ...shared.constants import (
    CHARACTER_RANGE_HIGH,
    CHARACTER_RANGE_LOW,
    CHARACTER_RANGE_MEDIUM,
    CHARACTER_THRESHOLD_HIGH,
    CHARACTER_THRESHOLD_MEDIUM,
)


class CalendarDataBuilder:
    """日历数据构建器.

    负责将原始打卡数据转换为日历展示所需的业务数据结构。
    """

    @staticmethod
    def build_weeks(
        month_map: dict[int, int], year: int, month: int
    ) -> list[list[CalendarDay]]:
        """构建按周分组的日历数据.

        Args:
            month_map: 日期到打卡次数的映射
            year: 年份
            month: 月份

        Returns:
            按周分组的日历数据
        """
        cal = calendar.Calendar(firstweekday=0)
        weeks: list[list[CalendarDay]] = []

        for week in cal.monthdayscalendar(year, month):
            # 跳过完全为空的周（比如月初之前的周）
            if all(day == 0 for day in week):
                continue

            week_data: list[CalendarDay] = []
            for day in week:
                week_data.append(
                    {
                        "day_of_month": day,
                        "count": month_map.get(day, 0) if day else 0,
                    }
                )
            weeks.append(week_data)

        return weeks

    @staticmethod
    def select_character_index(total_count: int, user_id: str) -> int:
        """根据打卡次数和用户ID确定性地选择角色图片索引.

        业务规则：
        - count >= 50: character_9~11 (高阶角色)
        - count >= 20: character_5~8  (中阶角色)
        - 其他: character_1~4        (初阶角色)

        使用 user_id 哈希确保同一用户同月渲染结果稳定。

        Args:
            total_count: 当月总打卡次数
            user_id: 用户ID，用于确定性选择

        Returns:
            角色图片的索引
        """
        # 根据打卡次数确定范围
        if total_count >= CHARACTER_THRESHOLD_HIGH:
            # 高阶角色
            start, end = CHARACTER_RANGE_HIGH
        elif total_count >= CHARACTER_THRESHOLD_MEDIUM:
            # 中阶角色
            start, end = CHARACTER_RANGE_MEDIUM
        else:
            # 初阶角色
            start, end = CHARACTER_RANGE_LOW

        # 使用 user_id 哈希确定性地选择索引
        # 注意：使用 hashlib.md5 仅用于非安全目的的确定性哈希（资源选择），
        # 不涉及密码学安全场景。
        hash_input = f"{user_id}:{total_count}".encode()
        hash_hex = hashlib.md5(hash_input).hexdigest()
        hash_value = int(hash_hex, 16)
        index = start + (hash_value % (end - start + 1))

        return index

    @staticmethod
    def validate_count_display_mode(
        mode: str,
    ) -> Literal["additive", "count"]:
        """验证并规范化打卡次数显示模式.

        Args:
            mode: 显示模式

        Returns:
            规范化后的显示模式
        """
        if mode not in ("additive", "count"):
            return "additive"
        return mode
