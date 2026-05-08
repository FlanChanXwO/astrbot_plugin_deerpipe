"""Deermap renderer.

鹿力图（年度热力图）渲染器。
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from ..utils.http_utils import fetch_avatar_base64
from .base_renderer import BaseTemplateRenderer


class DeermapRenderer(BaseTemplateRenderer):
    """鹿力图渲染器.

    处理年度打卡热力图的渲染。
    """

    def __init__(self, base_dir: Path) -> None:
        """初始化鹿力图渲染器.

        Args:
            base_dir: 插件根目录
        """
        super().__init__(
            base_dir=base_dir,
            template_name="deermap",
            css_name="deermap",
        )
        self.base_dir = base_dir

    async def build_payload(
        self,
        stats_data: dict[str, int],
        year: int,
        user_id: str,
        platform_name: str | None = None,
    ) -> dict[str, Any]:
        """构建鹿力图渲染数据.

        Args:
            stats_data: 日期到打卡次数的映射 {YYYY-MM-DD: count}
            year: 年份
            user_id: 用户ID
            platform_name: 平台名称（用于获取头像）

        Returns:
            渲染数据字典
        """
        # 构建热力图数据
        weeks_data, months, month_start_indices, week_to_month = (
            self._build_deermap_data(stats_data, year)
        )

        # 计算统计信息
        total_days = len(stats_data)
        total_count = sum(stats_data.values())
        max_count = max(stats_data.values()) if stats_data else 0
        avg_count = round(total_count / total_days, 1) if total_days > 0 else 0

        # 获取用户头像
        avatar_b64 = await fetch_avatar_base64(user_id, platform_name)

        # 获取shot图片（如果有）
        shot_b64 = self._load_shot_image()

        return {
            "title": f"{year}年鹿力图",
            "year": year,
            "months": months,
            "week_to_month": week_to_month,
            "weeks": weeks_data,
            "total_days": total_days,
            "total_count": total_count,
            "max_count": max_count,
            "avg_count": avg_count,
            "avatar_base64": avatar_b64,
            "shot_image": shot_b64,
        }

    def _load_shot_image(self) -> str:
        """加载shot图片并转换为base64.

        Returns:
            base64 data URI 或空字符串
        """
        shot_path = self.base_dir / "resources" / "images" / "shot.png"
        if not shot_path.exists():
            return ""

        import base64

        return (
            "data:image/png;base64," + base64.b64encode(shot_path.read_bytes()).decode()
        )

    @staticmethod
    def _build_deermap_data(
        stats_data: dict[str, int],
        year: int,
    ) -> tuple[list[list[dict]], list[str], list[int], list[int]]:
        """构建鹿力图数据.

        Args:
            stats_data: 日期到打卡次数的映射
            year: 年份

        Returns:
            (weeks_data, months, month_start_indices, week_to_month)
        """

        max_count = max(stats_data.values()) if stats_data else 1

        # 定义颜色等级阈值
        levels = [
            0,
            max_count * 0.2,
            max_count * 0.4,
            max_count * 0.6,
            max_count * 0.8,
            max_count,
        ]

        def get_level(count: int) -> str:
            """根据打卡次数获取颜色等级."""
            if count == 0:
                return "level-0"
            for i, threshold in enumerate(levels[1:], 1):
                if count <= threshold:
                    return f"level-{i}"
            return "level-5"

        weeks_data: list[list[dict]] = []

        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)

        # 调整到周一
        start_date -= datetime.timedelta(days=start_date.weekday())

        current_date = start_date
        week_to_month: list[int] = []
        month_start_indices: list[int] = []

        week_index = 0
        last_month = -1

        while current_date <= end_date or current_date.weekday() != 0:
            if current_date.weekday() == 0:
                week_data = []

                # 使用周四确定月份（ISO 8601 周规则）
                thursday = current_date + datetime.timedelta(days=3)
                m = thursday.month - 1
                week_to_month.append(m)

                if m != last_month:
                    month_start_indices.append(week_index)
                    last_month = m

            if current_date.year == year:
                date_key = current_date.strftime("%Y-%m-%d")
                count = stats_data.get(date_key, 0)
                week_data.append(
                    {"date": date_key, "count": count, "level": get_level(count)}
                )
            else:
                week_data.append({"date": "", "count": 0, "level": "level-0"})

            current_date += datetime.timedelta(days=1)

            if current_date.weekday() == 0:
                weeks_data.append(week_data)
                week_index += 1

        month_names = [
            "1月",
            "2月",
            "3月",
            "4月",
            "5月",
            "6月",
            "7月",
            "8月",
            "9月",
            "10月",
            "11月",
            "12月",
        ]

        return weeks_data, month_names, month_start_indices, week_to_month

    def format_fallback_text(
        self,
        stats_data: dict[str, int],
        year: int,
    ) -> str:
        """格式化鹿力图文本.

        Args:
            stats_data: 日期到打卡次数的映射
            year: 年份

        Returns:
            格式化的文本
        """
        total_days = len(stats_data)
        total_count = sum(stats_data.values())
        max_count = max(stats_data.values()) if stats_data else 0

        lines = [
            f"{year}年鹿力图",
            "",
            "统计信息:",
            f"  鹿天数: {total_days}天",
            f"  总鹿次数: {total_count}次",
            f"  单日最多: {max_count}次",
        ]

        return "\n".join(lines)
