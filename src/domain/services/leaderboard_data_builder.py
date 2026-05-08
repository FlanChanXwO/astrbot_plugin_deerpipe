"""Leaderboard domain services.

排行榜相关的领域服务，包含纯业务逻辑。
"""

from __future__ import annotations

from typing import Any


class LeaderboardDataBuilder:
    """排行榜数据构建器.

    负责将原始排行榜数据转换为展示所需的业务数据结构。
    """

    @staticmethod
    def build_display_data(
        leaderboard_data: list[tuple[str, int]],
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """构建排行榜显示数据.

        业务规则：
        - 只显示前 N 名
        - 用户名匿名化（只显示后4位）

        Args:
            leaderboard_data: 原始排行榜数据 [(user_id, count), ...]
            top_n: 显示前N名

        Returns:
            格式化后的排行榜数据
        """
        display_data = []

        for uid, count in leaderboard_data[:top_n]:
            # 匿名化用户名：只显示后4位
            name = f"用户{uid[-4:] if len(uid) > 4 else uid}"
            display_data.append({"name": name, "count": count})

        return display_data

    @staticmethod
    def calculate_statistics(
        leaderboard_data: list[tuple[str, int]],
    ) -> tuple[int, int]:
        """计算排行榜统计信息.

        Args:
            leaderboard_data: 排行榜数据

        Returns:
            (总打卡次数, 总用户数)
        """
        total_count = sum(count for _, count in leaderboard_data)
        total_users = len(leaderboard_data)

        return total_count, total_users

    @staticmethod
    def find_user_rank(
        leaderboard_data: list[tuple[str, int]],
        user_id: str,
    ) -> tuple[int | None, int]:
        """查找用户在排行榜中的位置.

        Args:
            leaderboard_data: 排行榜数据
            user_id: 用户ID

        Returns:
            (排名, 打卡次数)，如果未找到则返回 (None, 0)
        """
        for i, (uid, count) in enumerate(leaderboard_data):
            if uid == user_id:
                return i + 1, count

        return None, 0

    @staticmethod
    def format_leaderboard_medals(index: int) -> str:
        """格式化排名奖牌.

        Args:
            index: 排名索引（从0开始）

        Returns:
            奖牌符号或排名数字
        """
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        if index < len(medals):
            return medals[index]
        return f"{index + 1}."
