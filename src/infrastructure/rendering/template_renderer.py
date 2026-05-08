"""Template renderer.

通用模板渲染器，负责HTML模板的技术渲染实现。
"""

from __future__ import annotations

from typing import Any

from ..utils.logger import get_logger

logger = get_logger()


class TemplateRenderer:
    """通用模板渲染器.

    负责HTML模板的纯技术渲染工作，不包含业务逻辑。
    """

    def __init__(self) -> None:
        """初始化模板渲染器."""
        self.logger = logger

    async def render(
        self,
        html: str,
        payload: dict[str, Any],
        html_render_func,
        options: dict | None = None,
    ) -> str:
        """渲染HTML模板为图片.

        纯技术实现：
        1. 调用传入的渲染函数（t2i 或 playwright）
        2. 处理渲染结果

        Args:
            html: HTML模板字符串
            payload: 渲染数据
            html_render_func: HTML渲染函数
            options: 渲染选项

        Returns:
            渲染后的图片URL

        Raises:
            Exception: 渲染失败
        """
        try:
            # 调用渲染服务
            image_url = await html_render_func(
                html,
                payload,
                return_url=True,
                options=options
                or {
                    "type": "png",
                    "full_page": True,
                    "scale": "device",
                },
            )

            return image_url

        except Exception as e:
            self.logger.error(f"模板渲染失败: {e}")
            raise

    @staticmethod
    def schedule_temp_cleanup(
        html_render,
        file_path: str,
        delay_seconds: int = 60,
    ) -> None:
        """调度临时文件清理.

        Args:
            html_render: HTML渲染对象
            file_path: 要清理的文件路径
            delay_seconds: 延迟秒数
        """
        schedule = getattr(html_render, "schedule_temp_cleanup", None)
        if callable(schedule):
            schedule(file_path, delay_seconds)
