"""User entity.

用户相关实体和值对象。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserConfig:
    """用户配置实体.

    Attributes:
        user_id: 用户唯一标识
        allow_help: 是否允许他人帮🦌
        last_retro_date: 上次补🦌日期 (ISO格式字符串)
    """

    user_id: str
    allow_help: bool = True
    last_retro_date: str = ""
