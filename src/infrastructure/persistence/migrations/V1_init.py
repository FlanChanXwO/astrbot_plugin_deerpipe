"""V1 初始化迁移

创建迁移记录表，用于跟踪已应用的数据库迁移版本。
"""

from __future__ import annotations

from ...utils import get_logger

logger = get_logger()


async def upgrade(conn) -> None:
    """执行 V1 初始化迁移"""

    async def _table_exists(table: str) -> bool:
        result = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return await result.fetchone() is not None

    # 创建迁移记录表
    if not await _table_exists("migration_record"):
        await conn.execute(
            """
            CREATE TABLE migration_record (
                version    INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
            """
        )
        logger.info("创建迁移记录表 migration_record")

    await conn.commit()
