"""数据库迁移运行器

支持版本化迁移，通过扫描 migrations/ 目录下的脚本文件，
根据 migration_record 表中记录的版本号，自动执行未应用的迁移。

迁移脚本命名规范:
    V{数字}_{描述}.py
    例如: V1_init.py, V2_add_group_id.py

迁移脚本必须实现:
    async def upgrade(conn) -> None:
        '''执行迁移逻辑'''
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from ...utils import get_logger

logger = get_logger()

# 匹配迁移文件名: V1_init.py, V10_add_index.py
_MIGRATION_PATTERN = re.compile(r"^V(\d+)_.+\.py$")


def _extract_version(filename: str) -> int:
    """从迁移文件名提取版本号数字。

    Args:
        filename: 迁移文件名

    Returns:
        版本号整数

    Raises:
        ValueError: 文件名格式不符合规范
    """
    match = _MIGRATION_PATTERN.match(filename)
    if not match:
        raise ValueError(
            f"无效的迁移文件名: {filename}, 期望格式: V{{数字}}_{{描述}}.py"
        )
    return int(match.group(1))


@dataclass(frozen=True, slots=True)
class MigrationScript:
    """迁移脚本信息"""

    version: int
    name: str
    module_name: str
    upgrade: Callable[..., Any] | None = None


class MigrationRunner:
    """数据库迁移运行器

    负责扫描、排序和执行数据库迁移脚本。

    使用示例:
        runner = MigrationRunner()
        await runner.run_all(conn)
    """

    _scripts: list[MigrationScript] | None = None

    def __init__(self, package: str = __package__):
        """初始化迁移运行器。

        Args:
            package: 迁移脚本所在的 Python 包名
        """
        self._package = package

    def _discover_scripts(self) -> list[MigrationScript]:
        """扫描并加载所有迁移脚本。

        Returns:
            按版本号排序的迁移脚本列表
        """
        scripts: list[MigrationScript] = []

        try:
            package = importlib.import_module(self._package)
            package_path = Path(package.__file__).parent
        except (ImportError, AttributeError):
            logger.warning("迁移包 %s 不存在或未找到 __file__", self._package)
            return []

        for _, module_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
            if is_pkg:
                continue

            try:
                version = _extract_version(module_name + ".py")
            except ValueError:
                # 忽略不符合命名规范的文件
                continue

            # 动态导入迁移模块
            full_module_name = f"{self._package}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
            except Exception as ex:
                logger.error("加载迁移脚本 %s 失败: %s", full_module_name, ex)
                continue

            upgrade = getattr(module, "upgrade", None)
            if upgrade is None:
                logger.warning(
                    "迁移脚本 %s 缺少 upgrade 函数，已跳过", full_module_name
                )
                continue

            scripts.append(
                MigrationScript(
                    version=version,
                    name=module_name,
                    module_name=full_module_name,
                    upgrade=upgrade,
                )
            )

        # 按版本号排序
        scripts.sort(key=lambda s: s.version)

        # 检查版本号是否重复
        seen_versions: set[int] = set()
        for script in scripts:
            if script.version in seen_versions:
                raise ValueError(f"迁移版本号重复: V{script.version}")
            seen_versions.add(script.version)

        return scripts

    @property
    def scripts(self) -> list[MigrationScript]:
        """获取已排序的迁移脚本列表（延迟加载）"""
        if self._scripts is None:
            self._scripts = self._discover_scripts()
        return self._scripts

    def get_pending_versions(self, applied_versions: set[int]) -> list[MigrationScript]:
        """获取待执行的迁移脚本列表。

        Args:
            applied_versions: 已应用的版本号集合

        Returns:
            待执行的迁移脚本列表
        """
        return [s for s in self.scripts if s.version not in applied_versions]

    async def _get_applied_versions(self, conn: aiosqlite.Connection) -> set[int]:
        """从数据库获取已应用的迁移版本号。

        Args:
            conn: 数据库连接对象

        Returns:
            已应用的版本号集合
        """
        # 先检查 migration_record 表是否存在
        result = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='migration_record'"
        )
        row = await result.fetchone()
        if row is None:
            return set()

        result = await conn.execute("SELECT version FROM migration_record")
        applied: set[int] = set()
        async for row in result:
            version_str = str(row[0])
            try:
                applied.add(int(version_str))
            except ValueError:
                logger.debug("跳过无效的迁移记录: %s", version_str)
                continue

        return applied

    async def _record_migration(
        self, conn: aiosqlite.Connection, version: int, description: str = ""
    ) -> None:
        """记录迁移版本到数据库。

        Args:
            conn: 数据库连接对象
            version: 版本号
            description: 迁移描述
        """
        await conn.execute(
            """
            INSERT OR REPLACE INTO migration_record (version, applied_at, description)
            VALUES (?, datetime('now'), ?)
            """,
            (str(version), description),
        )

    async def run_all(self, conn: aiosqlite.Connection) -> list[int]:
        """执行所有待迁移的脚本。

        Args:
            conn: 数据库连接对象（应在事务中）

        Returns:
            已执行的版本号列表
        """
        applied = await self._get_applied_versions(conn)
        pending = self.get_pending_versions(applied)

        if not pending:
            logger.debug("数据库已是最新版本，无需迁移")
            return []

        executed: list[int] = []
        for script in pending:
            logger.info("执行迁移 V%s: %s", script.version, script.name)
            if script.upgrade is None:
                raise RuntimeError(
                    f"迁移脚本 V{script.version} ({script.name}) 的 upgrade 函数为 None，"
                    f"请检查模块 {script.module_name} 是否正确导出 upgrade 函数"
                )
            try:
                await script.upgrade(conn)
                await self._record_migration(conn, script.version, script.name)
                executed.append(script.version)
                logger.info("迁移 V%s 执行成功", script.version)
            except Exception:
                logger.error("迁移 V%s (%s) 执行失败", script.version, script.name)
                raise

        logger.info("数据库迁移完成，本次执行 %d 个迁移", len(executed))
        return executed

    async def run_to(
        self, conn: aiosqlite.Connection, target_version: int
    ) -> list[int]:
        """执行迁移到指定版本号。

        Args:
            conn: 数据库连接对象
            target_version: 目标版本号

        Returns:
            已执行的版本号列表
        """
        applied = await self._get_applied_versions(conn)
        pending = self.get_pending_versions(applied)

        executed: list[int] = []
        for script in pending:
            if script.version > target_version:
                break
            logger.info("执行迁移 V%s: %s", script.version, script.name)
            if script.upgrade is None:
                raise RuntimeError(
                    f"迁移脚本 V{script.version} ({script.name}) 的 upgrade 函数为 None，"
                    f"请检查模块 {script.module_name} 是否正确导出 upgrade 函数"
                )
            try:
                await script.upgrade(conn)
                await self._record_migration(conn, script.version, script.name)
                executed.append(script.version)
                logger.info("迁移 V%s 执行成功", script.version)
            except Exception:
                logger.error("迁移 V%s (%s) 执行失败", script.version, script.name)
                raise

        return executed

    def list_all(self) -> list[tuple[int, str, str]]:
        """列出所有迁移脚本信息。

        Returns:
            [(版本号, 名称, 模块名), ...]
        """
        return [(s.version, s.name, s.module_name) for s in self.scripts]


async def run_migrations(conn: aiosqlite.Connection) -> list[int]:
    """便捷函数：执行所有待迁移脚本。

    Args:
        conn: 数据库连接对象

    Returns:
        已执行的版本号列表
    """
    runner = MigrationRunner()
    return await runner.run_all(conn)
