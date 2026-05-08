"""数据库迁移包

提供版本化数据库迁移功能。
迁移脚本命名规范: V{数字}_{描述}.py
"""

from .migration_runner import MigrationRunner, run_migrations

__all__ = ["MigrationRunner", "run_migrations"]
