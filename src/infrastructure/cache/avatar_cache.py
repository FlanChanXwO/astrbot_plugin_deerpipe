"""Avatar cache manager.

提供带 TTL 和 LRU 淘汰策略的头像缓存管理。
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Literal

from ...shared.constants import AVATAR_CACHE_MAX_SIZE, AVATAR_CACHE_TTL
from ..utils.http_utils import fetch_avatar_base64
from ..utils.logger import get_logger

logger = get_logger()


def make_avatar_cache_key(user_id: str, platform_name: str | None) -> str:
    """统一构造头像缓存 key，避免跨平台 user_id 冲突.

    Args:
        user_id: 用户 ID
        platform_name: 平台类型名称

    Returns:
        组合的缓存 key 字符串
    """
    return f"{platform_name}:{user_id}" if platform_name else f"_:{user_id}"


# 头像缓存: OrderedDict 实现 LRU 淘汰策略
_avatar_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
# 缓存操作锁，防止并发问题
_avatar_cache_lock = asyncio.Lock()
# 正在进行中的头像请求（用于请求合并防止缓存击穿）
_avatar_pending_requests: dict[str, asyncio.Task] = {}
_avatar_pending_lock = asyncio.Lock()


async def cleanup_avatar_cache(now: float | None = None) -> None:
    """清理过期的头像缓存，并在必要时进行容量控制。

    注意：调用此函数前必须已持有 _avatar_cache_lock，本函数内部不再获取锁。
    通常由 get_cached_avatar 在持有锁时调用。

    Args:
        now: 当前时间戳，如果为 None 则使用 time.time()
    """
    if now is None:
        now = time.time()

    # 删除已过期的条目
    expired_keys = [
        cache_key
        for cache_key, (timestamp, _data_uri) in _avatar_cache.items()
        if now - timestamp > AVATAR_CACHE_TTL
    ]
    for cache_key in expired_keys:
        _avatar_cache.pop(cache_key, None)

    # 控制缓存大小，超出时从最旧的条目开始淘汰
    while len(_avatar_cache) > AVATAR_CACHE_MAX_SIZE:
        # OrderedDict.popitem(last=False) 弹出最早插入/最久未使用的条目
        _avatar_cache.popitem(last=False)


async def _fetch_avatar_with_cache(
    user_id: str, platform_name: str | None, now: float
) -> str:
    """实际获取头像并更新缓存（内部函数）.

    此函数自行管理 _avatar_cache_lock，调用者无需持有锁。

    Args:
        user_id: 用户 ID
        platform_name: 平台类型名称
        now: 当前时间戳

    Returns:
        头像的 base64 data URI，失败返回空字符串
    """
    data = await fetch_avatar_base64(user_id, platform_name)
    cache_key = make_avatar_cache_key(user_id, platform_name)

    if data:
        # 获取锁后更新缓存，确保并发安全
        async with _avatar_cache_lock:
            await cleanup_avatar_cache(now)
            _avatar_cache[cache_key] = (now, data)
            _avatar_cache.move_to_end(cache_key)
            logger.debug(f"头像缓存更新: {cache_key}")
    return data


async def get_cached_avatar(
    user_id: str, platform_name: str | None = None
) -> str:
    """获取用户头像，带 TTL 缓存和 LRU 淘汰策略，支持请求合并防止缓存击穿.

    Args:
        user_id: 用户 ID
        platform_name: 平台类型名称（如 aiocqhttp, discord 等）

    Returns:
        头像的 base64 data URI，失败返回空字符串
    """
    now = time.time()
    cache_key = make_avatar_cache_key(user_id, platform_name)

    # 在锁内检查缓存（保证读写一致性）
    async with _avatar_cache_lock:
        cached = _avatar_cache.get(cache_key)
        if cached is not None:
            timestamp, data = cached
            if now - timestamp < AVATAR_CACHE_TTL:
                logger.debug(f"头像缓存命中: {cache_key}")
                # 更新访问顺序（LRU：将最新使用的移到队尾）
                _avatar_cache.move_to_end(cache_key)
                return data
            # 缓存已过期，删除
            _avatar_cache.pop(cache_key, None)

    # 缓存未命中，检查是否有正在进行中的请求（请求合并）
    async with _avatar_pending_lock:
        pending_task = _avatar_pending_requests.get(cache_key)
        if pending_task is not None and not pending_task.done():
            logger.debug(f"头像请求合并: {cache_key}")
            try:
                return await pending_task
            except (RuntimeError, asyncio.CancelledError):
                # 如果pending任务失败或被取消，继续执行新的请求
                logger.debug(f"头像请求任务失败或被取消，将创建新请求: {cache_key}")

        # 创建新的请求任务
        task = asyncio.create_task(
            _fetch_avatar_with_cache(user_id, platform_name, now)
        )
        _avatar_pending_requests[cache_key] = task

    try:
        return await task
    finally:
        # 清理已完成的pending请求
        async with _avatar_pending_lock:
            await _avatar_pending_requests.pop(cache_key, None)
