"""Deer-pipe plugin utility functions.

通用工具函数模块，包括图片处理和正则表达式等。
"""

from __future__ import annotations

import asyncio
import base64
import calendar
import re
from pathlib import Path
from typing import Any

import aiohttp

from astrbot.api import logger
from astrbot.core.message.components import At


def normalize_user_id(user_id: Any) -> str:
    """将用户 ID 归一化为字符串.

    Args:
        user_id: 任意类型的用户 ID

    Returns:
        字符串类型的用户 ID
    """
    return str(user_id)


# HTTP 请求超时时间 (秒)
HTTP_TIMEOUT_SECONDS = 15

# 全局共享的 aiohttp ClientSession
_aiohttp_session: aiohttp.ClientSession | None = None
_aiohttp_session_lock = asyncio.Lock()


async def _get_aiohttp_session() -> aiohttp.ClientSession:
    """获取全局共享的 aiohttp ClientSession.

    Returns:
        全局共享的 ClientSession 实例
    """
    global _aiohttp_session
    # 双重检查锁，避免在高并发时重复创建 ClientSession
    if _aiohttp_session is not None and not _aiohttp_session.closed:
        return _aiohttp_session

    async with _aiohttp_session_lock:
        if _aiohttp_session is None or _aiohttp_session.closed:
            _aiohttp_session = aiohttp.ClientSession()
        return _aiohttp_session


async def close_aiohttp_session() -> None:
    """关闭全局共享的 aiohttp ClientSession.

    在应用关闭时调用，避免资源泄漏和事件循环清理警告。
    """
    global _aiohttp_session
    if _aiohttp_session is not None and not _aiohttp_session.closed:
        await _aiohttp_session.close()
        logger.debug("[DeerPipe] aiohttp ClientSession 已关闭")
    _aiohttp_session = None


def image_to_data_uri(image_path: Path) -> str:
    """将本地图片文件转换为 base64 data URI.

    Args:
        image_path: 图片文件的完整路径

    Returns:
        base64 data URI 字符串，文件不存在时返回空字符串
    """
    if not image_path.exists():
        logger.warning(f"图片文件不存在: {image_path}")
        return ""

    try:
        data = image_path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.error(f"读取图片失败 {image_path}: {e}")
        return ""


async def fetch_avatar_base64(user_id: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> str:
    """获取 QQ 用户头像并转换为 base64 data URI.

    从 QQ 头像服务获取用户头像，失败时返回空字符串。
    使用全局共享的 ClientSession 以提高性能。

    Args:
        user_id: QQ 用户 ID（应为纯数字）
        timeout: 请求超时时间 (秒)

    Returns:
        base64 data URI 字符串
    """
    # 基础输入校验：QQ号应为纯数字
    if not user_id or not user_id.isdigit():
        logger.warning(f"无效的用户ID格式: {user_id}")
        return ""

    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    try:
        session = await _get_aiohttp_session()
        async with session.get(avatar_url, timeout=client_timeout) as resp:
            resp.raise_for_status()
            data = await resp.read()
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.warning(f"获取头像失败 {user_id}: {e}")
        return ""


def extract_mention_user_ids(messages: list[At]) -> set[str]:
    """从消息中提取 @ 提及的用户 ID 集合.

    Args:
        messages: At 组件列表

    Returns:
        被 @ 的用户 ID 集合（自动去重）
    """
    return {normalize_user_id(m.qq) for m in messages}


def parse_allow_flag(text: str) -> bool | None:
    """解析允许/开启标志.

    从文本中解析开关状态。支持多种表达方式：
    - 开/on/允许/开启/打开/启用/可以/能
    - 关/off/禁止/关闭/关掉/禁用/不可以/不能

    使用正则匹配避免子串误判（例如"不要开启"不应被误判为"开启"）。

    Args:
        text: 包含开关标志的文本

    Returns:
        True 表示开启/允许，False 表示关闭/禁止，None 表示无法解析
    """
    # 将文本转换为小写并去除首尾空格
    normalized = text.strip().lower()

    # 定义边界字符（空白或标点）
    boundary = r"(^|[\s,，.;；：:!！?？])"
    end_boundary = r"(?=[\s,，.;；：:!！?？]|$)"

    # 匹配 "开" 类表达：开、on、允许、开启、打开、启用、可以、能
    open_patterns = r"(开|on|允许|开启|打开|启用|可以|能)"
    if re.search(boundary + open_patterns + end_boundary, normalized, re.IGNORECASE):
        return True

    # 匹配 "关" 类表达：关、off、禁止、关闭、关掉、禁用、不可以、不能
    close_patterns = r"(关|off|禁止|关闭|关掉|禁用|不可以|不能)"
    if re.search(boundary + close_patterns + end_boundary, normalized, re.IGNORECASE):
        return False

    return None


def validate_day(day: int, year: int, month: int) -> tuple[bool, str]:
    """验证日期是否有效.

    Args:
        day: 日期
        year: 年份
        month: 月份

    Returns:
        (是否有效, 错误信息)
    """
    if day < 1:
        return False, "日期必须大于等于 1"

    max_day = calendar.monthrange(year, month)[1]
    if day > max_day:
        return False, f"日期无效，本月范围为 1-{max_day}"

    return True, ""
