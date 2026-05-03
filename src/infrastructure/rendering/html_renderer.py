"""HTML 渲染器 - 支持 Playwright 本地渲染和 AstrBot t2i 服务.

提供统一的 HTML 渲染接口，自动根据配置选择渲染方式：
1. Playwright 本地渲染（需要安装 playwright）
2. AstrBot 内置 t2i 服务渲染（无需额外依赖）
"""

from __future__ import annotations

import asyncio

from ..utils.logger import get_logger

logger = get_logger()


def check_playwright_installation() -> tuple[bool, str]:
    """检测 Playwright 是否已安装.

    Returns:
        (是否安装, 提示信息)
    """
    try:
        import playwright  # noqa: F401

        return True, "Playwright 已安装"
    except ImportError:
        return False, (
            "⚠️ 未检测到 Playwright，图片渲染功能将使用 AstrBot 内置 t2i 服务。\n"
            "如需使用 Playwright 渲染（效果更好），请安装：\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )


class DeerPipeHTMLRenderer:
    """DeerPipe HTML 渲染器.

    支持两种渲染方式：
    1. Playwright 本地渲染（需要安装 playwright）
    2. AstrBot 内置 t2i 服务渲染（无需额外依赖）
    """

    def __init__(self, use_t2i: bool = True, jpeg_quality: int = 95):
        """初始化 HTML 渲染器.

        Args:
            use_t2i: 是否使用 t2i 服务。True 使用 AstrBot t2i，False 使用 Playwright
            jpeg_quality: JPEG 图片质量 (1-100)，仅对 Playwright 生效
        """
        self.use_t2i = use_t2i
        self.jpeg_quality = jpeg_quality

        # Playwright 浏览器实例（延迟初始化）
        self._browser = None
        self._playwright = None
        self._lock = asyncio.Lock()

        # 检测 Playwright 安装状态并记录日志
        if not use_t2i:
            installed, msg = check_playwright_installation()
            if not installed:
                logger.warning(msg)

    async def close(self):
        """关闭浏览器资源."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _get_browser(self):
        """获取或创建 Playwright 浏览器实例."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch()
            except ImportError as e:
                raise RuntimeError(
                    "Playwright 未安装，请运行：\n"
                    "  pip install playwright\n"
                    "  playwright install chromium"
                ) from e
        return self._browser

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

        Args:
            html: HTML 模板字符串
            payload: Jinja2 模板数据
            return_url: 是否返回 URL
            options: 渲染选项

        Returns:
            图片 URL 或文件路径
        """
        if self.use_t2i:
            return await self._render_with_t2i(html, payload, return_url, options)
        return await self._render_with_playwright(html, payload, options)

    async def _render_with_t2i(
        self,
        html: str,
        payload: dict,
        return_url: bool = True,
        options: dict | None = None,
    ) -> str:
        """使用 AstrBot t2i 服务渲染."""
        try:
            from astrbot.core import html_renderer as t2i_renderer

            return await t2i_renderer.render_custom_template(
                html,
                payload,
                return_url=return_url,
                options=options,
            )
        except Exception as e:
            # t2i 失败时自动回退到 Playwright
            logger.warning(f"t2i 渲染失败，回退到 Playwright: {e}")
            return await self._render_with_playwright(html, payload, options)

    async def _render_with_playwright(
        self,
        html: str,
        payload: dict,
        options: dict | None = None,
    ) -> str:
        """使用 Playwright 本地渲染."""
        try:
            from jinja2 import Template
        except ImportError:
            raise RuntimeError(
                "Playwright 渲染需要 jinja2，请安装: pip install jinja2"
            )

        # 使用 Jinja2 渲染模板
        template = Template(html)
        html_content = template.render(**payload)

        async with self._lock:
            browser = await self._get_browser()
            page = await browser.new_page()

            try:
                await page.set_content(html_content, wait_until="networkidle")
                await page.wait_for_timeout(500)

                # 获取主容器尺寸（优先使用容器元素，避免 body 宽度不准确）
                dimensions = await page.evaluate("""() => {
                    const container = document.querySelector('.container, .leaderboard-container, .heatmap-container, .batch-container');
                    if (container) {
                        const rect = container.getBoundingClientRect();
                        return { width: Math.ceil(rect.width), height: Math.ceil(rect.height) };
                    }
                    // 回退到 body 尺寸
                    return {
                        width: document.body.scrollWidth,
                        height: document.body.scrollHeight
                    };
                }""")
                page_width = dimensions['width']
                page_height = dimensions['height']
                await page.set_viewport_size(
                    {"width": page_width, "height": page_height}
                )

                # 截图选项
                screenshot_type = (options or {}).get("type", "png")
                full_page = (options or {}).get("full_page", True)

                if screenshot_type == "jpeg":
                    screenshot_bytes = await page.screenshot(
                        type="jpeg",
                        quality=self.jpeg_quality,
                        full_page=full_page,
                    )
                else:
                    screenshot_bytes = await page.screenshot(
                        type="png",
                        full_page=full_page,
                    )

                # 保存到临时文件
                import tempfile

                suffix = ".jpeg" if screenshot_type == "jpeg" else ".png"
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix, prefix="deerpipe_"
                ) as f:
                    f.write(screenshot_bytes)
                    return f.name

            finally:
                await page.close()


# 单例实例
_renderer_instance: DeerPipeHTMLRenderer | None = None


def get_html_renderer(use_t2i: bool = True, jpeg_quality: int = 95) -> DeerPipeHTMLRenderer:
    """获取 HTML 渲染器单例.

    Args:
        use_t2i: 是否使用 t2i 服务
        jpeg_quality: JPEG 质量

    Returns:
        DeerPipeHTMLRenderer 实例
    """
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = DeerPipeHTMLRenderer(use_t2i, jpeg_quality)
    return _renderer_instance


def reset_html_renderer() -> None:
    """重置渲染器单例（用于测试）."""
    global _renderer_instance
    _renderer_instance = None
