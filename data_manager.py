"""Deer-pipe plugin data export/import module.

数据导出导入功能模块。
"""

from __future__ import annotations

from astrbot.api import logger

from .database import DatabaseManager


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
