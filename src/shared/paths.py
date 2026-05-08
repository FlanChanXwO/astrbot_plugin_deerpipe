"""路径管理器.

集中管理插件内各资源路径，便于统一维护和扩展.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResourcePaths:
    """资源路径管理器."""

    base_dir: Path

    def template(self, name: str) -> Path:
        """获取模板文件路径."""
        return self.base_dir / "templates" / name / "index.html"

    def style(self, name: str) -> Path:
        """获取样式文件路径."""
        return self.base_dir / "templates" / name / "style.css"

    def font(self, filename: str) -> Path:
        """获取字体文件路径."""
        return self.base_dir / "resources" / "font" / filename

    def image(self, filename: str) -> Path:
        """获取图片文件路径."""
        return self.base_dir / "resources" / "images" / filename

    def images_dir(self) -> Path:
        """获取图片目录路径."""
        return self.base_dir / "resources" / "images"

    def template_dir(self, name: str) -> Path:
        """获取模板目录路径."""
        return self.base_dir / "templates" / name
