"""Deer check-in command handlers.

处理与打卡（鹿管）相关的命令，包括自我打卡、帮他人打卡、允许/禁止被帮等。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from astrbot.core.message.components import At
from astrbot.core.platform.message_type import MessageType
from data.plugins.astrbot_plugin_deerpipe.src.application.services.deer_service import (
    DeerResult,
)

from ...domain import TEMPLATE_GROUP_ONLY
from ...infrastructure import extract_mention_user_ids, get_logger
from ...shared import ResourcePaths

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ...application.services import DeerPipeService

logger = get_logger()


class DeerCommandHandler:
    """鹿管打卡命令处理器.

    轻量级处理器，通过构造函数接收必要的依赖。
    """

    def __init__(self, service: DeerPipeService) -> None:
        """初始化命令处理器.

        Args:
            service: 鹿管业务服务实例
        """
        self.service = service
        self.logger = logger

    async def handle_deer_self(self, event: AstrMessageEvent) -> str:
        """处理自我打卡.

        Args:
            event: 消息事件

        Returns:
            打卡结果消息
        """
        return await self.service.handle_deer_self(event)

    async def handle_deer_other(
        self,
        event: AstrMessageEvent,
        at_ids: list[str],
        at_list: list[At],
        self_id: str | None,
    ) -> list[DeerResult]:
        """处理帮他人打卡.

        Args:
            event: 消息事件
            at_ids: 目标用户ID列表
            at_list: @组件列表
            self_id: 机器人自身ID

        Returns:
            打卡结果列表
        """
        return await self.service.batch_deer_other(
            event, event.get_sender_id(), set(at_ids), at_list, self_id
        )

    async def handle_allow_deer(self, event: AstrMessageEvent) -> str:
        """处理允许他人帮自己打卡.

        Args:
            event: 消息事件

        Returns:
            操作结果消息
        """
        return await self.service.handle_set_self_help(event, True)

    async def handle_forbid_deer(self, event: AstrMessageEvent) -> str:
        """处理禁止他人帮自己打卡.

        Args:
            event: 消息事件

        Returns:
            操作结果消息
        """
        return await self.service.handle_set_self_help(event, False)

    async def handle_retro_deer(self, event: AstrMessageEvent, day: int) -> str | None:
        """处理补打卡.

        Args:
            event: 消息事件
            day: 日期（1-31）

        Returns:
            操作结果消息，失败时返回 None
        """
        return await self.service.handle_deer_past(event, day)

    async def run_deer_checkin(
        self, event: AstrMessageEvent, html_render
    ) -> AsyncGenerator[Any, None]:
        """运行完整的打卡流程.

        Args:
            event: 消息事件
            html_render: HTML渲染函数

        Yields:
            发送给用户的响应
        """
        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)

        if at_ids:
            if event.get_message_type() != MessageType.GROUP_MESSAGE:
                yield event.plain_result(TEMPLATE_GROUP_ONLY)
                return

            self_id = event.get_self_id()
            if self_id and self_id in at_ids:
                yield event.plain_result("不可以帮 Bot🦌哦~")
                return

            try:
                results = await self.handle_deer_other(event, at_ids, at_list, self_id)
            except (OSError, RuntimeError, ValueError) as exc:
                self.logger.error(f"deer_cmd help_other failed: {exc}")
                yield event.plain_result("操作失败，请稍后重试。")
                return

            if len(at_ids) == 1:
                result_data = (
                    results[0] if results else {"success": False, "reason": "未知错误"}
                )
                target_name = result_data["nickname"]

                if not result_data["success"]:
                    reason = result_data.get("reason", "无法帮🦌")
                    yield event.plain_result(f"❌ 无法帮 {target_name} 🦌：{reason}")
                    return

                async for cal_result, is_text in self.service.render_calendar(
                    event,
                    dt.date.today(),
                    html_render,
                    user_id=result_data["user_id"],
                ):
                    if is_text:
                        yield event.plain_result(f"成功帮{target_name}🦌了")
                        yield event.plain_result(cal_result)
                    else:
                        yield (
                            event.make_result()
                            .message(f"成功帮{target_name}🦌了")
                            .file_image(cal_result)
                        )
                return

            # 批量帮🦌
            success_count = sum(1 for r in results if r["success"])
            image_url = await self._render_batch_report(
                results, success_count, html_render
            )
            if image_url:
                total = len(results)
                msg = f"批量帮🦌完成！成功 {success_count}/{total} 人"
                yield event.make_result().message(msg).file_image(image_url)
            else:
                lines = [f"批量帮🦌结果（{success_count}/{len(results)} 成功）："]
                for r in results:
                    status = "✅" if r["success"] else "❌"
                    lines.append(f"{status} {r['nickname']} - 第 {r['count']} 次")
                yield event.plain_result("\n".join(lines))
            return

        # 自我打卡
        result = await self.handle_deer_self(event)
        async for cal_result, is_text in self.service.render_calendar(
            event, dt.date.today(), html_render
        ):
            if is_text:
                yield event.plain_result(result)
                yield event.plain_result(cal_result)
            else:
                yield event.make_result().message(result).file_image(cal_result)

    async def _render_batch_report(
        self, results: list[dict], success_count: int, html_render
    ) -> str | None:
        """渲染批量报告图片.

        Args:
            results: 打卡结果列表
            success_count: 成功人数
            html_render: HTML渲染函数

        Returns:
            图片 URL 或 None（渲染失败）
        """
        base_dir = Path(__file__).parent.parent.parent.parent
        paths = ResourcePaths(base_dir)
        template_path = paths.template("batch_report")
        css_path = paths.style("batch_report")

        if not template_path.exists():
            self.logger.error(f"批量报告模板不存在: {template_path}")
            return None

        try:
            # 读取模板和 CSS
            html = template_path.read_text(encoding="utf-8")
            css_content = ""
            if css_path.exists():
                css_content = f"<style>{css_path.read_text(encoding='utf-8')}</style>"

            # 构建渲染数据
            payload = {
                "css_style": css_content,
                "results": results,
                "total_count": len(results),
                "success_count": success_count,
            }

            # 调用渲染服务 - 使用 full_page 自动适应高度
            image_url = await html_render(
                html,
                payload,
                return_url=True,
                options={
                    "type": "png",
                    "full_page": True,
                    "scale": "device",
                },
            )
            return image_url

        except (OSError, RuntimeError, ValueError) as exc:
            self.logger.error(f"批量报告渲染失败: {exc}")
            return None
