"""HTML 渲染器行为回归测试。"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import re
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


def _seed_package(
    monkeypatch: pytest.MonkeyPatch, name: str, package_path: Path
) -> None:
    """注册最小包结构，避免单元测试加载完整 AstrBot 运行环境。"""
    package = types.ModuleType(name)
    package.__path__ = [str(package_path)]
    monkeypatch.setitem(sys.modules, name, package)


def _load_module(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    file_path: Path,
):
    """按真实包名加载模块，使相对导入保持与生产环境一致。"""
    spec = importlib.util.spec_from_file_location(name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载测试模块: {file_path}")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _load_renderer_module(
    monkeypatch: pytest.MonkeyPatch,
    render_custom_template,
):
    """只替换 AstrBot t2i 与 HTTP 两个外部边界，加载真实渲染器。"""
    src_dir = PROJECT_ROOT / "src"
    infrastructure_dir = src_dir / "infrastructure"

    _seed_package(monkeypatch, "src", src_dir)
    _seed_package(monkeypatch, "src.domain", src_dir / "domain")
    _seed_package(monkeypatch, "src.infrastructure", infrastructure_dir)
    _seed_package(
        monkeypatch,
        "src.infrastructure.rendering",
        infrastructure_dir / "rendering",
    )
    _seed_package(
        monkeypatch,
        "src.infrastructure.utils",
        infrastructure_dir / "utils",
    )

    http_utils = types.ModuleType("src.infrastructure.utils.http_utils")

    async def unexpected_http_session():
        raise AssertionError("字节响应不应触发 HTTP 下载")

    http_utils._get_aiohttp_session = unexpected_http_session
    monkeypatch.setitem(sys.modules, "src.infrastructure.utils.http_utils", http_utils)

    astrbot = types.ModuleType("astrbot")
    astrbot.__path__ = []
    astrbot_core = types.ModuleType("astrbot.core")
    astrbot_core.html_renderer = types.SimpleNamespace(
        render_custom_template=render_custom_template
    )
    astrbot.core = astrbot_core
    monkeypatch.setitem(sys.modules, "astrbot", astrbot)
    monkeypatch.setitem(sys.modules, "astrbot.core", astrbot_core)

    _load_module(
        monkeypatch,
        "src.domain.exceptions",
        src_dir / "domain" / "exceptions.py",
    )
    return _load_module(
        monkeypatch,
        "src.infrastructure.rendering.html_renderer",
        infrastructure_dir / "rendering" / "html_renderer.py",
    )


@pytest.mark.asyncio
async def test_renderer_recovers_when_t2i_succeeds_after_repeated_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """历史失败不得阻止服务恢复后的下一次真实 t2i 调用。"""
    call_count = 0

    async def render_custom_template(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise RuntimeError("临时网络故障")
        return b"rendered-image"

    renderer_module = _load_renderer_module(monkeypatch, render_custom_template)
    renderer = renderer_module.DeerPipeHTMLRenderer(
        render_timeout=1,
        data_dir=tmp_path,
    )

    for _ in range(3):
        with pytest.raises(RuntimeError, match="临时网络故障"):
            await renderer.render("<p>{{ text }}</p>", {"text": "鹿"})

    image_path = await renderer.render("<p>{{ text }}</p>", {"text": "鹿"})

    assert call_count == 4
    assert Path(image_path).read_bytes() == b"rendered-image"


@pytest.mark.asyncio
async def test_legacy_disabled_state_is_ignored_and_left_untouched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """升级后不得读取、覆盖或删除旧版渲染器状态文件。"""
    legacy_state = tmp_path / "renderer_state.json"
    original_content = '{"t2i_failures": 3, "t2i_disabled": true}'
    legacy_state.write_text(original_content, encoding="utf-8")

    async def render_custom_template(*args, **kwargs):
        return b"rendered-image"

    renderer_module = _load_renderer_module(monkeypatch, render_custom_template)
    renderer = renderer_module.DeerPipeHTMLRenderer(
        render_timeout=1,
        data_dir=tmp_path,
    )

    image_path = await renderer.render("<p>鹿</p>", {})

    assert Path(image_path).read_bytes() == b"rendered-image"
    assert legacy_state.read_text(encoding="utf-8") == original_content


def test_renderer_public_api_has_no_legacy_engine_switches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """公开接口只保留真实生效的 t2i 渲染参数。"""

    async def render_custom_template(*args, **kwargs):
        return b"rendered-image"

    renderer_module = _load_renderer_module(monkeypatch, render_custom_template)

    constructor_parameters = inspect.signature(
        renderer_module.DeerPipeHTMLRenderer
    ).parameters
    factory_parameters = inspect.signature(renderer_module.get_html_renderer).parameters

    assert "use_t2i" not in constructor_parameters
    assert "jpeg_quality" not in constructor_parameters
    assert "use_t2i" not in factory_parameters
    assert "jpeg_quality" not in factory_parameters

    renderer = renderer_module.DeerPipeHTMLRenderer(data_dir=tmp_path)
    assert not hasattr(renderer, "use_t2i")
    assert not hasattr(renderer, "jpeg_quality")


def test_renderer_public_api_has_no_disabled_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """禁用状态、失败计数和人工重置接口必须整体退出。"""

    async def render_custom_template(*args, **kwargs):
        return b"rendered-image"

    renderer_module = _load_renderer_module(monkeypatch, render_custom_template)
    exceptions_module = sys.modules["src.domain.exceptions"]
    renderer = renderer_module.DeerPipeHTMLRenderer(data_dir=tmp_path)

    assert not hasattr(renderer, "t2i_disabled")
    assert not hasattr(renderer, "t2i_failures")
    assert not hasattr(renderer, "reset_t2i_state")
    assert not hasattr(exceptions_module, "RendererDisabledError")


def test_plugin_has_no_playwright_runtime_dependency() -> None:
    """插件生产代码和依赖清单均不得依赖本地 Playwright。"""
    imported_roots: set[str] = set()
    production_files = [
        PROJECT_ROOT / "main.py",
        *sorted((PROJECT_ROOT / "src").rglob("*.py")),
    ]

    for file_path in production_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

    requirement_names = {
        re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip().lower()
        for line in (PROJECT_ROOT / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "playwright" not in imported_roots
    assert "playwright" not in requirement_names
