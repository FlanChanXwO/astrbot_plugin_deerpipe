"""Admin command handlers.

处理管理员命令，如设置他人权限等。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...infrastructure import get_logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ...application.services import DeerPipeService

logger = get_logger()


class AdminCommandHandler:
    """管理员命令处理器.

    轻量级处理器，通过构造函数接收必要的依赖。
    """

    def __init__(self, service: DeerPipeService) -> None:
        """初始化命令处理器.

        Args:
            service: 鹿管业务服务实例
        """
        self.service = service
        self.logger = logger

    async def handle_set_deer_on(self, event: AstrMessageEvent) -> str | None:
        """处理允许他人被帮打卡.

        Args:
            event: 消息事件

        Returns:
            操作结果消息，失败时返回 None
        """
        return await self.service.handle_set_other_help(event, True)

    async def handle_set_deer_off(self, event: AstrMessageEvent) -> str | None:
        """处理禁止他人被帮打卡.

        Args:
            event: 消息事件

        Returns:
            操作结果消息，失败时返回 None
        """
        return await self.service.handle_set_other_help(event, False)
