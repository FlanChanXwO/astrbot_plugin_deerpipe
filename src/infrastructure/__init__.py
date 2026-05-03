"""Infrastructure layer.

基础设施层包含技术实现细节，如数据库、HTTP客户端、渲染等。
"""

from .persistence.database import DatabaseManager
from .rendering import (
    CalendarRenderer,
    DeerPipeHTMLRenderer,
    get_html_renderer,
    reset_html_renderer,
)
from .utils.http_utils import (
    close_aiohttp_session,
    extract_mention_user_ids,
    fetch_avatar_base64,
    image_to_data_uri,
    normalize_user_id,
    parse_allow_flag,
    validate_day,
)
from .utils.logger import get_logger, logger

__all__ = [
    # Persistence
    "DatabaseManager",
    # Rendering
    "CalendarRenderer",
    "DeerPipeHTMLRenderer",
    "get_html_renderer",
    "reset_html_renderer",
    # Utils
    "close_aiohttp_session",
    "extract_mention_user_ids",
    "fetch_avatar_base64",
    "get_logger",
    "image_to_data_uri",
    "logger",
    "normalize_user_id",
    "parse_allow_flag",
    "validate_day",
]
