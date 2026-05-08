"""HTML 渲染器 - 优先使用 t2i，失败时回退到 Playwright.

渲染策略：
1. 优先使用 AstrBot 内置 t2i 服务（远程渲染，无需本地依赖）
2. t2i 连续失败3次后自动禁用，切换到 Playwright 为主
3. 支持配置渲染超时时间
4. 状态持久化，AstrBot 重启后仍保留
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

from ..utils.http_utils import _get_aiohttp_session
from ..utils.logger import get_logger

logger = get_logger()

# t2i 连续失败阈值，达到此值后禁用 t2i
T2I_MAX_FAILURES = 3
# 状态文件保存间隔（秒），避免频繁写入
STATE_SAVE_INTERVAL = 5


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
            "⚠️ 未检测到 Playwright，如 t2i 渲染失败将无法回退到本地渲染。\n"
            "建议安装以确保渲染稳定性：\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )


class T2IStateManager:
    """t2i 状态管理器 - 持久化记录失败次数和禁用状态."""

    def __init__(self, data_dir: Path | None = None):
        """初始化状态管理器.

        Args:
            data_dir: 插件数据目录，用于保存状态文件
        """
        if data_dir is None:
            # 默认使用插件数据目录
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path

            data_dir = (
                Path(get_astrbot_data_path())
                / "plugin_data"
                / "astrbot_plugin_deerpipe"
            )

        self.data_dir = data_dir
        self.state_file = data_dir / "renderer_state.json"
        self._state: dict = {}
        self._last_save = 0
        self._load_state()

    def _load_state(self) -> None:
        """从文件加载状态."""
        try:
            if self.state_file.exists():
                self._state = json.loads(self.state_file.read_text(encoding="utf-8"))
            else:
                self._state = {
                    "t2i_failures": 0,
                    "t2i_disabled": False,
                    "last_failure_time": None,
                }
        except Exception:
            self._state = {
                "t2i_failures": 0,
                "t2i_disabled": False,
                "last_failure_time": None,
            }

    def _save_state(self) -> None:
        """保存状态到文件（带间隔限制）."""
        now = time.time()
        if now - self._last_save < STATE_SAVE_INTERVAL:
            return

        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._last_save = now
        except Exception:
            pass

    @property
    def t2i_disabled(self) -> bool:
        """检查 t2i 是否已被禁用."""
        return self._state.get("t2i_disabled", False)

    @property
    def t2i_failures(self) -> int:
        """获取当前连续失败次数."""
        return self._state.get("t2i_failures", 0)

    def record_t2i_failure(self) -> bool:
        """记录一次 t2i 失败.

        Returns:
            是否达到阈值被禁用
        """
        self._state["t2i_failures"] = self.t2i_failures + 1
        self._state["last_failure_time"] = time.time()

        if self._state["t2i_failures"] >= T2I_MAX_FAILURES:
            self._state["t2i_disabled"] = True
            logger.warning(f"t2i 已连续失败 {T2I_MAX_FAILURES} 次，已自动禁用")
            self._save_state()
            return True

        self._save_state()
        return False

    def record_t2i_success(self) -> None:
        """记录一次 t2i 成功，重置失败计数."""
        if self._state["t2i_failures"] > 0 or self._state["t2i_disabled"]:
            self._state["t2i_failures"] = 0
            self._state["t2i_disabled"] = False
            self._state["last_failure_time"] = None
            self._save_state()

    def reset(self) -> None:
        """手动重置状态（用户通过命令或配置更改后调用）."""
        self._state = {
            "t2i_failures": 0,
            "t2i_disabled": False,
            "last_failure_time": None,
        }
        self._save_state()


class DeerPipeHTMLRenderer:
    """DeerPipe HTML 渲染器.

    渲染策略：
    1. 根据 use_t2i 配置决定优先使用 t2i 还是 Playwright
    2. t2i 连续失败3次后自动禁用，切换到 Playwright
    3. 支持通过 timeout 参数控制渲染超时
    4. 状态持久化，AstrBot 重启后仍保留禁用状态
    """

    def __init__(
        self,
        render_timeout: int = 30,
        jpeg_quality: int = 95,
        data_dir: Path | None = None,
        use_t2i: bool = False,
    ):
        """初始化 HTML 渲染器.

        Args:
            render_timeout: 渲染超时时间（秒），默认 30 秒
            jpeg_quality: JPEG 图片质量 (1-100)，仅对 Playwright 生效
            data_dir: 插件数据目录，用于保存状态
            use_t2i: 是否优先使用 t2i 服务（默认 False，使用 Playwright）
        """
        self.render_timeout = render_timeout
        self.jpeg_quality = jpeg_quality
        self.use_t2i = use_t2i

        self._data_dir = data_dir or (Path.cwd() / "data")
        self._temp_dir = self._data_dir / "temp"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        # t2i 状态管理器
        self._state_manager = T2IStateManager(data_dir)

        # Playwright 浏览器实例（延迟初始化，仅在需要时创建）
        self._browser = None
        self._playwright = None
        self._lock = asyncio.Lock()

    @property
    def t2i_disabled(self) -> bool:
        """检查 t2i 是否已被禁用."""
        return self._state_manager.t2i_disabled

    @property
    def t2i_failures(self) -> int:
        """获取 t2i 当前连续失败次数."""
        return self._state_manager.t2i_failures

    def reset_t2i_state(self) -> None:
        """手动重置 t2i 状态（用户修复 t2i 服务后调用）."""
        self._state_manager.reset()

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
                    "Playwright 未安装，无法回退到本地渲染。请运行：\n"
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

        根据 use_t2i 配置决定渲染策略：
        - use_t2i=True: 优先使用 t2i，失败时回退到 Playwright
        - use_t2i=False: 仅使用 Playwright

        Args:
            html: HTML 模板字符串
            payload: Jinja2 模板数据
            return_url: 是否返回 URL
            options: 渲染选项

        Returns:
            图片 URL 或文件路径
        """
        # 根据配置决定渲染策略
        if self.use_t2i and not self.t2i_disabled:
            # 第1策略：尝试 t2i（带超时）
            try:
                result = await asyncio.wait_for(
                    self._render_with_t2i(html, payload, return_url, options),
                    timeout=self.render_timeout,
                )
                # 成功，重置失败计数
                self._state_manager.record_t2i_success()
                return result
            except asyncio.TimeoutError:
                logger.warning(
                    f"t2i 渲染超时（{self.render_timeout}秒），回退到 Playwright"
                )
                self._state_manager.record_t2i_failure()
            except Exception as e:
                # 仅记录异常类型和简短描述，避免 base64 污染日志
                logger.warning(f"t2i 渲染失败 ({type(e).__name__})，回退到 Playwright")
                self._state_manager.record_t2i_failure()
        elif not self.use_t2i:
            logger.debug("use_t2i=False，使用 Playwright 渲染")
        else:
            logger.warning("t2i 已被禁用，回退到 Playwright")

        # 第2策略：回退到 Playwright
        return await self._render_with_playwright(html, payload, options)

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

        raise RuntimeError(f"t2i 返回了不支持的类型: {type(image_data)}")

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
            raise RuntimeError("Playwright 渲染需要 jinja2，请安装: pip install jinja2")

        # 使用 Jinja2 渲染模板
        template = Template(html)
        html_content = template.render(**payload)

        async with self._lock:
            browser = await self._get_browser()
            page = await browser.new_page()

            try:
                await page.set_content(html_content, wait_until="networkidle")

                # 等待字体加载完成（通过检查 data-fonts-loaded 属性）
                try:
                    await page.wait_for_selector(
                        "html[data-fonts-loaded='true']", timeout=5000, state="attached"
                    )
                except Exception:
                    pass

                # 额外等待确保渲染稳定
                await page.wait_for_timeout(300)

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
                page_width = dimensions["width"]
                page_height = dimensions["height"]
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

                suffix = ".jpeg" if screenshot_type == "jpeg" else ".png"
                return self._write_temp_file(screenshot_bytes, suffix)

            finally:
                await page.close()


# 单例实例
_renderer_instance: DeerPipeHTMLRenderer | None = None


def get_html_renderer(
    render_timeout: int = 30,
    jpeg_quality: int = 95,
    data_dir: Path | None = None,
    use_t2i: bool = False,
) -> DeerPipeHTMLRenderer:
    """获取 HTML 渲染器单例.

    Args:
        render_timeout: 渲染超时时间（秒）
        jpeg_quality: JPEG 质量
        data_dir: 插件数据目录
        use_t2i: 是否优先使用 t2i 服务

    Returns:
        DeerPipeHTMLRenderer 实例
    """
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = DeerPipeHTMLRenderer(
            render_timeout, jpeg_quality, data_dir, use_t2i
        )
    return _renderer_instance


def reset_html_renderer() -> None:
    """重置渲染器单例（用于测试）."""
    global _renderer_instance
    _renderer_instance = None
