"""Command base classes.

命令模式基类定义。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class CommandHandler:
    """命令处理器基类.

    子类通过构造函数接收具体依赖，保持轻量和解耦。
    """

    pass
