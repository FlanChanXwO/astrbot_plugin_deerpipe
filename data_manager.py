"""Deer-pipe plugin data export/import module.

数据导出导入功能模块。
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from astrbot.api import logger

from .database import DatabaseManager


def _is_valid_date(year: int, month: int, day: int) -> bool:
    """验证日期是否真实存在.

    Args:
        year: 年份
        month: 月份
        day: 日期

    Returns:
        日期是否有效
    """
    try:
        dt.date(year, month, day)
        return True
    except ValueError:
        return False


class DataManager:
    """数据管理器.

    处理数据导出导入功能。
    """

    def __init__(self, db: DatabaseManager) -> None:
        """初始化数据管理器.

        Args:
            db: 数据库管理器实例
        """
        self.db = db

    async def export_data(self) -> tuple[bool, str, dict | None]:
        """导出所有数据.

        Returns:
            (是否成功, 消息, 数据字典)
        """
        db = await self.db.get_connection()
        try:
            data = await self.db.export_all_data(db)
            record_count = len(data.get("deer_records", []))
            config_count = len(data.get("user_configs", []))
            msg = f"数据导出成功！共 {config_count} 个用户配置，{record_count} 条打卡记录。"
            return True, msg, data
        except Exception as exc:
            logger.error(f"Export data failed: {exc}")
            return False, "数据导出失败，请稍后重试。", None
        finally:
            await db.close()

    async def import_data(self, data: dict) -> tuple[bool, str]:
        """导入数据.

        Args:
            data: 导入的数据字典

        Returns:
            (是否成功, 消息)
        """
        # 验证数据格式
        if not isinstance(data, dict):
            return False, "数据格式无效，请提供有效的 JSON 对象。"

        if "deer_records" not in data and "user_configs" not in data:
            return False, "数据格式无效，未找到用户配置或打卡记录。"

        # 验证 user_configs 结构
        if "user_configs" in data:
            if not isinstance(data["user_configs"], list):
                return False, "数据格式无效：user_configs 必须是数组。"
            for i, config in enumerate(data["user_configs"]):
                if not isinstance(config, dict):
                    return False, f"数据格式无效：user_configs[{i}] 必须是对象。"
                if "user_id" not in config:
                    return False, f"数据格式无效：user_configs[{i}] 缺少 user_id 字段。"
                if not isinstance(config.get("user_id"), str):
                    return (
                        False,
                        f"数据格式无效：user_configs[{i}].user_id 必须是字符串。",
                    )

        # 验证 deer_records 结构
        if "deer_records" in data:
            if not isinstance(data["deer_records"], list):
                return False, "数据格式无效：deer_records 必须是数组。"
            for i, record in enumerate(data["deer_records"]):
                if not isinstance(record, dict):
                    return False, f"数据格式无效：deer_records[{i}] 必须是对象。"
                required_fields = ["user_id", "year", "month", "day", "count"]
                for field in required_fields:
                    if field not in record:
                        return (
                            False,
                            f"数据格式无效：deer_records[{i}] 缺少 {field} 字段。",
                        )
                # 验证 user_id 类型（必须是字符串）
                if not isinstance(record.get("user_id"), str):
                    return (
                        False,
                        f"数据格式无效：deer_records[{i}].user_id 必须是字符串。",
                    )
                # 验证数值类型和范围
                for field in ["year", "month", "day", "count"]:
                    value = record.get(field)
                    if not isinstance(value, int):
                        return (
                            False,
                            f"数据格式无效：deer_records[{i}].{field} 必须是整数。",
                        )
                    # 验证数值范围
                    if field == "month" and not (1 <= value <= 12):
                        return (
                            False,
                            f"数据格式无效：deer_records[{i}].month 必须在 1-12 之间。",
                        )
                    if field == "day" and not (1 <= value <= 31):
                        return (
                            False,
                            f"数据格式无效：deer_records[{i}].day 必须在 1-31 之间。",
                        )
                    if field == "count" and value < 0:
                        return (
                            False,
                            f"数据格式无效：deer_records[{i}].count 不能为负数。",
                        )
                # 验证年月日组合的真实性（如排除2月31日）
                year, month, day = record["year"], record["month"], record["day"]
                if not _is_valid_date(year, month, day):
                    return (
                        False,
                        f"数据格式无效：deer_records[{i}] 的日期 {year}-{month:02d}-{day:02d} 不存在。",
                    )

        db = await self.db.get_connection()
        try:
            config_count, record_count = await self.db.import_all_data(db, data)
            msg = f"数据导入成功！共导入 {config_count} 个用户配置，{record_count} 条打卡记录。"
            return True, msg
        except Exception as exc:
            logger.error(f"Import data failed: {exc}")
            return False, "数据导入失败，请检查数据格式后重试。"
        finally:
            await db.close()
