"""Deer-pipe plugin utility functions.

通用工具函数模块，包括图片处理和正则表达式等。
"""

from __future__ import annotations

import base64
from pathlib import Path

import aiohttp

from astrbot.api import logger
from astrbot.core.message.components import At

# HTTP 请求超时时间 (秒)
HTTP_TIMEOUT_SECONDS = 15


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

    Args:
        user_id: QQ 用户 ID
        timeout: 请求超时时间 (秒)

    Returns:
        base64 data URI 字符串
    """
    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(avatar_url) as resp:
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
    return {str(m.qq) for m in messages}


def parse_allow_flag(text: str) -> bool | None:
    """解析允许/开启标志.

    从文本中解析开关状态。

    Args:
        text: 包含开关标志的文本

    Returns:
        True 表示开启/允许，False 表示关闭/禁止，None 表示无法解析
    """
    if any(kw in text for kw in ("开", "on", "允许")):
        return True
    if any(kw in text for kw in ("关", "off", "禁止")):
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
    import calendar

    if day < 1:
        return False, "日期必须大于等于 1"

    max_day = calendar.monthrange(year, month)[1]
    if day > max_day:
        return False, f"日期无效，本月范围为 1-{max_day}"

    return True, ""
