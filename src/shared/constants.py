"""DeerPipe 插件常量.

集中管理插件中所有可暴露的常量.
"""

from __future__ import annotations

from typing import Final, Literal

# =============================================================================
# 纯文本命令正则
# =============================================================================

PLAIN_DEER_TRIGGER_PATTERN: Final[str] = (
    r"^(?!/)(?:[🦌鹿撸]|撸🦌|帮\s*(?:[🦌鹿撸]|撸🦌))(?:\s+.*)?$"
)
"""纯文本打卡触发：仅完整短命令或“帮鹿/帮🦌 ...”格式，避免普通文本误触发."""

PLAIN_CALENDAR_TRIGGER_PATTERN: Final[str] = (
    r"^(?!/)(上月)?(\d{4}年\d{1,2}月)?[🦌鹿撸](历|🦌历)$"
)
"""纯文本鹿历查询触发."""

# =============================================================================
# HTTP 和网络相关常量
# =============================================================================

HTTP_TIMEOUT_SECONDS: Final[int] = 15
"""HTTP 请求超时时间（秒）."""

# =============================================================================
# 缓存相关常量
# =============================================================================

AVATAR_CACHE_TTL: Final[int] = 3600
"""头像缓存有效期（秒），默认1小时."""

AVATAR_CACHE_MAX_SIZE: Final[int] = 1024
"""头像缓存最大条目数，防止内存无限增长."""

# =============================================================================
# 数据库相关常量
# =============================================================================

DEFAULT_DAILY_RETRO_LIMIT: Final[int] = 31
"""每日补打卡次数上限（与 _conf_schema.json 的 max 保持一致）."""

# =============================================================================
# 渲染相关常量
# =============================================================================

MAX_FONT_SIZE: Final[int] = 1 * 1024 * 1024
"""字体文件大小限制（字节），避免 HTTP 422 payload too large，默认1MB."""

DEFAULT_COUNT_DISPLAY_MODE: Final[Literal["additive", "count"]] = "additive"
"""默认打卡次数显示模式（与 _conf_schema.json 默认值保持一致）."""

DEFAULT_SHOW_CHECK_MARK: Final[bool] = True
"""默认是否显示打勾图标（与 _conf_schema.json 默认值保持一致）."""

# 日历图片渲染尺寸
CALENDAR_IMAGE_WIDTH: Final[int] = 1360
"""日历图片默认宽度（像素）."""

# 角色图片选择阈值
CHARACTER_THRESHOLD_HIGH: Final[int] = 50
"""高阶角色图片打卡次数阈值."""

CHARACTER_THRESHOLD_MEDIUM: Final[int] = 20
"""中阶角色图片打卡次数阈值."""

# 角色图片编号范围
CHARACTER_RANGE_HIGH: Final[tuple[int, int]] = (9, 11)
"""高阶角色图片编号范围（count >= 50）."""

CHARACTER_RANGE_MEDIUM: Final[tuple[int, int]] = (5, 8)
"""中阶角色图片编号范围（20 <= count < 50）."""

CHARACTER_RANGE_LOW: Final[tuple[int, int]] = (1, 4)
"""初阶角色图片编号范围（count < 20）."""

# =============================================================================
# 会话和超时相关常量
# =============================================================================

IMPORT_SESSION_TIMEOUT: Final[int] = 300
"""导入会话超时时间（秒），默认5分钟."""

# =============================================================================
# 文件大小限制
# =============================================================================

MAX_IMPORT_FILE_SIZE: Final[int] = 10 * 1024 * 1024
"""导入文件大小限制（字节），默认10MB."""

# =============================================================================
# 消息模板键名
# =============================================================================

# 模板键名常量，用于类型提示和防止拼写错误
TEMPLATE_GROUP_ONLY: Final[str] = "group_only"
TEMPLATE_OPERATION_FAILED: Final[str] = "operation_failed"
TEMPLATE_DEER_PAST_LIMIT: Final[str] = "deer_past_limit"
TEMPLATE_DEER_PAST_SUCCESS: Final[str] = "deer_past_success"
TEMPLATE_CALENDAR_LOAD_FAILED: Final[str] = "calendar_load_failed"
TEMPLATE_FALLBACK_CALENDAR_HEADER: Final[str] = "fallback_calendar_header"
TEMPLATE_FALLBACK_CALENDAR_STATS: Final[str] = "fallback_calendar_stats"

# =============================================================================
# LLM 工具名称
# =============================================================================

LLM_TOOL_DEER_SELF: Final[str] = "deer_self"
LLM_TOOL_DEER_OTHER: Final[str] = "deer_other"
LLM_TOOL_RETRO_DEER: Final[str] = "retro_deer"
LLM_TOOL_SET_ALLOW_HELP: Final[str] = "set_allow_help"
LLM_TOOL_GET_USER_DEER_DATA: Final[str] = "get_user_deer_data"

LLM_TOOLS: Final[list[str]] = [
    LLM_TOOL_DEER_SELF,
    LLM_TOOL_DEER_OTHER,
    LLM_TOOL_RETRO_DEER,
    LLM_TOOL_SET_ALLOW_HELP,
    LLM_TOOL_GET_USER_DEER_DATA,
]
"""所有 LLM 工具名称列表."""

# =============================================================================
# 平台相关
# =============================================================================

PLATFORM_AIOCQHTTP: Final[str] = "aiocqhttp"
"""QQ 平台适配器名称."""

# QQ 头像服务 URL 模板
QQ_AVATAR_URL_TEMPLATE: Final[str] = "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
"""QQ 头像服务 URL 模板."""
