"""Deermap domain services.

鹿力图相关的领域服务，包含纯业务逻辑。
"""

from __future__ import annotations

import datetime
from typing import Any


class DeermapDataBuilder:
    """鹿力图数据构建器.

    负责将年度打卡数据转换为热力图展示所需的业务数据结构。
    """

    @staticmethod
    def build_heatmap_data(
        stats_data: dict[str, int],
        year: int,
    ) -> tuple[list[list[dict]], list[str], list[int]]:
        """构建热力图数据.

        业务规则：
        - 按 ISO 8601 标准组织周数据（周一为第一天）
        - 使用周四确定周所属月份
        - 颜色等级分为5级（level-0 到 level-4）
        - 颜色等级按最大值的 0%, 20%, 40%, 60%, 80%, 100% 分档

        Args:
            stats_data: 日期到打卡次数的映射 {YYYY-MM-DD: count}
            year: 年份

        Returns:
            (weeks_data, months, week_to_month)
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
            return "level-4"

        weeks_data: list[list[dict]] = []

        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)

        # 调整到周一
        start_date -= datetime.timedelta(days=start_date.weekday())

        current_date = start_date
        week_to_month: list[int] = []

        week_index = 0
        last_month = -1

        while current_date <= end_date or current_date.weekday() != 0:
            if current_date.weekday() == 0:
                week_data = []

                # 使用周四确定月份（ISO 8601 周规则）
                thursday = current_date + datetime.timedelta(days=3)
                m = thursday.month - 1
                week_to_month.append(m)

                # 记录月份变更（用于显示月份标签）
                if m != last_month:
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

        return weeks_data, month_names, week_to_month

    @staticmethod
    def calculate_statistics(
        stats_data: dict[str, int],
    ) -> tuple[int, int, int, float]:
        """计算鹿力图统计信息.

        Args:
            stats_data: 日期到打卡次数的映射

        Returns:
            (总天数, 总打卡次数, 单日最多, 平均打卡次数)
        """
        total_days = len(stats_data)
        total_count = sum(stats_data.values())
        max_count = max(stats_data.values()) if stats_data else 0
        avg_count = round(total_count / total_days, 1) if total_days > 0 else 0

        return total_days, total_count, max_count, avg_count
