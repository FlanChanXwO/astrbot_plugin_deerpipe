"""DeerPipe plugin entry point.

鹿管打卡插件主模块，使用命令模式重构以简化代码结构。
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from astrbot.api import llm_tool
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, StarTools
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import Plain

from .src import (
    LLM_TOOLS,
    AdminCommandHandler,
    CalendarCommandHandler,
    CalendarRenderer,
    DatabaseManager,
    DataCommandHandler,
    DataManager,
    DeerCommandHandler,
    DeerPipeHTMLRenderer,
    DeerPipeLLMTools,
    DeerPipeService,
    LeaderboardCommandHandler,
    LeaderboardType,
    close_aiohttp_session,
    get_logger,
)
from .src.domain.datamodels import ToolResult

logger = get_logger()


class DeerPipePlugin(Star):
    """Deer-pipe daily check-in plugin with SQLite persistence."""

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

        # 初始化命令处理器（轻量级，直接传入所需依赖）
        self.deer_handler = DeerCommandHandler(self.service)
        self.calendar_handler = CalendarCommandHandler(self.service)
        self.admin_handler = AdminCommandHandler(self.service)
        self.data_handler = DataCommandHandler(self.data_manager)
        self.base_dir = Path(__file__).parent
        self.leaderboard_handler = LeaderboardCommandHandler(
            self.service, self.db, self.base_dir
        )

        # 初始化 HTML 渲染器（根据配置选择 t2i 或 playwright）
        rendering_cfg = self.config.get("rendering", {})
        use_t2i = rendering_cfg.get("use_t2i", False)  # 默认使用 Playwright
        jpeg_quality = rendering_cfg.get("jpeg_quality", 95)

        # 诊断日志：输出配置值
        logger.info(f"[DeerPipe] 插件名称: {self.name}")
        logger.info(f"[DeerPipe] 完整配置: {self.config}")
        logger.info(f"[DeerPipe] rendering_cfg: {rendering_cfg}")
        logger.info(f"[DeerPipe] use_t2i 配置值: {use_t2i}")

        self.html_render = DeerPipeHTMLRenderer(use_t2i=use_t2i, jpeg_quality=jpeg_quality)
        logger.info(f"[DeerPipe] HTML 渲染器已初始化: use_t2i={use_t2i}, jpeg_quality={jpeg_quality}")

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
            plugin_config = config.get(self.name)
            if isinstance(plugin_config, dict):
                return plugin_config
            # 不含插件配置键时返回空 dict，而不是整个 config
            return {}
        return {}

    async def terminate(self):
        """插件卸载时清理资源."""
        self._unregister_llm_tools()
        # 关闭 HTML 渲染器
        if hasattr(self, "html_render") and self.html_render:
            await self.html_render.close()
        # 关闭全局 aiohttp session，防止资源泄漏
        await close_aiohttp_session()

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求时附加自定义 prompt."""
        ai_config = self.config.get("ai_behavior", {})
        custom_prompt = (
            ai_config.get("custom_prompt", "") if isinstance(ai_config, dict) else ""
        )
        if custom_prompt:
            logger.debug("当前 custom_prompt 长度: %d", len(custom_prompt))
            current_prompt = req.system_prompt or ""
            logger.debug("当前 system_prompt 长度: %d", len(current_prompt))
            req.system_prompt = f"{current_prompt}\n\n{custom_prompt}"
            logger.debug(
                "已追加 custom_prompt，当前 system_prompt 长度: %d",
                len(req.system_prompt),
            )

    def _unregister_llm_tools(self):
        """注销所有LLM工具函数."""
        try:
            func_tool_mgr = self.context.get_llm_tool_manager()
            for tool_name in LLM_TOOLS:
                func_tool_mgr.remove_tool(tool_name)
                logger.info(f"已移除LLM工具: {tool_name}")
        except (AttributeError, RuntimeError) as e:
            logger.error(f"移除LLM工具失败: {e}")

    @staticmethod
    def _is_send_ack_timeout(exc: Exception) -> bool:
        """检查是否是发送确认超时错误."""
        msg = str(exc).lower()
        ack_timeout_hints = (
            "retcode=1200",
            "retcode:1200",
            "retcode 1200",
            '"retcode": 1200',
            "'retcode': 1200",
        )
        return any(hint in msg for hint in ack_timeout_hints)

    async def _send_calendar_non_fatal(
        self,
        event: AstrMessageEvent,
        cal_result: str,
        is_text: bool,
        result: ToolResult,
        tool_name: str,
    ) -> None:
        """非致命性地发送日历（失败时记录警告但不中断流程）."""
        try:
            if is_text:
                await event.send(event.plain_result(cal_result))
            else:
                await event.send(event.image_result(cal_result))
        except (OSError, RuntimeError) as exc:
            if self._is_send_ack_timeout(exc):
                logger.info(f"{tool_name} calendar send ack timeout: {exc}")
                result.append_delivery_warning("SEND_ACK_TIMEOUT_MAY_DELIVERED", exc)
                return
            logger.warning(f"{tool_name} calendar send failed: {exc}")
            result.append_delivery_warning("CALENDAR_SEND_FAILED", exc)

    # ==================================================================
    # LLM Tools - AI工具函数
    # ==================================================================
    @llm_tool("deer_self")
    async def tool_deer_self(self, event: AstrMessageEvent) -> str:
        """Check in (deer) for yourself today.

        Use this when user wants to check in for themselves.
        Examples: "我要打卡", "今天鹿一下", etc.

        """
        user_id = str(event.get_sender_id())
        result = ToolResult.from_dict(await self.llm_tools.deer_self(user_id))

        # 如果打卡成功，发送🦌历图片
        if result.success:
            async for cal_result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render, user_id=user_id
            ):
                await self._send_calendar_non_fatal(
                    event, cal_result, is_text, result, "deer_self"
                )

        return json.dumps(result.to_dict(), ensure_ascii=False)

    @llm_tool("deer_other")
    async def tool_deer_other(
        self, event: AstrMessageEvent, target_ids: list[str]
    ) -> str:
        """Help other users check in (deer) on their behalf.

        Use this when user wants to help others check in.
        Examples: "帮@小明打卡", "帮大家鹿一下", etc.

        Args:
            target_ids (list[str]): List of user IDs to help check in for
        """
        user_id = str(event.get_sender_id())
        bot_id = str(event.get_self_id()) if event.get_self_id() else None
        target_ids = [str(tid) for tid in target_ids]
        result = ToolResult.from_dict(
            await self.llm_tools.deer_other(user_id, target_ids, bot_id)
        )

        # 如果帮打卡成功，为第一个成功的用户发送🦌历图片
        if result.success and target_ids:
            display_user_id = user_id if user_id in target_ids else target_ids[0]
            if display_user_id:
                async for cal_result, is_text in self.service.render_calendar(
                    event, dt.date.today(), self.html_render, user_id=display_user_id
                ):
                    await self._send_calendar_non_fatal(
                        event, cal_result, is_text, result, "deer_other"
                    )

        return json.dumps(result.to_dict(), ensure_ascii=False)

    @llm_tool("retro_deer")
    async def tool_retro_deer(
        self,
        event: AstrMessageEvent,
        day: int,
        year: int,
        month: int,
    ) -> str:
        """Make a retroactive check-in (deer) for a specific past day.

        Use this when user wants to retroactively check in for a past day.
        Examples: "补打卡昨天", "补录3号的记录", "补鹿5号", etc.

        Args:
            day (int): The day of the month to retroactively check in (1-31)
            year (int): The year (e.g., 2025), uses current year if not specified
            month (int): The month (1-12), uses current month if not specified
        """
        user_id = str(event.get_sender_id())
        result = ToolResult.from_dict(
            await self.llm_tools.retro_deer(
                user_id,
                day,
                year if year is not None and year > 0 else None,
                month if month is not None and month > 0 else None,
            )
        )

        # 如果补打卡成功，发送🦌历图片
        if result.success:
            async for cal_result, is_text in self.service.render_calendar(
                event, dt.date.today(), self.html_render, user_id=user_id
            ):
                await self._send_calendar_non_fatal(
                    event, cal_result, is_text, result, "retro_deer"
                )

        return json.dumps(result.to_dict(), ensure_ascii=False)

    @llm_tool("set_allow_help")
    async def tool_set_allow_help(self, event: AstrMessageEvent, allowed: bool) -> str:
        """Set whether others can help check in (deer) for you.

        Use this when user wants to allow or disallow others from helping them check in.
        Examples: "允许别人帮我打卡", "禁止别人帮我鹿", "开启帮打卡", "关闭帮打卡", etc.

        Args:
            allowed (bool): True to allow others to help check in, False to disallow
        """
        user_id = str(event.get_sender_id())
        result = ToolResult.from_dict(
            await self.llm_tools.set_allow_help(user_id, allowed)
        )
        return json.dumps(result.to_dict(), ensure_ascii=False)

    @llm_tool("get_user_deer_data")
    async def tool_get_user_deer_data(
        self,
        event: AstrMessageEvent,
        year: int,
        month: int,
    ) -> str:
        """Get user's deer check-in data including calendar and statistics.

        Use this when user wants to check their data for a specific month or year.
        Examples: "查看2025年3月的鹿历", "我去年打卡了多少次", etc.

        Args:
            year (int): Year (e.g., 2025), uses current year if not specified
            month (int): Month (1-12), uses current month if not specified
        """
        user_id = str(event.get_sender_id())
        year_val = year if year is not None and year > 0 else None
        month_val = month if month is not None and month > 0 else None

        # 合并获取日历和统计数据
        calendar_result = await self.llm_tools.get_calendar(
            user_id, year_val, month_val
        )
        stats_result = await self.llm_tools.get_user_stats(user_id)

        result = ToolResult(
            success=calendar_result.get("success", False)
            and stats_result.get("success", False),
            user_id=user_id,
            calendar=calendar_result.get("calendar", {}),
            stats=stats_result.get("current_month", {}),
            analysis=calendar_result.get("analysis", {}),
            user_settings={"allow_help": stats_result.get("allow_help", True)},
            note="For visual calendar image, use /🦌历 command",
        )

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
                    await self._send_calendar_non_fatal(
                        event, cal_result, is_text, result, "get_user_deer_data"
                    )
            except ValueError as exc:
                logger.warning(
                    f"Invalid date parameters: year_val={year_val}, month_val={month_val}, exc={exc}"
                )

        return json.dumps(result.to_dict(), ensure_ascii=False)

    # ==================================================================
    # Command Handlers (使用命令处理器)
    # ==================================================================

    @filter.command("deer", alias={"鹿", "🦌", "撸", "撸🦌"})
    async def deer_cmd(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        """自我打卡或帮他人打卡 (/deer)."""
        async for result in self.deer_handler.run_deer_checkin(event, self.html_render):
            yield result

    @filter.command("允许被鹿", alias={"允许被🦌", "允许被撸", "允许被撸🦌"})
    async def allow_deer(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        """允许他人帮自己打卡 (/允许被鹿)."""
        result = await self.deer_handler.handle_allow_deer(event)
        yield event.plain_result(result)

    @filter.command("禁止被鹿", alias={"禁止被🦌", "禁止被撸", "禁止被撸🦌"})
    async def forbid_deer(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        """禁止他人帮自己打卡 (/禁止被鹿)."""
        result = await self.deer_handler.handle_forbid_deer(event)
        yield event.plain_result(result)

    @filter.command_group("设置被鹿", alias={"设置被撸", "设置被撸🦌"})
    async def set_deer_group(self, event: AstrMessageEvent) -> None:
        """管理员设置他人的帮deer权限"""

    @filter.permission_type(filter.PermissionType.ADMIN)
    @set_deer_group.command("开", alias={"on", "撸", "撸🦌"})
    async def set_deer_on(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        """管理员允许他人被帮deer (/设置被鹿 开 @用户)."""
        result = await self.admin_handler.handle_set_deer_on(event)
        if result:
            yield event.plain_result(result)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @set_deer_group.command("关", alias={"off", "禁撸", "禁撸🦌"})
    async def set_deer_off(self, event: AstrMessageEvent) -> AsyncGenerator[Any, None]:
        """管理员禁止他人被帮deer (/设置被鹿 关 @用户)."""
        result = await self.admin_handler.handle_set_deer_off(event)
        if result:
            yield event.plain_result(result)

    @filter.command("retro_deer", alias={"补鹿", "补🦌", "补撸", "补撸🦌"})
    async def retro_deer_cmd(
        self, event: AstrMessageEvent, day: int
    ) -> AsyncGenerator[Any, None]:
        """补deer (/retro_deer <day>)."""
        result = await self.deer_handler.handle_retro_deer(event, day)
        if result:
            yield event.plain_result(result)

    @filter.command(
        "deer_calendar",
        alias={
            "鹿历",
            "🦌历",
            "撸历",
            "撸🦌历",
            "上月鹿历",
            "上月🦌历",
            "上月撸历",
            "上月撸🦌历",
        },
    )
    async def deer_calendar_cmd(
        self, event: AstrMessageEvent, year: int = 0, month: int = 0
    ) -> AsyncGenerator[Any, None]:
        """显示指定月份日历 (/deer_calendar [year] [month]).

        示例:
            /deer_calendar - 显示本月日历
            /deer_calendar 2025 3 - 显示2025年3月日历
            /deer_calendar 0 3 - 显示今年3月日历
            /上月鹿历 - 显示上月日历
        """
        # 检查是否是"上月"命令
        plain_text = ""
        for comp in event.get_messages():
            if isinstance(comp, Plain):
                plain_text = comp.text.strip()
                break

        if plain_text.startswith(("上月", "/上月")):
            today = dt.date.today()
            first = today.replace(day=1)
            target_date = (first - dt.timedelta(days=1)).replace(day=1)
            title = "📅 上月鹿历"
        elif year > 0 or month > 0:
            target_date = dt.date.today()
            if year > 0:
                target_date = target_date.replace(year=year)
            if 1 <= month <= 12:
                target_date = target_date.replace(month=month)
            title = f"📅 {target_date.year}年{target_date.month}月鹿历"
        else:
            target_date = dt.date.today()
            title = None

        async for result in self.calendar_handler.handle_calendar_query(
            event, self.html_render, target_date, title
        ):
            yield result

    # ==================================================================
    # Data export/import commands
    # ==================================================================
    @filter.command_group("管理鹿管数据", alias={"管理🦌管数据"})
    async def deer_data_group(self, event: AstrMessageEvent) -> None:
        """鹿管数据管理（导入/导出）"""

    @filter.permission_type(filter.PermissionType.ADMIN)
    @deer_data_group.command("导出", alias={"export"})
    async def export_data_cmd(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """导出所有数据 (/管理鹿管数据 导出)."""
        async for result in self.data_handler.handle_export_data(event):
            yield result

    @filter.permission_type(filter.PermissionType.ADMIN)
    @deer_data_group.command("导入", alias={"import"})
    async def import_data_cmd(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """导入数据 (/管理鹿管数据 导入)."""
        async for result in self.data_handler.handle_import_data(event):
            yield result

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_file_message(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """监听文件消息以处理导入."""
        async for result in self.data_handler.handle_import_file(event):
            yield result

    # ==================================================================
    # Leaderboard commands
    # ==================================================================
    @filter.command(
        "deer_rank", alias={"鹿排行榜", "鹿排名", "鹿榜🦌排行榜", "🦌排名", "🦌榜"}
    )
    async def leaderboard_cmd(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """查看今日群打卡排行榜 (/leaderboard)."""
        async for result in self.leaderboard_handler.handle_leaderboard(
            event, self.html_render, LeaderboardType.DAILY
        ):
            yield result

    @filter.command("deer_yesterday_rank", alias={"昨日鹿榜", "昨日🦌榜"})
    async def yesterday_rank_cmd(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """查看昨日群打卡排行榜 (/yesterday_rank)."""
        async for result in self.leaderboard_handler.handle_leaderboard(
            event, self.html_render, LeaderboardType.YESTERDAY
        ):
            yield result

    @filter.command("deer_monthly_rank", alias={"鹿月榜", "🦌月榜"})
    async def monthly_rank_cmd(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """查看本月群打卡排行榜 (/monthly_rank)."""
        async for result in self.leaderboard_handler.handle_leaderboard(
            event, self.html_render, LeaderboardType.MONTHLY
        ):
            yield result

    @filter.command("deer_map", alias={"鹿力图", "鹿年历", "🦌力图"})
    async def deermap_cmd(
        self, event: AstrMessageEvent, year: int | None = None
    ) -> AsyncGenerator[Any, None]:
        """查看年度打卡热力图 (/deermap [年份])."""
        async for result in self.leaderboard_handler.handle_deermap(
            event, self.html_render, year
        ):
            yield result

    # ==================================================================
    # Plain message handlers (without / prefix)
    # ==================================================================

    def _is_explicit_slash_command(self, event: AstrMessageEvent) -> bool:
        """检查消息是否以 / 开头."""
        for comp in event.get_messages():
            if isinstance(comp, Plain):
                return comp.text.strip().startswith("/")
        return False

    def _parse_calendar_date(self, text: str) -> tuple[dt.date, str] | None:
        """从文本中解析日历查询日期.

        支持的格式:
        - 🦌历 / 鹿历 / 撸历 / 撸🦌历 -> 本月
        - 上月🦌历 / 上月鹿历 -> 上月
        - 2025年3月🦌历 / 2025年3月鹿历 -> 指定年月

        Args:
            text: 用户输入文本

        Returns:
            (target_date, title) 或 None 如果不匹配
        """
        import re

        text = text.strip()

        # 匹配 "上月🦌历" 格式
        if re.match(r"^上月[🦌鹿撸](历|🦌历)$", text):
            today = dt.date.today()
            first = today.replace(day=1)
            last_month = (first - dt.timedelta(days=1)).replace(day=1)
            return last_month, "📅 上月鹿历"

        # 匹配 "2025年3月🦌历" 格式
        match = re.match(r"^(\d{4})年(\d{1,2})月[🦌鹿撸](历|🦌历)$", text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            if 1 <= month <= 12:
                try:
                    target_date = dt.date(year, month, 1)
                    return target_date, f"📅 {year}年{month}月鹿历"
                except ValueError:
                    return None
            return None

        # 匹配 "🦌历" / "鹿历" / "撸历" / "撸🦌历" 格式 (本月)
        if re.match(r"^[🦌鹿撸](历|🦌历)$", text):
            today = dt.date.today()
            return today, None  # None 表示使用默认标题

        return None

    @filter.regex(r"^(?!/)(🦌|鹿|撸|撸🦌)(?!历)")
    async def plain_deer_merged_cmd(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """纯文本打卡命令（不带/前缀）."""
        if self._is_explicit_slash_command(event):
            return

        async for result in self.deer_handler.run_deer_checkin(event, self.html_render):
            yield result

    @filter.regex(r"^(?!/)(上月)?(\d{4}年\d{1,2}月)?[🦌鹿撸](历|🦌历)$")
    async def plain_calendar_merged_cmd(
        self, event: AstrMessageEvent
    ) -> AsyncGenerator[Any, None]:
        """纯文本日历查询命令（不带/前缀）.

        支持格式:
        - 🦌历 / 鹿历 / 撸历 / 撸🦌历 -> 本月
        - 上月🦌历 / 上月鹿历 -> 上月
        - 2025年3月🦌历 / 2025年3月鹿历 -> 指定年月
        """
        if self._is_explicit_slash_command(event):
            return

        for comp in event.get_messages():
            if isinstance(comp, Plain):
                parsed = self._parse_calendar_date(comp.text)
                if parsed:
                    target_date, title = parsed
                    async for result in self.calendar_handler.handle_calendar_query(
                        event, self.html_render, target_date, title
                    ):
                        yield result
                    return
