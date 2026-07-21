"""Commands package.

命令模式实现，将 main.py 中的命令处理器分离到独立模块。
"""

from .admin_cmd import AdminCommandHandler
from .base import CommandHandler
from .calendar_cmd import CalendarCommandHandler
from .data_cmd import DataCommandHandler
from .deer_cmd import DeerCommandHandler
from .deermap_cmd import DeermapCommandHandler
from .help_cmd import HelpCommandHandler

__all__ = [
    "CommandHandler",
    "DeerCommandHandler",
    "CalendarCommandHandler",
    "AdminCommandHandler",
    "DataCommandHandler",
    "DeermapCommandHandler",
    "HelpCommandHandler",
]
