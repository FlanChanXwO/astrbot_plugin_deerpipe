"""Data import/export command handlers.

处理数据导入导出相关命令。
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from typing import TYPE_CHECKING

from astrbot.core.message.components import File

from ...domain import IMPORT_SESSION_TIMEOUT
from ...infrastructure import get_logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

    from ...application.services import DataManager

logger = get_logger()


class DataCommandHandler:
    """数据管理命令处理器.

    轻量级处理器，通过构造函数接收必要的依赖。
    """

    def __init__(self, data_manager: DataManager) -> None:
        """初始化命令处理器.

        Args:
            data_manager: 数据管理器实例
        """
        self.data_manager = data_manager
        self.logger = logger

        # 导入会话状态管理
        self._import_session_lock = asyncio.Lock()
        self._import_sessions: dict[str, float] = {}
        self._import_session_timeout = IMPORT_SESSION_TIMEOUT

    async def handle_export_data(self, event: AstrMessageEvent):
        """处理数据导出.

        Args:
            event: 消息事件

        Yields:
            发送给用户的响应
        """
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
            self.logger.error(f"导出文件发送失败: {e}")
            yield event.plain_result(f"{msg}\n文件发送失败: {e}")
        finally:
            # 确保临时文件被删除
            if temp_path:
                try:
                    os.unlink(temp_path)
                except (OSError, FileNotFoundError) as e:
                    self.logger.warning(f"删除临时导出文件失败: {e}")

    async def handle_import_data(self, event: AstrMessageEvent):
        """处理导入命令（启动导入会话）.

        Args:
            event: 消息事件

        Yields:
            发送给用户的响应
        """
        # 记录导入会话状态（绑定到具体用户，实例级隔离）
        user_id = event.get_sender_id()
        now = time.monotonic()
        async with self._import_session_lock:
            # 清理所有超时的会话，防止内存泄漏
            timeout_threshold = now - self._import_session_timeout
            expired_keys = [
                sid
                for sid, start_time in self._import_sessions.items()
                if start_time < timeout_threshold
            ]
            for sid in expired_keys:
                del self._import_sessions[sid]
            self._import_sessions[user_id] = now
        yield event.plain_result(
            "请发送 JSON 格式的数据文件（通常是 .json 文件），或在回复此消息时附上文件。\n"
            "注意：导入将合并现有数据，相同日期的记录会累加次数。\n"
            "请在5分钟内发送文件，超时请重新执行导入命令。"
        )

    async def handle_import_file(self, event: AstrMessageEvent):
        """处理文件导入.

        当管理员发送文件时，自动尝试解析并导入数据。
        需要满足以下条件才会处理：
        1. 是管理员身份
        2. 在执行导入命令后5分钟内
        3. 发送者是发起导入命令的用户本人（会话隔离）
        文件大小限制：10MB

        Args:
            event: 消息事件

        Yields:
            发送给用户的响应
        """
        # 检查是否是管理员（内部检查，避免每条消息都触发权限提示）
        if not event.is_admin():
            return

        sender_id = event.get_sender_id()

        # 检查是否有活跃的导入会话（实例级隔离）
        async with self._import_session_lock:
            session_start = self._import_sessions.get(sender_id)
            if session_start is None:
                return

            # 检查会话是否超时
            now = time.monotonic()
            if now - session_start > self._import_session_timeout:
                del self._import_sessions[sender_id]
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
                        self.logger.error(f"读取导入文件失败: {e}")
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
            self.logger.error(f"导入文件处理失败: {e}")
            yield event.plain_result(f"文件处理失败: {e}")
        finally:
            # 统一清理临时文件和会话状态
            async with self._import_session_lock:
                self._import_sessions.pop(sender_id, None)
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except (OSError, FileNotFoundError) as e:
                    self.logger.warning(f"删除临时导入文件失败: {e}")

    def clear_import_session(self, user_id: str) -> None:
        """清除指定用户的导入会话.

        Args:
            user_id: 用户ID
        """
        self._import_sessions.pop(user_id, None)

    def has_import_session(self, user_id: str) -> bool:
        """检查用户是否有活跃的导入会话.

        Args:
            user_id: 用户ID

        Returns:
            是否有活跃会话
        """
        return user_id in self._import_sessions
