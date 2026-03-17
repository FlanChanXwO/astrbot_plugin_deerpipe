"""Deer-pipe plugin LLM Tools.

AI工具函数模块，为LLM提供结构化的数据访问能力。
所有工具函数返回字典格式的数据，便于AI分析。
"""

from __future__ import annotations

import calendar
import datetime as dt
from typing import Any

from .commands import DeerPipeService
from .data_manager import DataManager
from .database import DatabaseManager


class DeerPipeLLMTools:
    """鹿管插件AI工具集合.

    提供结构化的数据访问，使AI能够分析用户的打卡数据。
    """

    def __init__(
        self,
        db: DatabaseManager,
        data_manager: DataManager,
        service: DeerPipeService,
        config: dict | None = None,
    ) -> None:
        """初始化AI工具.

        Args:
            db: 数据库管理器
            data_manager: 数据管理器
            service: 业务服务
            config: 插件配置
        """
        self.db = db
        self.data_manager = data_manager
        self.service = service
        self.config = config or {}

    def _is_ai_help_deer_allowed(self) -> bool:
        """检查是否允许AI帮用户🦌.

        Returns:
            True表示允许
        """
        ai_config = self.config.get("ai_behavior", {})
        return ai_config.get("allow_ai_help_deer", True)

    def _is_ai_be_deered_allowed(self) -> bool:
        """检查是否允许AI被🦌.

        Returns:
            True表示允许
        """
        ai_config = self.config.get("ai_behavior", {})
        return ai_config.get("allow_ai_be_deered", False)

    def _get_daily_retro_limit(self) -> int:
        """获取每日补🦌次数限制.

        Returns:
            每日补🦌次数限制，0表示禁止，最大31
        """
        limits_config = self.config.get("limits", {})
        limit = limits_config.get("daily_retro_limit", 1)
        # 防御性校验：负数视为0（禁止），过大值限制为31
        if not isinstance(limit, int):
            return 1
        if limit < 0:
            return 0
        if limit > 31:
            return 31
        return limit

    async def deer_self(self, user_id: str) -> dict[str, Any]:
        """用户自我打卡.

        Args:
            user_id: 用户ID

        Returns:
            打卡结果数据
        """
        today = dt.date.today()

        db = await self.db.get_connection()
        try:
            await self.db.ensure_user_config(db, user_id)
            await self.db.record_attendance(
                db, user_id, today.year, today.month, today.day
            )
            await db.commit()

            # 获取本月数据用于返回
            month_map = await self.db.get_calendar_data(
                db, user_id, today.year, today.month
            )
            total = sum(month_map.values())
            days_recorded = len(month_map)

            return {
                "success": True,
                "user_id": user_id,
                "date": today.isoformat(),
                "year": today.year,
                "month": today.month,
                "day": today.day,
                "message": "成功🦌了",
                "stats": {
                    "total_count": total,
                    "days_recorded": days_recorded,
                    "today_count": month_map.get(today.day, 0),
                },
                "calendar_data": month_map,
            }
        except Exception:
            return {
                "success": False,
                "user_id": user_id,
                "error": "INTERNAL_ERROR",
                "message": "操作失败，请稍后重试。",
            }
        finally:
            await db.close()

    def _is_ai_help_self_allowed(self) -> bool:
        """检查是否允许AI帮发消息的用户自己打卡.

        Returns:
            True表示允许
        """
        ai_config = self.config.get("ai_behavior", {})
        return ai_config.get("allow_ai_help_self", True)

    async def deer_other(
        self, operator_id: str, target_ids: list[str], bot_id: str | None = None
    ) -> dict[str, Any]:
        """帮他人打卡.

        Args:
            operator_id: 操作用户ID
            target_ids: 目标用户ID列表
            bot_id: Bot自身的ID，用于判断是否在帮AI打卡

        Returns:
            打卡结果数据
        """
        # 检查是否允许AI帮用户🦌
        if not self._is_ai_help_deer_allowed():
            return {
                "success": False,
                "error": "AI_HELP_DEER_DISABLED",
                "message": "当前配置禁止AI帮用户🦌，请使用 /🦌 或 /鹿 命令自行打卡。",
            }

        # 检查是否允许AI帮用户自己打卡（如果operator在target列表中）
        if operator_id in target_ids and not self._is_ai_help_self_allowed():
            return {
                "success": False,
                "error": "AI_HELP_SELF_DISABLED",
                "message": "当前配置禁止AI帮用户自己打卡，请使用 /🦌 或 /鹿 命令自行打卡。",
            }

        # 检查是否允许用户帮AI🦌（如果目标包含Bot）
        if bot_id and bot_id in target_ids and not self._is_ai_be_deered_allowed():
            return {
                "success": False,
                "error": "AI_BE_DEERED_DISABLED",
                "message": "当前配置禁止帮AI🦌。",
            }

        today = dt.date.today()
        results = []

        db = await self.db.get_connection()
        try:
            for target_id in target_ids:
                allowed = await self.db.is_help_allowed(db, target_id)
                if not allowed:
                    results.append(
                        {
                            "target_id": target_id,
                            "success": False,
                            "message": f"用户 {target_id} 不允许被帮🦌",
                            "allowed": False,
                        }
                    )
                    continue

                await self.db.record_attendance(
                    db, target_id, today.year, today.month, today.day
                )
                results.append(
                    {
                        "target_id": target_id,
                        "success": True,
                        "message": f"成功帮 {target_id}🦌了",
                        "allowed": True,
                    }
                )
            await db.commit()

            return {
                "success": True,
                "operator_id": operator_id,
                "date": today.isoformat(),
                "results": results,
            }
        except Exception:
            return {
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": "操作失败，请稍后重试。",
            }
        finally:
            await db.close()

    async def get_calendar(
        self, user_id: str, year: int | None = None, month: int | None = None
    ) -> dict[str, Any]:
        """获取用户日历数据.

        Args:
            user_id: 用户ID
            year: 年份，默认为当前年份
            month: 月份，默认为当前月份

        Returns:
            日历数据
        """
        today = dt.date.today()
        year = year or today.year
        month = month or today.month

        db = await self.db.get_connection()
        try:
            month_map = await self.db.get_calendar_data(db, user_id, year, month)
            total = sum(month_map.values())
            days_recorded = len(month_map)

            # 计算连续打卡天数
            consecutive_days = self._calculate_consecutive_days(month_map, year, month)

            # 计算打卡频率
            max_day = dt.date(year, month, 1)
            if month == 12:
                next_month = dt.date(year + 1, 1, 1)
            else:
                next_month = dt.date(year, month + 1, 1)
            days_in_month = (next_month - max_day).days

            frequency = days_recorded / days_in_month if days_in_month > 0 else 0

            return {
                "success": True,
                "user_id": user_id,
                "year": year,
                "month": month,
                "calendar": month_map,
                "stats": {
                    "total_count": total,
                    "days_recorded": days_recorded,
                    "consecutive_days": consecutive_days,
                    "frequency": round(frequency, 2),
                    "frequency_percent": round(frequency * 100, 1),
                },
                "analysis": {
                    "most_active_day": max(month_map, key=month_map.get)
                    if month_map
                    else None,
                    "average_per_day": round(total / days_recorded, 2)
                    if days_recorded > 0
                    else 0,
                },
            }
        except Exception as e:
            return {
                "success": False,
                "user_id": user_id,
                "error": str(e),
                "message": "加载🦌历失败。",
            }
        finally:
            await db.close()

    def _calculate_consecutive_days(
        self, month_map: dict[int, int], year: int, month: int
    ) -> int:
        """计算连续打卡天数."""
        if not month_map:
            return 0

        sorted_days = sorted(month_map.keys())
        if not sorted_days:
            return 0

        consecutive = 1
        max_consecutive = 1

        for i in range(1, len(sorted_days)):
            if sorted_days[i] == sorted_days[i - 1] + 1:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 1

        return max_consecutive

    async def retro_deer(
        self, user_id: str, day: int, year: int | None = None, month: int | None = None
    ) -> dict[str, Any]:
        """补打卡.

        Args:
            user_id: 用户ID
            day: 日期
            year: 年份，默认为当前年份
            month: 月份，默认为当前月份

        Returns:
            补打卡结果
        """
        # 检查每日补🦌次数限制
        daily_limit = self._get_daily_retro_limit()
        if daily_limit <= 0:
            return {
                "success": False,
                "error": "RETRO_DEER_DISABLED",
                "message": "当前配置禁止补🦌功能。",
            }

        today = dt.date.today()
        year = year or today.year
        month = month or today.month

        # 验证日期
        if day < 1 or day > calendar.monthrange(year, month)[1]:
            return {
                "success": False,
                "error": f"日期无效，本月范围为 1-{calendar.monthrange(year, month)[1]}",
            }

        # 检查不能对未来日期补签
        target_date = dt.date(year, month, day)
        if target_date > today:
            return {
                "success": False,
                "error": "FUTURE_DATE_NOT_ALLOWED",
                "message": "不能对未来的日期补🦌哦~",
            }

        db = await self.db.get_connection()
        try:
            # 检查今日补🦌次数
            retro_count = await self.db.get_today_retro_count(db, user_id)
            if retro_count >= daily_limit:
                return {
                    "success": False,
                    "error": "DAILY_LIMIT_REACHED",
                    "message": f"今天已经补🦌 {retro_count} 次了，每日限制 {daily_limit} 次。",
                    "retro_count": retro_count,
                    "daily_limit": daily_limit,
                }

            # 执行补打卡
            await self.db.record_attendance(db, user_id, year, month, day)
            await self.db.increment_retro_count(db, user_id, today.isoformat())
            await db.commit()

            return {
                "success": True,
                "user_id": user_id,
                "retro_date": f"{year}-{month:02d}-{day:02d}",
                "message": f"补🦌成功：{month}月{day}日",
                "retro_count": retro_count + 1,
                "daily_limit": daily_limit,
            }
        except Exception:
            return {
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": "操作失败，请稍后重试。",
            }
        finally:
            await db.close()

    async def set_allow_help(self, user_id: str, allowed: bool) -> dict[str, Any]:
        """设置是否允许他人帮打卡.

        Args:
            user_id: 用户ID
            allowed: 是否允许

        Returns:
            设置结果
        """
        db = await self.db.get_connection()
        try:
            await self.db.set_help_allowed(db, user_id, allowed)
            await db.commit()

            return {
                "success": True,
                "user_id": user_id,
                "allowed": allowed,
                "message": "已开启，现在别人可以帮你🦌了~"
                if allowed
                else "已关闭，现在只有你自己能🦌了！",
            }
        except Exception:
            return {
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": "操作失败，请稍后重试。",
            }
        finally:
            await db.close()

    async def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """获取用户统计信息.

        Args:
            user_id: 用户ID

        Returns:
            用户统计
        """
        db = await self.db.get_connection()
        try:
            today = dt.date.today()

            # 获取本月数据
            month_map = await self.db.get_calendar_data(
                db, user_id, today.year, today.month
            )

            # 获取允许设置
            allowed = await self.db.is_help_allowed(db, user_id)

            # 计算总体统计
            total_count = sum(month_map.values())
            days_recorded = len(month_map)

            # 获取用户配置信息
            await self.db.ensure_user_config(db, user_id)
            cursor = await db.execute(
                "SELECT last_retro_date FROM deer_config WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            last_retro = row[0] if row else None

            return {
                "success": True,
                "user_id": user_id,
                "allow_help": allowed,
                "current_month": {
                    "year": today.year,
                    "month": today.month,
                    "total_count": total_count,
                    "days_recorded": days_recorded,
                    "calendar": month_map,
                },
                "last_retro": last_retro,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await db.close()
