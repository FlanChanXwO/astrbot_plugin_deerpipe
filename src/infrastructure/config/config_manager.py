"""配置管理模块

提供统一的、类型安全的插件配置访问。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AIBehaviorConfig(BaseModel):
    """AI 行为配置"""

    allow_ai_help_deer: bool = Field(default=True, description="允许 AI 帮用户 🦌")
    allow_ai_be_deered: bool = Field(default=False, description="允许 AI 被 🦌")
    allow_ai_help_self: bool = Field(default=True, description="允许 AI 帮用户自己打卡")
    custom_prompt: str = Field(default="", description="自定义 LLM Prompt")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AIBehaviorConfig:
        """从字典创建配置"""
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class LimitsConfig(BaseModel):
    """限制配置"""

    daily_retro_limit: int = Field(default=1, description="每日补🦌次数限制")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> LimitsConfig:
        """从字典创建配置"""
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class CalendarConfig(BaseModel):
    """日历显示配置"""

    count_display_mode: str = Field(default="additive", description="打卡次数显示模式")
    show_check_mark: bool = Field(default=True, description="显示打勾图标")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CalendarConfig:
        """从字典创建配置"""
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class RenderingConfig(BaseModel):
    """渲染引擎配置"""

    render_timeout: int = Field(default=30, description="渲染超时时间(秒)")
    jpeg_quality: int = Field(default=95, description="JPEG 图片质量")
    use_t2i: bool = Field(
        default=False,
        description="使用 AstrBot 内置 t2i 服务渲染图片，无需安装 Playwright",
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RenderingConfig:
        """从字典创建配置"""
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class DeerPipePluginConfig(BaseModel):
    """DeerPipe 插件统一配置类"""

    ai_behavior: AIBehaviorConfig = Field(default_factory=AIBehaviorConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    calendar: CalendarConfig = Field(default_factory=CalendarConfig)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)

    @classmethod
    def from_astrbot_config(
        cls, raw_config: dict[str, Any] | None
    ) -> DeerPipePluginConfig:
        """从 AstrBot 配置字典创建配置对象"""
        if not raw_config:
            return cls()

        return cls(
            ai_behavior=AIBehaviorConfig.from_dict(raw_config.get("ai_behavior", {})),
            limits=LimitsConfig.from_dict(raw_config.get("limits", {})),
            calendar=CalendarConfig.from_dict(raw_config.get("calendar", {})),
            rendering=RenderingConfig.from_dict(raw_config.get("rendering", {})),
        )

    def save(self, raw_config: dict[str, Any]) -> None:
        """保存配置到原始配置字典"""
        config_dict = self.model_dump()
        for key, value in config_dict.items():
            raw_config[key] = value

    # 向后兼容属性

    @property
    def render_timeout(self) -> int:
        return self.rendering.render_timeout

    @property
    def jpeg_quality(self) -> int:
        return self.rendering.jpeg_quality

    @property
    def daily_retro_limit(self) -> int:
        return self.limits.daily_retro_limit

    @property
    def count_display_mode(self) -> str:
        return self.calendar.count_display_mode

    @property
    def show_check_mark(self) -> bool:
        return self.calendar.show_check_mark

    @property
    def allow_ai_help_deer(self) -> bool:
        return self.ai_behavior.allow_ai_help_deer

    @property
    def allow_ai_be_deered(self) -> bool:
        return self.ai_behavior.allow_ai_be_deered

    @property
    def allow_ai_help_self(self) -> bool:
        return self.ai_behavior.allow_ai_help_self

    @property
    def custom_prompt(self) -> str:
        return self.ai_behavior.custom_prompt

    @property
    def use_t2i(self) -> bool:
        return self.rendering.use_t2i


# ---------------------------------------------------------------------------
# 单例管理
# ---------------------------------------------------------------------------

_config_instance: DeerPipePluginConfig | None = None


def init_config(raw_config: dict[str, Any] | None) -> DeerPipePluginConfig:
    """初始化配置单例（在插件 __init__ 中调用一次）"""
    global _config_instance
    _config_instance = DeerPipePluginConfig.from_astrbot_config(raw_config)
    return _config_instance


def get_config() -> DeerPipePluginConfig:
    """获取配置单例"""
    if _config_instance is None:
        raise RuntimeError("Config not initialized, call init_config() first")
    return _config_instance


def refresh_config(raw_config: dict[str, Any] | None) -> DeerPipePluginConfig:
    """刷新配置（配置变更时调用）"""
    global _config_instance
    _config_instance = DeerPipePluginConfig.from_astrbot_config(raw_config)
    return _config_instance


def clear_config() -> None:
    """清除配置单例（测试用）"""
    global _config_instance
    _config_instance = None
