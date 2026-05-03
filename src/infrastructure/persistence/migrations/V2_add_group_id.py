"""V2 迁移 - 添加 group_id 字段

在 deer_record 表中添加 group_id 字段，用于支持群排行榜功能。
"""

from __future__ import annotations

from ...utils import get_logger

logger = get_logger()


async def upgrade(conn) -> None:
    """执行 V2 迁移: 添加 group_id 字段"""

    # 检查 deer_record 表是否存在
    result = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='deer_record'"
    )
    if await result.fetchone() is None:
        logger.warning("deer_record 表不存在，跳过迁移")
        return

    # 检查 group_id 列是否已存在
    result = await conn.execute("PRAGMA table_info(deer_record)")
    columns = await result.fetchall()
    column_names = [col[1] for col in columns]

    if "group_id" in column_names:
        logger.info("group_id 列已存在，跳过迁移")
        return

    # 添加 group_id 列
    await conn.execute("ALTER TABLE deer_record ADD COLUMN group_id TEXT")
    logger.info("成功添加 group_id 列到 deer_record 表")

    # 创建索引以优化群排行榜查询
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_deer_record_group_date
        ON deer_record(group_id, year, month, day)
        """
    )
    logger.info("创建索引 idx_deer_record_group_date")

    # 更新现有的迁移，将 group_id 设为 'unknown' 表示未知群组
    await conn.execute(
        "UPDATE deer_record SET group_id = 'unknown' WHERE group_id IS NULL"
    )
    logger.info("迁移现有记录，设置默认 group_id")

    await conn.commit()
