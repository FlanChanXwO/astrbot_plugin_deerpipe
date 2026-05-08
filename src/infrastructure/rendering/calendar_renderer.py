"""Calendar renderer.

日历渲染器，处理月度打卡日历的渲染。
"""

from __future__ import annotations

import asyncio
import calendar
import datetime as dt
import hashlib
from collections.abc import Awaitable
from pathlib import Path
from typing import Literal, cast

from ...domain import (
    CHARACTER_RANGE_HIGH,
    CHARACTER_RANGE_LOW,
    CHARACTER_RANGE_MEDIUM,
    CHARACTER_THRESHOLD_HIGH,
    CHARACTER_THRESHOLD_MEDIUM,
    CalendarAssets,
    CalendarDay,
    CalendarPayload,
)
from ..cache import get_cached_avatar
from ..utils.http_utils import image_to_data_uri
from ..utils.logger import get_logger
from .base_renderer import BaseTemplateRenderer

logger = get_logger()


class CalendarRenderer(BaseTemplateRenderer):
    """日历渲染器.

    处理月度打卡日历的图片渲染和文本回退。
    """

    def __init__(self, base_dir: Path) -> None:
        """初始化日历渲染器.

        Args:
            base_dir: 插件根目录
        """
        super().__init__(
            base_dir=base_dir,
            template_name="calendar",
            css_name="calendar",
        )
        self.base_dir = base_dir

        # 获取图片目录路径
        from ...shared import ResourcePaths

        paths = ResourcePaths(base_dir)
        self.images_dir = paths.images_dir()

    def _get_image_data_uri(self, image_name: str) -> str:
        """获取图片的 base64 data URI.

        Args:
            image_name: 图片文件名

        Returns:
            base64 data URI 或空字符串
        """
        image_path = self.images_dir / image_name
        return image_to_data_uri(image_path)

    def _get_character_image(self, total_count: int, user_id: str) -> str:
        """根据打卡次数和用户ID确定性地选择角色图片.

        参考Java实现的分组逻辑:
        - count >= 50: character_9~11
        - count >= 20: character_5~8
        - 其他: character_1~4

        使用user_id哈希确保同一用户同月渲染结果稳定。

        Args:
            total_count: 当月总打卡次数
            user_id: 用户ID，用于确定性选择

        Returns:
            角色图片的 base64 data URI
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

        # 使用user_id哈希确定性地选择索引
        # 注意：使用 hashlib.md5 仅用于非安全目的的确定性哈希（资源选择），
        # 不涉及密码学安全场景。这样可以保证同一用户跨进程渲染结果一致。
        hash_input = f"{user_id}:{total_count}".encode()
        hash_hex = hashlib.md5(hash_input).hexdigest()
        hash_value = int(hash_hex, 16)
        index = start + (hash_value % (end - start + 1))

        return self._get_image_data_uri(f"character_{index}.png")

    def _load_assets(
        self, user_id: str, month_map: dict[int, int] | None = None
    ) -> CalendarAssets:
        """加载日历所需的图片资源.

        Args:
            user_id: 用户ID，用于确定性选择角色图片
            month_map: 日期到打卡次数的映射，用于确定角色图片

        Returns:
            图片资源字典
        """
        # 计算总打卡次数，用于选择角色图片
        total_count = sum(month_map.values()) if month_map else 0

        return {
            "character": self._get_character_image(total_count, user_id),
            "deer_pipe": self._get_image_data_uri("deerpipe.png"),
            "check": self._get_image_data_uri("check.png"),
            "undeer_pipe": self._get_image_data_uri("undeerpipe.png"),
        }

    @staticmethod
    def _build_calendar_data(
        month_map: dict[int, int], year: int, month: int
    ) -> list[list[CalendarDay]]:
        """构建日历数据结构.

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

    async def build_payload(
        self,
        user_id: str,
        year: int,
        month: int,
        month_map: dict[int, int],
        platform_name: str | None = None,
        count_display_mode: Literal["additive", "count"] = "additive",
        show_check_mark: bool = True,
    ) -> dict:
        """构建日历渲染所需的完整数据负载.

        Args:
            user_id: 用户 ID (用于获取头像)
            year: 年份
            month: 月份
            month_map: 日期到打卡次数的映射
            platform_name: 平台类型名称（如 aiocqhttp, discord 等）
            count_display_mode: 打卡次数显示模式
            show_check_mark: 是否显示打勾图标

        Returns:
            日历渲染数据负载
        """
        # 验证并规范化 count_display_mode
        if count_display_mode not in ("additive", "count"):
            logger.warning(
                f"Invalid count_display_mode: {count_display_mode}, using 'additive'"
            )
            count_display_mode = cast(Literal["additive", "count"], "additive")

        # 构建日历数据
        calendar_weeks = self._build_calendar_data(month_map, year, month)

        # 获取用户头像（带缓存，传入平台信息）
        avatar_b64 = await get_cached_avatar(user_id, platform_name)

        # 加载图片资源（根据打卡次数选择角色图片）
        assets = self._load_assets(user_id, month_map)

        # 判断是否为本月
        today = dt.date.today()
        is_current_month = year == today.year and month == today.month

        return {
            "year": year,
            "month": month,
            "is_current_month": is_current_month,
            "calendar": calendar_weeks,
            "avatar_base64": avatar_b64,
            "assets": assets,
            "count_display_mode": count_display_mode,
            "show_check_mark": show_check_mark,
        }

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
            格式化的纯文本日历 (包含日历表格和统计信息)
        """
        total = sum(month_map.values())
        days_recorded = len(month_map)

        # 构建日历表头
        header = f"📅 {year}年{month}月 鹿历"
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
        stats = f"📊 统计: 共{days_recorded}天 {total}次\n💡 带数字的日期为已打卡次数"

        return (
            f"{header}\n"
            f"{separator}\n"
            f"{weekday_header}\n"
            f"{calendar_body}\n"
            f"{separator}\n"
            f"{stats}"
        )
