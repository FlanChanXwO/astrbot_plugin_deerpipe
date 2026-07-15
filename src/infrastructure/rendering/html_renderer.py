"""HTML 渲染器 - 使用 AstrBot 内置 t2i 服务渲染图片.

渲染策略：
1. 使用 AstrBot 内置 t2i 服务渲染 HTML 为图片
2. 支持配置单次渲染超时时间
3. 每次请求独立调用 t2i，失败不会阻断后续渲染
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path

from ..utils.http_utils import _get_aiohttp_session
from ...domain.exceptions import RenderError


class DeerPipeHTMLRenderer:
    """DeerPipe HTML 渲染器.

    使用 AstrBot 内置 t2i 服务渲染 HTML 为图片。
    单次失败不会产生跨请求状态，后续请求仍会重新调用 t2i。
    """

    def __init__(
        self,
        render_timeout: int = 30,
        data_dir: Path | None = None,
    ) -> None:
        """初始化 HTML 渲染器.

        Args:
            render_timeout: 渲染超时时间（秒），默认 30 秒
            data_dir: 插件数据目录，用于保存临时图片
        """
        self.render_timeout = render_timeout

        self._data_dir = data_dir or (Path.cwd() / "data")
        self._temp_dir = self._data_dir / "temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    def _get_temp_suffix(self, options: dict | None) -> str:
        image_type = (options or {}).get("type", "png")
        return ".jpeg" if image_type == "jpeg" else ".png"

    def _write_temp_file(self, data: bytes, suffix: str) -> str:
        filename = f"deerpipe_{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
        temp_path = self._temp_dir / filename
        temp_path.write_bytes(data)
        return str(temp_path)

    async def _download_to_temp(self, url: str, suffix: str) -> str:
        session = await _get_aiohttp_session()
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
        return self._write_temp_file(data, suffix)

    def is_temp_file(self, file_path: str) -> bool:
        try:
            return Path(file_path).resolve().is_relative_to(self._temp_dir.resolve())
        except (OSError, ValueError):
            return False

    async def cleanup_temp_file(self, file_path: str, delay_seconds: int = 0) -> None:
        if not file_path or not self.is_temp_file(file_path):
            return
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            pass

    def schedule_temp_cleanup(self, file_path: str, delay_seconds: int = 60) -> None:
        try:
            asyncio.create_task(self.cleanup_temp_file(file_path, delay_seconds))
        except RuntimeError:
            pass

    async def close(self):
        """清理资源（t2i 无需显式关闭）."""
        pass

    async def __call__(
        self,
        html: str,
        payload: dict,
        return_url: bool = True,
        options: dict | None = None,
    ) -> str:
        """使实例可直接调用，委托给 render 方法."""
        return await self.render(html, payload, return_url, options)

    async def render(
        self,
        html: str,
        payload: dict,
        return_url: bool = True,
        options: dict | None = None,
    ) -> str:
        """渲染 HTML 为图片.

        使用 AstrBot 内置 t2i 服务渲染。每次调用互相独立，失败不会阻断
        后续请求。

        Args:
            html: HTML 模板字符串
            payload: Jinja2 模板数据
            return_url: 是否返回 URL
            options: 渲染选项

        Returns:
            图片 URL 或文件路径

        Raises:
            RenderError: t2i 渲染超时或返回了不支持的数据类型
            Exception: 模板渲染、t2i 调用或图片下载的底层异常会原样传播
        """
        try:
            return await asyncio.wait_for(
                self._render_with_t2i(html, payload, return_url, options),
                timeout=self.render_timeout,
            )
        except asyncio.TimeoutError:
            raise RenderError(
                f"t2i 渲染超时（{self.render_timeout}秒），请检查 t2i 服务状态"
            )

    async def _render_with_t2i(
        self,
        html: str,
        payload: dict,
        return_url: bool = True,
        options: dict | None = None,
    ) -> str:
        """使用 AstrBot t2i 服务渲染.

        使用 return_url=True 获取 t2i URL，然后下载到插件本地 temp 目录。
        """
        from astrbot.core import html_renderer as t2i_renderer
        from jinja2 import Template

        # 本地先渲染 Jinja2 模板，避免远程服务端处理大 payload 时截断
        template = Template(html)
        html_content = template.render(**payload)

        # 调用 t2i，优先拿 URL
        image_data = await t2i_renderer.render_custom_template(
            html_content,
            {},
            return_url=True,
            options=options,
        )

        suffix = self._get_temp_suffix(options)
        if isinstance(image_data, bytes):
            return self._write_temp_file(image_data, suffix)
        if isinstance(image_data, str):
            if image_data.startswith("http"):
                return await self._download_to_temp(image_data, suffix)
            if os.path.exists(image_data):
                temp_path = self._write_temp_file(Path(image_data).read_bytes(), suffix)
                try:
                    Path(image_data).unlink(missing_ok=True)
                except OSError:
                    pass
                return temp_path
            return image_data

        raise RenderError(f"t2i 返回了不支持的类型: {type(image_data)}")


# 单例实例
_renderer_instance: DeerPipeHTMLRenderer | None = None


def get_html_renderer(
    render_timeout: int = 30,
    data_dir: Path | None = None,
) -> DeerPipeHTMLRenderer:
    """获取 HTML 渲染器单例.

    Args:
        render_timeout: 渲染超时时间（秒）
        data_dir: 插件数据目录

    Returns:
        DeerPipeHTMLRenderer 实例
    """
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = DeerPipeHTMLRenderer(
            render_timeout=render_timeout,
            data_dir=data_dir,
        )
    return _renderer_instance


def reset_html_renderer() -> None:
    """重置渲染器单例（用于测试）."""
    global _renderer_instance
    _renderer_instance = None
