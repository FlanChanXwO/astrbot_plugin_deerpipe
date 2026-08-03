"""Base template renderer.

提供统一的模板渲染接口，确保所有渲染器遵循相同的模式。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger()


class BaseTemplateRenderer(ABC):
    """模板渲染器基类.

    定义统一的渲染流程：
    1. 加载模板和CSS
    2. 构建渲染数据（子类实现）
    3. 调用渲染服务
    4. 提供文本回退（子类实现）
    """

    def __init__(
        self,
        base_dir: Path,
        template_name: str,
        css_name: str | None = None,
    ) -> None:
        """初始化模板渲染器.

        Args:
            base_dir: 插件根目录
            template_name: 模板文件名（不含扩展名）
            css_name: CSS文件名（不含扩展名），可选
        """
        self.base_dir = base_dir
        self.logger = logger

        # 设置模板路径
        from ...shared import ResourcePaths

        paths = ResourcePaths(base_dir)
        self.template_path = paths.template(template_name)

        # 设置CSS路径（如果提供）
        self.css_path = paths.style(css_name) if css_name else None

    def _load_template(self) -> str:
        """加载HTML模板.

        Returns:
            HTML模板字符串

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        if not self.template_path.exists():
            raise FileNotFoundError(f"模板不存在: {self.template_path}")

        return self.template_path.read_text(encoding="utf-8")

    def _load_css(self) -> str:
        """加载CSS并包装在<style>标签中.

        Returns:
            CSS字符串（已包装在style标签中）或空字符串
        """
        if self.css_path is None or not self.css_path.exists():
            return ""

        raw_css = self.css_path.read_text(encoding="utf-8")
        return f"<style>{raw_css}</style>"

    @abstractmethod
    async def build_payload(self, *args, **kwargs) -> dict:
        """构建渲染数据负载.

        子类必须实现此方法，根据业务需求构建渲染所需的数据。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            渲染数据字典
        """

    async def render(
        self,
        html_render_func,
        *args,
        options: dict | None = None,
        **kwargs,
    ) -> str:
        """渲染模板为图片.

        统一的渲染流程：
        1. 加载模板和CSS
        2. 调用子类的 build_payload 构建数据
        3. 合并CSS到 payload
        4. 调用渲染服务

        Args:
            html_render_func: HTML渲染函数
            *args: 传递给 build_payload 的位置参数
            options: 渲染选项（type, full_page, scale等）
            **kwargs: 传递给 build_payload 的关键字参数

        Returns:
            渲染后的图片URL

        Raises:
            Exception: 渲染失败
        """
        try:
            # 加载模板
            html = self._load_template()

            # 构建数据负载
            payload = await self.build_payload(*args, **kwargs)

            # 合并CSS
            css_content = self._load_css()
            if css_content:
                payload["css_style"] = css_content

            # 调用渲染服务
            image_url = await html_render_func(
                html,
                payload,
                return_url=True,
                options=options
                or {
                    "type": "png",
                    "full_page": True,
                    "omit_background": True,
                    "scale": "device",
                },
            )

            return image_url

        except Exception as e:
            self.logger.error(f"渲染失败: {e}")
            raise

    @abstractmethod
    def format_fallback_text(self, *args, **kwargs) -> str:
        """生成渲染失败时的纯文本回退.

        子类必须实现此方法，提供可读的文本格式。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            格式化的纯文本
        """
