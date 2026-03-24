"""Deer-pipe (鹿管) daily check-in plugin.

Migrated from the Java WineFoxBot DeerpipePlugin.
Tracks daily deer check-ins per user with a calendar view.

Commands:
    /deer or /鹿 or /🦌              - Check in (deer yourself) for today.
    /deer @someone                   - Help deer someone else (if they allow it).
    /允许被鹿 or /允许被🦌            - Allow others to deer you.
    /禁止被鹿 or /禁止被🦌            - Disallow others from deering you.
    /设置被鹿 开/关 @user            - Admin: set help-status for others.
    /retro_deer <day> or /补鹿 <day> - Retroactively check in.
    /deer_calendar or /鹿历          - Show this month's deer calendar.
    /last_month_calendar or /上月鹿历 - Show last month's deer calendar.
    /管理鹿管数据 导出              - Admin: export all data.
    /管理鹿管数据 导入              - Admin: import data from JSON.

LLM Tools (for AI analysis):
    deer_self         - User self check-in
    deer_other        - Help others check-in
    retro_deer        - Retroactive check-in
    set_allow_help    - Set allow help status
    get_user_deer_data - Get calendar + stats (merged query tool)

AI Behavior Configuration (in WebUI):
    allow_ai_help_deer   - Whether AI can help users check-in
    allow_ai_be_deered   - Whether users can help AI check-in
    daily_retro_limit    - Max retroactive check-ins per day
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import tempfile
import time
from pathlib import Path

from astrbot.api import llm_tool, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, StarTools
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import At, File
from astrbot.core.platform.message_type import MessageType

from .commands import DeerPipeService
from .data_manager import DataManager
from .database import DatabaseManager
from .llm_tools import DeerPipeLLMTools
from .renderer import CalendarRenderer
from .utils import extract_mention_user_ids, close_aiohttp_session


# 导入会话状态管理（线程安全）
_import_session_lock = asyncio.Lock()
_import_sessions: dict[str, float] = {}  # user_id -> start_time
_import_session_timeout = 300  # 5分钟超时


class DeerPipePlugin(Star):
    """Deer-pipe daily check-in plugin with SQLite persistence."""

    # 工具函数名称列表，用于卸载时移除
    LLM_TOOLS = [
        "deer_self",
        "deer_other",
        "retro_deer",
        "set_allow_help",
        "get_user_deer_data",
    ]

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        """Initialize the plugin."""
        super().__init__(context)

        # 读取插件配置 (转换为 dict)
        self.config = self._config_to_dict(config)

        # 初始化数据库、渲染器和数据管理器
        db_path = StarTools.get_data_dir(self.name) / "deerpipe.db"
        self.db = DatabaseManager(db_path)
        self.renderer = CalendarRenderer(Path(__file__).parent)
        self.data_manager = DataManager(self.db)
        # 初始化业务服务（传入配置）
        self.service = DeerPipeService(self.db, self.renderer, self.config)

        # 初始化AI工具
        self.llm_tools = DeerPipeLLMTools(
            self.db, self.data_manager, self.service, self.config
        )

    def _config_to_dict(self, config: AstrBotConfig) -> dict:
        """将 AstrBotConfig 转换为普通 dict.

        优先使用插件专用配置，如果没有则返回空 dict。
        """
        if hasattr(config, "get"):
            # 尝试获取插件配置
            plugin_config = config.get(self.name)
            if plugin_config and isinstance(plugin_config, dict):
                return plugin_config
        # 如果 config 是 dict 类型，检查是否包含插件配置键
        if isinstance(config, dict):
            if self.name in config:
                plugin_config = config.get(self.name)
                if isinstance(plugin_config, dict):
                    return plugin_config
            # 不含插件配置键时返回空 dict，而不是整个 config
            return {}
        return {}

    async def terminate(self):
        """插件卸载时清理资源."""
        self._unregister_llm_tools()
        # 关闭全局 aiohttp session，防止资源泄漏
        await close_aiohttp_session()

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求时附加自定义 prompt.

        如果配置了 custom_prompt，则将其追加到 system_prompt 中。
        """
        ai_config = self.config.get("ai_behavior", {})
        custom_prompt = (
            ai_config.get("custom_prompt", "") if isinstance(ai_config, dict) else ""
        )
        if custom_prompt:
            logger.debug("[DeerPipe] 当前 custom_prompt 长度: %d", len(custom_prompt))
            # 防护 system_prompt 为 None 的情况
            current_prompt = req.system_prompt or ""
            logger.debug("[DeerPipe] 当前 system_prompt 长度: %d", len(current_prompt))
            req.system_prompt = f"{current_prompt}\n\n{custom_prompt}"
            logger.debug(
                "[DeerPipe] 已追加 custom_prompt，当前 system_prompt 长度: %d",
                len(req.system_prompt),
            )

    def _unregister_llm_tools(self):
        """注销所有LLM工具函数."""
        try:
            func_tool_mgr = self.context.get_llm_tool_manager()
            for tool_name in self.LLM_TOOLS:
                func_tool_mgr.remove_tool(tool_name)
                logger.info(f"[DeerPipe] 已移除LLM工具: {tool_name}")
        except Exception as e:
            logger.error(f"[DeerPipe] 移除LLM工具失败: {e}")

    # ==================================================================
    # LLM Tools - AI工具函数 (精简版)
    # ==================================================================
    @llm_tool("deer_self")
    async def tool_deer_self(self, event: AstrMessageEvent) -> str:
        """Check in (deer) for yourself today. Use this when the user wants to check in, mark their attendance, or says something like "deer", "打卡", "🦌", "撸", "鹿", "导管", "导", "🦌管", "鹿管", "撸管", "我要🦌", "我要撸", "我要鹿", "我要导管", "我要导", "帮我🦌", "帮我撸", "帮我鹿", "帮我导管", "帮我导" etc.

        Returns:
            JSON result with success status, date, and stats.
        """
        user_id = str(event.get_sender_id())
        result = await self.llm_tools.deer_self(user_id)

        # 如果打卡成功，发送🦌历图片
        if result.get("success"):
            async for cal_result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render, user_id=user_id
            ):
                if is_text:
                    await event.send(event.plain_result(cal_result))
                else:
                    await event.send(event.image_result(cal_result))

        return json.dumps(result, ensure_ascii=False)

    @llm_tool("deer_other")
    async def tool_deer_other(
        self, event: AstrMessageEvent, target_ids: list[str]
    ) -> str:
        """Help other users check in (deer) on their behalf. Use this when the user says "帮我🦌", "帮XX🦌", "帮我撸", "帮XX撸", "帮我鹿", "帮XX鹿", "帮我导管", "帮XX导管", "帮我导", "帮XX导", "帮🦌", "帮撸", "帮鹿", "帮导管", "帮导", or asks you to check in for them.

        IMPORTANT: Requires 'allow_ai_help_deer' to be enabled in plugin config.

        Args:
            target_ids(array): List of target user IDs.

        Returns:
            JSON result with success status for each target.
        """
        user_id = str(event.get_sender_id())
        bot_id = str(event.get_self_id()) if event.get_self_id() else None
        # 确保 target_ids 中的 ID 都是字符串
        target_ids = [str(tid) for tid in target_ids]
        result = await self.llm_tools.deer_other(user_id, target_ids, bot_id)

        # 如果帮打卡成功，为第一个成功的用户发送🦌历图片
        # 如果操作者在目标列表中，优先显示操作者的日历
        if result.get("success") and target_ids:
            # 优先选择操作者自己的日历（如果操作者在目标列表中）
            display_user_id = user_id if user_id in target_ids else target_ids[0]
            if display_user_id:
                async for cal_result, is_text in self.service.render_calendar(
                    event, dt.date.today(), self.html_render, user_id=display_user_id
                ):
                    if is_text:
                        await event.send(event.plain_result(cal_result))
                    else:
                        await event.send(event.image_result(cal_result))

        return json.dumps(result, ensure_ascii=False)

    @llm_tool("retro_deer")
    async def tool_retro_deer(
        self,
        event: AstrMessageEvent,
        day: int,
        year: int = 0,
        month: int = 0,
    ) -> str:
        """Make a retroactive check-in (deer) for a specific past day. Use this when the user wants to 补打卡, 补🦌, 补撸, 补鹿, 补导管, 补导 for a date they missed.

        Args:
            day(number): Day of month (1-31) to retroactively check in
            year(number): Year, default 0 means current year
            month(number): Month (1-12), default 0 means current month

        Returns:
            JSON result with success status, retroactive date, and daily limit info.
        """
        user_id = str(event.get_sender_id())
        result = await self.llm_tools.retro_deer(
            user_id,
            day,
            year if year > 0 else None,
            month if month > 0 else None,
        )

        # 如果补打卡成功，发送🦌历图片
        if result.get("success"):
            async for cal_result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render, user_id=user_id
            ):
                if is_text:
                    await event.send(event.plain_result(cal_result))
                else:
                    await event.send(event.image_result(cal_result))

        return json.dumps(result, ensure_ascii=False)

    @llm_tool("set_allow_help")
    async def tool_set_allow_help(self, event: AstrMessageEvent, allowed: bool) -> str:
        """Set whether others can help check in (deer) for you. Use this when the user wants to allow or disallow others from helping them 🦌, 撸, 鹿, 导管, 导.

        Args:
            allowed(boolean): True to allow others to help, false to disable

        Returns:
            JSON result with the updated permission setting.
        """
        user_id = str(event.get_sender_id())
        result = await self.llm_tools.set_allow_help(user_id, allowed)
        return json.dumps(result, ensure_ascii=False)

    @llm_tool("get_user_deer_data")
    async def tool_get_user_deer_data(
        self,
        event: AstrMessageEvent,
        year: int = 0,
        month: int = 0,
    ) -> str:
        """Get user's deer check-in data including calendar and statistics. Use this when the user asks "我🦌了多少次", "我撸了多少次", "我鹿了多少次", "我导了多少次", "我导管了多少次", "我的统计", "看看我的🦌历", "看看我的撸历", "看看我的鹿历", "看看我的导历", "看看我的导管历", "我的🦌数据", "我的撸数据", "我的鹿数据", "我的导数据", "我的导管数据", or any question about their 🦌, 撸, 鹿, 导管, 导 data.

        Args:
            year(number): Year, default 0 means current year
            month(number): Month (1-12), default 0 means current month

        Returns:
            JSON with calendar data, total check-ins, days recorded, consecutive days, and analysis.
        """
        user_id = str(event.get_sender_id())
        year_val = year if year > 0 else None
        month_val = month if month > 0 else None

        # 合并获取日历和统计数据
        calendar_result = await self.llm_tools.get_calendar(
            user_id, year_val, month_val
        )
        stats_result = await self.llm_tools.get_user_stats(user_id)

        # 合并结果
        result = {
            "success": calendar_result.get("success", False)
            and stats_result.get("success", False),
            "user_id": user_id,
            "calendar": calendar_result.get("calendar", {}),
            "stats": stats_result.get("current_month", {}),
            "analysis": calendar_result.get("analysis", {}),
            "user_settings": {
                "allow_help": stats_result.get("allow_help", True),
            },
            "note": "For visual calendar image, use /🦌历 command",
        }

        # 发送🦌历图片
        if calendar_result.get("success"):
            try:
                target_date = dt.date(
                    year_val or dt.date.today().year,
                    month_val or dt.date.today().month,
                    1,
                )
                async for cal_result, is_text in self.service.render_calendar(
                    event, target_date, self.html_render, user_id=user_id
                ):
                    if is_text:
                        await event.send(event.plain_result(cal_result))
                    else:
                        await event.send(event.image_result(cal_result))
            except ValueError as exc:
                logger.warning(
                    f"Invalid date parameters: year_val={year_val}, month_val={month_val}, exc={exc}"
                )

        return json.dumps(result, ensure_ascii=False)

    # ==================================================================
    # Command Handlers (英文主命令 + 中文别名)
    # ==================================================================

    @filter.command("deer", alias={"鹿", "🦌", "撸", "撸🦌"})
    async def deer_cmd(self, event: AstrMessageEvent):
        """自我打卡或帮他人打卡 (/deer).

        Command: /deer or /鹿 or /🦌 (自我打卡)
                 /deer @someone or /🦌 @用户 (帮他人打卡)
        Returns: 打卡成功消息 + 本月🦌历图片（合并为同一条消息）
        """
        # 检查是否有 @ 用户
        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)

        if at_ids:
            # 帮他人打卡模式
            result = await self.service.handle_deer_other(event, at_ids)
            if result is None:
                result = "请 @ 要帮🦌的用户。"
            yield event.plain_result(result)
        else:
            # 自我打卡模式
            result = await self.service.handle_deer_self(event)

            # 再渲染日历图片
            async for cal_result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render
            ):
                if is_text:
                    # 降级为纯文本时，分开发送
                    yield event.plain_result(result)
                    yield event.plain_result(cal_result)
                else:
                    # 文字在上，图片在下，合并为同一条消息
                    yield event.make_result().message(result).url_image(cal_result)

    @filter.command("允许被鹿", alias={"允许被🦌", "允许被撸", "允许被撸🦌"})
    async def allow_deer(self, event: AstrMessageEvent):
        """允许他人帮自己打卡 (/允许被鹿).

        Command: /允许被鹿 or /允许被🦌
        """
        result = await self.service.handle_set_self_help(event, True)
        yield event.plain_result(result)

    @filter.command("禁止被鹿", alias={"禁止被🦌", "禁止被撸", "禁止被撸🦌"})
    async def forbid_deer(self, event: AstrMessageEvent):
        """禁止他人帮自己打卡 (/禁止被鹿).

        Command: /禁止被鹿 or /禁止被🦌
        """
        result = await self.service.handle_set_self_help(event, False)
        yield event.plain_result(result)

    @filter.command_group("设置被鹿", alias={"设置被撸", "设置被撸🦌"})
    async def set_deer_group(self, event: AstrMessageEvent) -> None:
        """管理员设置他人的帮deer权限"""

    @filter.permission_type(filter.PermissionType.ADMIN)
    @set_deer_group.command("开", alias={"on", "撸", "撸🦌"})
    async def set_deer_on(self, event: AstrMessageEvent):
        """管理员允许他人被帮deer (/设置被鹿 开 @用户)."""
        result = await self.service.handle_set_other_help(event, True)
        if result:
            yield event.plain_result(result)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @set_deer_group.command("关", alias={"off", "禁撸", "禁撸🦌"})
    async def set_deer_off(self, event: AstrMessageEvent):
        """管理员禁止他人被帮deer (/设置被鹿 关 @用户)."""
        result = await self.service.handle_set_other_help(event, False)
        if result:
            yield event.plain_result(result)

    @filter.command("retro_deer", alias={"补鹿", "补🦌", "补撸", "补撸🦌"})
    async def retro_deer_cmd(self, event: AstrMessageEvent, day: int):
        """补deer (/retro_deer <day>).

        Command: /retro_deer <day> or /补鹿 <day>
        Restriction: Limited by daily_retro_limit config.
        """
        result = await self.service.handle_deer_past(event, day)
        if result:
            yield event.plain_result(result)

    @filter.command("deer_calendar", alias={"鹿历", "🦌历", "撸历", "撸🦌历"})
    async def deer_calendar_cmd(self, event: AstrMessageEvent):
        """显示本月日历 (/deer_calendar).

        支持查看自己的日历或 @ 他人的日历。
        """
        from .utils import extract_mention_user_ids

        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)

        # 构建 user_id -> name 映射
        at_map = {str(m.qq): m.name for m in at_list if m.name}

        if at_ids:
            # 查看他人的鹿历
            # 使用 at_list 保持消息中的顺序，避免 set 无序导致随机选择
            target_id = str(at_list[0].qq)
            target_name = at_map.get(target_id, target_id)
            async for result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render, user_id=target_id
            ):
                if is_text:
                    yield event.plain_result(f"{target_name} 的鹿历：\n{result}")
                else:
                    yield (
                        event.make_result()
                        .message(f"{target_name} 的鹿历")
                        .url_image(result)
                    )
        else:
            # 查看自己的鹿历
            async for result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render
            ):
                if is_text:
                    yield event.plain_result(result)
                else:
                    yield event.image_result(result)

    @filter.command(
        "last_month_calendar", alias={"上月鹿历", "上月🦌历", "上月撸历", "上月撸🦌历"}
    )
    async def last_month_calendar_cmd(self, event: AstrMessageEvent):
        """显示上月日历 (/last_month_calendar).

        支持查看自己的上月日历或 @ 他人的上月日历。
        """
        from .utils import extract_mention_user_ids

        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)

        # 构建 user_id -> name 映射
        at_map = {str(m.qq): m.name for m in at_list if m.name}

        first = dt.date.today().replace(day=1)
        last_month = (first - dt.timedelta(days=1)).replace(day=1)

        if at_ids:
            # 查看他人的上月鹿历
            # 使用 at_list 保持消息中的顺序，避免 set 无序导致随机选择
            target_id = str(at_list[0].qq)
            target_name = at_map.get(target_id, target_id)
            async for result, is_text in self.service.render_calendar(
                event, last_month, self.html_render, user_id=target_id
            ):
                if is_text:
                    yield event.plain_result(f"{target_name} 的上月鹿历：\n{result}")
                else:
                    yield (
                        event.make_result()
                        .message(f"📅 {target_name} 的上月鹿历")
                        .url_image(result)
                    )
        else:
            # 查看自己的上月鹿历
            async for result, is_text in self.service.render_calendar(
                event, last_month, self.html_render
            ):
                if is_text:
                    yield event.plain_result(result)
                else:
                    yield event.make_result().message("📅 上月鹿历").url_image(result)

    # ==================================================================
    # Data export/import commands (管理员命令，不是LLM工具)
    # ==================================================================
    @filter.command_group("管理鹿管数据", alias={"管理🦌管数据"})
    async def deer_data_group(self, event: AstrMessageEvent) -> None:
        """鹿管数据管理（导入/导出）"""

    @filter.permission_type(filter.PermissionType.ADMIN)
    @deer_data_group.command("导出", alias={"export"})
    async def export_data_cmd(self, event: AstrMessageEvent):
        """导出所有数据 (/管理鹿管数据 导出)."""
        success, msg, data = await self.data_manager.export_data()
        if not success:
            yield event.plain_result(msg)
            return

        # 检查是否有数据可以导出
        record_count = len(data.get("deer_records", [])) if data else 0
        config_count = len(data.get("user_configs", [])) if data else 0
        if record_count == 0 and config_count == 0:
            yield event.plain_result(
                "数据库为空，没有数据可以导出。请先使用🦌命令打卡后再导出。"
            )
            return

        # 创建临时文件并发送
        temp_path: str | None = None
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                f.write(json_str)
                temp_path = f.name

            # 发送文件给用户
            file_component = File(name="deerpipe_export.json", file=temp_path)
            yield event.chain_result([file_component])

        except OSError as e:
            logger.error(f"导出文件发送失败: {e}")
            yield event.plain_result(f"{msg}\n文件发送失败: {e}")
        finally:
            # 确保临时文件被删除
            if temp_path:
                try:
                    os.unlink(temp_path)
                except (OSError, FileNotFoundError) as e:
                    logger.warning(f"删除临时导出文件失败: {e}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @deer_data_group.command("导入", alias={"import"})
    async def import_data_cmd(self, event: AstrMessageEvent):
        """导入数据 (/管理鹿管数据 导入)."""
        global _import_sessions
        # 记录导入会话状态（绑定到具体用户，线程安全）
        user_id = event.get_sender_id()
        async with _import_session_lock:
            _import_sessions[user_id] = time.time()
        yield event.plain_result(
            "请发送 JSON 格式的数据文件（通常是 .json 文件），或在回复此消息时附上文件。\n"
            "注意：导入将合并现有数据，相同日期的记录会累加次数。\n"
            "请在5分钟内发送文件，超时请重新执行导入命令。"
        )

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_file_message(self, event: AstrMessageEvent):
        """监听文件消息以处理导入.

        当管理员发送文件时，自动尝试解析并导入数据。
        需要满足以下条件才会处理：
        1. 是管理员身份
        2. 在执行导入命令后5分钟内
        3. 发送者是发起导入命令的用户本人（会话隔离）
        文件大小限制：10MB
        """
        global _import_sessions

        # 检查是否是管理员（内部检查，避免每条消息都触发权限提示）
        if not event.is_admin():
            return

        sender_id = event.get_sender_id()

        # 检查是否有活跃的导入会话（线程安全）
        async with _import_session_lock:
            session_start = _import_sessions.get(sender_id)
            if session_start is None:
                return

            # 检查会话是否超时
            now = time.time()
            if now - session_start > _import_session_timeout:
                del _import_sessions[sender_id]
                return

        temp_file_path: str | None = None

        try:
            # 检查消息中是否有文件
            messages = event.get_messages()
            has_file = False
            for comp in messages:
                if isinstance(comp, File):
                    has_file = True
                    break
            if not has_file:
                return

            # 处理文件导入
            for comp in messages:
                if isinstance(comp, File):
                    # 获取文件内容
                    file_path = await comp.get_file()
                    if not file_path:
                        continue
                    temp_file_path = file_path

                    # 检查文件大小（限制10MB）
                    try:
                        file_size = os.path.getsize(file_path)
                        max_size = 10 * 1024 * 1024  # 10MB
                        if file_size > max_size:
                            yield event.plain_result(
                                f"文件过大 ({file_size / 1024 / 1024:.2f}MB > 10MB)，请压缩或分批导入。"
                            )
                            return
                    except OSError:
                        pass  # 如果无法获取大小，继续尝试处理

                    # 读取文件内容
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            file_content = f.read()
                    except OSError as e:
                        logger.error(f"读取导入文件失败: {e}")
                        yield event.plain_result(f"读取文件失败: {e}")
                        return

                    # 尝试解析 JSON
                    try:
                        data = json.loads(file_content)
                    except json.JSONDecodeError as e:
                        yield event.plain_result(f"JSON 解析失败: {e}")
                        return

                    # 验证是否是鹿管数据格式
                    if not isinstance(data, dict):
                        yield event.plain_result(
                            "文件格式错误：JSON 根节点必须是对象（字典）。"
                        )
                        return

                    if "deer_records" not in data and "user_configs" not in data:
                        yield event.plain_result(
                            "文件格式错误：未找到有效的鹿管数据字段。\n"
                            "请确保文件包含 'deer_records' 或 'user_configs' 字段。"
                        )
                        return

                    # 执行导入
                    success, msg = await self.data_manager.import_data(data)
                    yield event.plain_result(msg)
                    return

        except OSError as e:
            logger.error(f"导入文件处理失败: {e}")
            yield event.plain_result(f"文件处理失败: {e}")
        finally:
            # 统一清理临时文件和会话状态
            async with _import_session_lock:
                _import_sessions.pop(sender_id, None)
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except (OSError, FileNotFoundError) as e:
                    logger.warning(f"删除临时导入文件失败: {e}")

    async def handle_import_file(self, file_content: str) -> str:
        """处理导入文件内容.

        Args:
            file_content: 文件内容字符串

        Returns:
            处理结果消息
        """
        try:
            data = json.loads(file_content)
            success, msg = await self.data_manager.import_data(data)
            return msg
        except json.JSONDecodeError as e:
            return f"JSON 解析失败: {e}"
        except Exception as e:
            return f"导入失败: {e}"

    # ==================================================================
    # Plain message handlers (without / prefix)
    # ==================================================================

    @filter.regex(r"^(🦌|鹿|撸|撸🦌)(?!历)")
    async def plain_deer_merged_cmd(self, event: AstrMessageEvent):
        """处理纯🦌/帮🦌消息（不带/前缀）.

        直接发送 🦌、鹿、撸、撸🦌 触发自我打卡。
        发送 "🦌 @用户" 触发帮他人打卡。
        单人输出日历图片，多人使用 batch_report 模板输出批量报告。
        """
        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)

        # 判断是帮他人打卡还是自己打卡
        if at_ids:
            # 帮他人打卡模式
            if event.get_message_type() != MessageType.GROUP_MESSAGE:
                yield event.plain_result("该命令仅限群聊使用。")
                return

            # 禁止帮 bot 自己打卡
            self_id = event.get_self_id()
            if self_id and self_id in at_ids:
                yield event.plain_result("不可以帮 Bot🦌哦~")
                return

            logger.debug(
                f"[DeerPipe] plain_deer_merged_cmd 处理 at_ids: {at_ids}, 类型: {type(list(at_ids)[0])}"
            )

            # 使用批量打卡方法
            try:
                results = await self.service.batch_deer_other(
                    event.get_sender_id(), at_ids, at_list, self_id
                )
            except Exception as exc:
                logger.error(f"plain_help_deer failed: {exc}")
                yield event.plain_result("操作失败，请稍后重试。")
                return

            success_count = sum(1 for r in results if r["success"])
            at_ids_list = list(at_ids)

            if len(at_ids_list) == 1:
                # 单人：输出被帮者的日历图片或失败提示
                result_data = (
                    results[0] if results else {"success": False, "reason": "未知错误"}
                )
                target_name = result_data["nickname"]

                if not result_data["success"]:
                    # 🦌失败，提示命令发起者原因
                    reason = result_data.get("reason", "无法帮🦌")
                    yield event.plain_result(f"❌ 无法帮 {target_name} 🦌：{reason}")
                    return

                async for cal_result, is_text in self.service.render_calendar(
                    event,
                    dt.date.today(),
                    self.html_render,
                    user_id=result_data["user_id"],
                ):
                    if is_text:
                        yield event.plain_result(f"成功帮{target_name}🦌了")
                        yield event.plain_result(cal_result)
                    else:
                        yield (
                            event.make_result()
                            .message(f"成功帮{target_name}🦌了")
                            .url_image(cal_result)
                        )
            else:
                # 多人：使用 batch_report 模板
                image_url = await self._render_batch_report(results, success_count)
                if image_url:
                    total = len(results)
                    msg = f"批量帮🦌完成！成功 {success_count}/{total} 人"
                    yield event.make_result().message(msg).url_image(image_url)
                else:
                    # 渲染失败，返回文本结果
                    lines = [f"批量帮🦌结果（{success_count}/{len(results)} 成功）："]
                    for r in results:
                        status = "✅" if r["success"] else "❌"
                        lines.append(f"{status} {r['nickname']} - 第 {r['count']} 次")
                    yield event.plain_result("\n".join(lines))
        else:
            # 自我打卡模式
            result = await self.service.handle_deer_self(event)

            # 渲染日历图片
            async for cal_result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render
            ):
                if is_text:
                    yield event.plain_result(result)
                    yield event.plain_result(cal_result)
                else:
                    yield event.make_result().message(result).url_image(cal_result)

    @filter.regex(r"^🦌历$")
    async def plain_deer_calendar_cmd(self, event: AstrMessageEvent):
        """处理纯 🦌历 消息（不带/前缀）."""
        from .utils import extract_mention_user_ids

        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)

        # 构建 user_id -> name 映射
        at_map = {str(m.qq): m.name for m in at_list if m.name}

        if at_ids:
            # 查看他人的鹿历
            target_id = str(at_list[0].qq)
            target_name = at_map.get(target_id, target_id)
            async for result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render, user_id=target_id
            ):
                if is_text:
                    yield event.plain_result(f"{target_name} 的鹿历：\n{result}")
                else:
                    yield (
                        event.make_result()
                        .message(f"{target_name} 的鹿历")
                        .url_image(result)
                    )
        else:
            # 查看自己的鹿历
            async for result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render
            ):
                if is_text:
                    yield event.plain_result(result)
                else:
                    yield event.image_result(result)

    @filter.regex(r"^上月🦌历$")
    async def plain_last_month_calendar_cmd(self, event: AstrMessageEvent):
        """处理纯 上月🦌历 消息（不带/前缀）."""
        from .utils import extract_mention_user_ids

        messages = event.message_obj.message
        at_list = [m for m in messages if isinstance(m, At)]
        at_ids = extract_mention_user_ids(at_list)

        # 构建 user_id -> name 映射
        at_map = {str(m.qq): m.name for m in at_list if m.name}

        first = dt.date.today().replace(day=1)
        last_month = (first - dt.timedelta(days=1)).replace(day=1)

        if at_ids:
            # 查看他人的上月鹿历
            target_id = str(at_list[0].qq)
            target_name = at_map.get(target_id, target_id)
            async for result, is_text in self.service.render_calendar(
                event, last_month, self.html_render, user_id=target_id
            ):
                if is_text:
                    yield event.plain_result(f"{target_name} 的上月鹿历：\n{result}")
                else:
                    yield (
                        event.make_result()
                        .message(f"{target_name} 的上月鹿历")
                        .url_image(result)
                    )
        else:
            # 查看自己的上月鹿历
            async for result, is_text in self.service.render_calendar(
                event, last_month, self.html_render
            ):
                if is_text:
                    yield event.plain_result(result)
                else:
                    yield event.make_result().message("上月鹿历").url_image(result)

    async def _render_batch_report(
        self, results: list[dict], success_count: int
    ) -> str | None:
        """渲染批量报告图片.

        Args:
            results: 打卡结果列表
            success_count: 成功人数

        Returns:
            图片 URL 或 None（渲染失败）
        """
        from pathlib import Path

        template_path = Path(__file__).parent / "templates" / "batch_report.html"
        css_path = (
            Path(__file__).parent / "templates" / "res" / "css" / "batch_report.css"
        )

        if not template_path.exists():
            logger.error(f"批量报告模板不存在: {template_path}")
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

            # 高度也直接按 2 倍物理像素计算
            # 头部(~200) + 列表容器上下内边距(40) + 每行(~112) + 底部(~160)
            estimated_height = 200 + 40 + len(payload["results"]) * 112 + 160

            # 调用渲染服务
            image_url = await self.html_render(
                html,
                payload,
                return_url=True,
                options={
                    "type": "png",
                    "full_page": False,
                    "scale": "device",  # 保持原本的参数，不用改
                    "clip": {
                        "x": 0,
                        "y": 0,
                        "width": 1360,  # 宽度直接锁定为 1360
                        "height": estimated_height,
                    },
                },
            )
            return image_url

        except Exception as exc:
            logger.error(f"批量报告渲染失败: {exc}")
            return None
