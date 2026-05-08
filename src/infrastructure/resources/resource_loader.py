"""Resource loader.

资源加载器，负责加载和管理静态资源文件。
"""

from __future__ import annotations

from pathlib import Path

from ..utils.http_utils import image_to_data_uri
from ..utils.logger import get_logger

logger = get_logger()


class ResourceLoader:
    """资源加载器.

    负责加载图片、模板、CSS等静态资源。
    """

    def __init__(self, base_dir: Path) -> None:
        """初始化资源加载器.

        Args:
            base_dir: 插件根目录
        """
        self.base_dir = base_dir
        self.logger = logger

        # 获取资源路径
        from ...shared import ResourcePaths

        self.paths = ResourcePaths(base_dir)
        self.images_dir = self.paths.images_dir()

    def load_image_as_data_uri(self, image_name: str) -> str:
        """加载图片并转换为 base64 data URI.

        Args:
            image_name: 图片文件名

        Returns:
            base64 data URI 或空字符串
        """
        image_path = self.images_dir / image_name
        return image_to_data_uri(image_path)

    def load_template(self, template_name: str) -> str:
        """加载HTML模板.

        Args:
            template_name: 模板文件名（不含扩展名）

        Returns:
            HTML模板字符串

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        template_path = self.paths.template(template_name)

        if not template_path.exists():
            raise FileNotFoundError(f"模板不存在: {template_path}")

        return template_path.read_text(encoding="utf-8")

    def load_css(self, css_name: str | None) -> str:
        """加载CSS并包装在<style>标签中.

        Args:
            css_name: CSS文件名（不含扩展名），None 表示不加载

        Returns:
            CSS字符串（已包装在style标签中）或空字符串
        """
        if css_name is None:
            return ""

        css_path = self.paths.style(css_name)

        if not css_path.exists():
            self.logger.warning(f"CSS文件不存在: {css_path}")
            return ""

        raw_css = css_path.read_text(encoding="utf-8")
        return f"<style>{raw_css}</style>"
