"""Deer-pipe plugin database module.

提供 SQLite 数据库连接管理和数据操作。
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
from pathlib import Path

import aiosqlite

from .models import MonthStats, UserConfig


def _get_plugin_version() -> str:
    """获取插件版本号.

    从 metadata.yaml 文件中读取版本信息。

    Returns:
        插件版本号，如果读取失败则返回 "unknown"
    """
    try:
        metadata_path = Path(__file__).parent / "metadata.yaml"
        if metadata_path.exists():
            content = metadata_path.read_text(encoding="utf-8")
            # 使用正则表达式提取版本号
            match = re.search(r"^version:\s*(.+)$", content, re.MULTILINE)
            if match:
                return match.group(1).strip()
    except Exception:
        pass
    return "unknown"


class DatabaseManager:
    """数据库管理器.

    负责数据库连接、初始化和所有数据操作。
    使用懒加载模式，首次连接时自动初始化表结构。
    使用异步锁保护初始化过程，防止并发竞态。
    """

    def __init__(self, db_path: Path) -> None:
        """初始化数据库管理器.

        Args:
            db_path: SQLite 数据库文件路径
        """
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def _ensure_tables(self, db: aiosqlite.Connection) -> None:
        """确保数据库表结构已创建.

        Args:
            db: 数据库连接对象
        """
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS deer_config (
                user_id           TEXT PRIMARY KEY,
                allow_help        INTEGER NOT NULL DEFAULT 1,
                last_retro_date   TEXT NOT NULL DEFAULT '',
                retro_count_today INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS deer_record (
                user_id   TEXT NOT NULL,
                year      INTEGER NOT NULL,
                month     INTEGER NOT NULL,
                day       INTEGER NOT NULL,
                count     INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, year, month, day)
            );
            CREATE INDEX IF NOT EXISTS idx_deer_record_user_month
            ON deer_record(user_id, year, month);
            CREATE TABLE IF NOT EXISTS deer_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        await db.commit()
        self._initialized = True

    async def get_connection(self) -> aiosqlite.Connection:
        """获取数据库连接.

        首次调用时会自动初始化表结构。
        使用异步锁保护初始化过程，防止并发竞态。

        Returns:
            SQLite 数据库连接对象
        """
        db = await aiosqlite.connect(str(self._db_path))
        if not self._initialized:
            async with self._init_lock:
                # 双重检查，防止锁竞争时重复初始化
                if not self._initialized:
                    await self._ensure_tables(db)
        return db

    async def ensure_user_config(self, db: aiosqlite.Connection, user_id: str) -> None:
        """确保用户配置记录存在.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识
        """
        await db.execute(
            "INSERT OR IGNORE INTO deer_config (user_id) VALUES (?)", (user_id,)
        )

    async def is_help_allowed(self, db: aiosqlite.Connection, user_id: str) -> bool:
        """检查用户是否允许被帮 deer.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识

        Returns:
            是否允许被帮 deer
        """
        await self.ensure_user_config(db, user_id)
        cursor = await db.execute(
            "SELECT allow_help FROM deer_config WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row and row[0])

    async def set_help_allowed(
        self, db: aiosqlite.Connection, user_id: str, allowed: bool
    ) -> None:
        """设置用户是否允许被帮 deer.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识
            allowed: 是否允许
        """
        await self.ensure_user_config(db, user_id)
        await db.execute(
            "UPDATE deer_config SET allow_help = ? WHERE user_id = ?",
            (1 if allowed else 0, user_id),
        )

    async def record_attendance(
        self, db: aiosqlite.Connection, user_id: str, year: int, month: int, day: int
    ) -> None:
        """记录用户打卡.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识
            year: 年份
            month: 月份
            day: 日期
        """
        await db.execute(
            """
            INSERT INTO deer_record (user_id, year, month, day, count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(user_id, year, month, day)
            DO UPDATE SET count = count + 1
            """,
            (user_id, year, month, day),
        )

    async def get_last_retro_date(self, db: aiosqlite.Connection, user_id: str) -> str:
        """获取用户上次补 deer 日期.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识

        Returns:
            上次补 deer 日期 (ISO格式字符串，空字符串表示从未补过)
        """
        await self.ensure_user_config(db, user_id)
        cursor = await db.execute(
            "SELECT last_retro_date FROM deer_config WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else ""

    async def set_last_retro_date(
        self, db: aiosqlite.Connection, user_id: str, date: str
    ) -> None:
        """设置用户上次补 deer 日期.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识
            date: 日期字符串 (ISO格式)
        """
        await self.ensure_user_config(db, user_id)
        await db.execute(
            "UPDATE deer_config SET last_retro_date = ? WHERE user_id = ?",
            (date, user_id),
        )

    async def get_today_retro_count(
        self, db: aiosqlite.Connection, user_id: str
    ) -> int:
        """获取用户今日补 deer 次数.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识

        Returns:
            今日补 deer 次数
        """
        await self.ensure_user_config(db, user_id)
        # 检查是否是新的一天
        last_retro_date = await self.get_last_retro_date(db, user_id)
        today = dt.date.today().isoformat()

        if last_retro_date != today:
            # 新的一天，重置计数
            return 0

        cursor = await db.execute(
            "SELECT retro_count_today FROM deer_config WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def increment_retro_count(
        self, db: aiosqlite.Connection, user_id: str, date: str
    ) -> None:
        """增加用户今日补 deer 次数.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识
            date: 日期字符串 (ISO格式)
        """
        last_retro_date = await self.get_last_retro_date(db, user_id)

        if last_retro_date == date:
            # 同一天，增加计数
            await db.execute(
                """UPDATE deer_config
                   SET retro_count_today = retro_count_today + 1
                   WHERE user_id = ?""",
                (user_id,),
            )
        else:
            # 新的一天，重置计数
            await db.execute(
                """UPDATE deer_config
                   SET last_retro_date = ?, retro_count_today = 1
                   WHERE user_id = ?""",
                (date, user_id),
            )

    async def get_month_stats(
        self, db: aiosqlite.Connection, user_id: str, year: int, month: int
    ) -> MonthStats:
        """获取用户月度统计数据.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识
            year: 年份
            month: 月份

        Returns:
            月度统计数据
        """
        cursor = await db.execute(
            """
            SELECT day, count FROM deer_record
            WHERE user_id = ? AND year = ? AND month = ?
            """,
            (user_id, year, month),
        )

        days: dict[int, int] = {}
        total = 0
        async for row in cursor:
            day, count = row
            days[day] = count
            total += count

        return MonthStats(year=year, month=month, total_count=total, days=days)

    async def get_calendar_data(
        self, db: aiosqlite.Connection, user_id: str, year: int, month: int
    ) -> dict[int, int]:
        """获取日历展示所需数据.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识
            year: 年份
            month: 月份

        Returns:
            日期到打卡次数的映射字典
        """
        cursor = await db.execute(
            "SELECT day, count FROM deer_record WHERE user_id = ? AND year = ? AND month = ?",
            (user_id, year, month),
        )
        result: dict[int, int] = {}
        async for row in cursor:
            result[row[0]] = row[1]
        return result

    async def has_record_today(self, db: aiosqlite.Connection, user_id: str) -> bool:
        """检查用户今天是否已有打卡记录.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识

        Returns:
            今天是否有打卡记录
        """
        today = dt.date.today()
        cursor = await db.execute(
            "SELECT 1 FROM deer_record WHERE user_id = ? AND year = ? AND month = ? AND day = ?",
            (user_id, today.year, today.month, today.day),
        )
        row = await cursor.fetchone()
        return row is not None

    async def get_user_config(
        self, db: aiosqlite.Connection, user_id: str
    ) -> UserConfig:
        """获取用户完整配置.

        Args:
            db: 数据库连接对象
            user_id: 用户唯一标识

        Returns:
            用户配置对象
        """
        await self.ensure_user_config(db, user_id)
        cursor = await db.execute(
            "SELECT user_id, allow_help, last_retro_date FROM deer_config WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return UserConfig(
                user_id=row[0], allow_help=bool(row[1]), last_retro_date=row[2]
            )
        return UserConfig(user_id=user_id)

    # ==================================================================
    # Data export/import
    # ==================================================================
    async def export_all_data(self, db: aiosqlite.Connection) -> dict:
        """导出所有数据.

        Args:
            db: 数据库连接对象

        Returns:
            包含所有用户配置和打卡记录的字典
        """
        # 导出用户配置
        config_cursor = await db.execute(
            "SELECT user_id, allow_help, last_retro_date FROM deer_config"
        )
        configs: list[dict] = []
        async for row in config_cursor:
            configs.append(
                {
                    "user_id": row[0],
                    "allow_help": bool(row[1]),
                    "last_retro_date": row[2],
                }
            )

        # 导出打卡记录
        record_cursor = await db.execute(
            "SELECT user_id, year, month, day, count FROM deer_record"
        )
        records: list[dict] = []
        async for row in record_cursor:
            records.append(
                {
                    "user_id": row[0],
                    "year": row[1],
                    "month": row[2],
                    "day": row[3],
                    "count": row[4],
                }
            )

        return {
            "version": _get_plugin_version(),
            "export_time": dt.datetime.now().isoformat(),
            "user_configs": configs,
            "deer_records": records,
        }

    async def import_all_data(
        self, db: aiosqlite.Connection, data: dict
    ) -> tuple[int, int]:
        """导入数据.

        Args:
            db: 数据库连接对象
            data: 导入的数据字典

        Returns:
            (导入的配置数量, 导入的记录数量)

        Raises:
            ValueError: 数据格式无效
        """
        config_count = 0
        record_count = 0

        # 导入用户配置
        if "user_configs" in data:
            for config in data["user_configs"]:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO deer_config (user_id, allow_help, last_retro_date, retro_count_today)
                    VALUES (?, ?, ?, 0)
                    """,
                    (
                        config["user_id"],
                        1 if config.get("allow_help", True) else 0,
                        config.get("last_retro_date", config.get("last_retro", "")),
                    ),
                )
                config_count += 1

        # 导入打卡记录
        if "deer_records" in data:
            for record in data["deer_records"]:
                count = record["count"]
                # 防止负数 count 降低既有记录
                if count < 0:
                    count = 0
                await db.execute(
                    """
                    INSERT INTO deer_record (user_id, year, month, day, count)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, year, month, day)
                    DO UPDATE SET count = count + ?
                    """,
                    (
                        record["user_id"],
                        record["year"],
                        record["month"],
                        record["day"],
                        count,
                        count,
                    ),
                )
                record_count += 1

        await db.commit()
        return config_count, record_count
