"""Help command handler.

发送固定帮助图，不依赖 t2i 渲染。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...infrastructure.utils.logger import get_logger
from ...shared.constants import EVENT_DEDUP_HELP

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

logger = get_logger()


class HelpCommandHandler:
    """帮助命令处理器：直接发送打包的静态帮助图."""

    def __init__(self, base_dir: Path) -> None:
        self.help_image = (base_dir / "assets" / "help.png").resolve()
        self.logger = logger

    async def handle_help(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        if event.get_extra(EVENT_DEDUP_HELP):
            return
        event.set_extra(EVENT_DEDUP_HELP, True)

        if not self.help_image.is_file():
            self.logger.error("帮助图缺失: %s", self.help_image)
            yield event.plain_result("帮助图资源缺失，请重新安装或更新插件。")
            event.stop_event()
            return

        yield event.image_result(str(self.help_image))
        event.stop_event()
