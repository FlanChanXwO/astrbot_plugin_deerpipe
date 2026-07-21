"""Tests for HelpCommandHandler static image delivery and dedup."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parent.parent
CMD_PATH = ROOT / "src" / "application" / "commands" / "help_cmd.py"
CONST_PATH = ROOT / "src" / "shared" / "constants.py"


def _load_help_command_handler():
    """Load HelpCommandHandler without importing the full application package."""
    pkg = "deerpipe_help_test"
    modules = {
        pkg: types.ModuleType(pkg),
        f"{pkg}.application": types.ModuleType(f"{pkg}.application"),
        f"{pkg}.application.commands": types.ModuleType(f"{pkg}.application.commands"),
        f"{pkg}.infrastructure": types.ModuleType(f"{pkg}.infrastructure"),
        f"{pkg}.infrastructure.utils": types.ModuleType(f"{pkg}.infrastructure.utils"),
        f"{pkg}.infrastructure.utils.logger": types.ModuleType(
            f"{pkg}.infrastructure.utils.logger"
        ),
        f"{pkg}.shared": types.ModuleType(f"{pkg}.shared"),
        f"{pkg}.shared.constants": types.ModuleType(f"{pkg}.shared.constants"),
    }
    modules[pkg].__path__ = []
    modules[f"{pkg}.application"].__path__ = []
    modules[f"{pkg}.application.commands"].__path__ = [str(CMD_PATH.parent)]
    modules[f"{pkg}.infrastructure"].__path__ = []
    modules[f"{pkg}.infrastructure.utils"].__path__ = []
    modules[f"{pkg}.shared"].__path__ = []

    modules[f"{pkg}.infrastructure.utils.logger"].get_logger = lambda: SimpleNamespace(
        error=lambda *args, **kwargs: None
    )

    # Minimal constants needed by help_cmd
    const_src = CONST_PATH.read_text(encoding="utf-8")
    # exec just EVENT_DEDUP_HELP via reading the file symbols
    namespace: dict = {"__name__": f"{pkg}.shared.constants", "Final": str}
    # Provide typing.Final for the constants module
    import typing

    namespace["Final"] = typing.Final
    namespace["Literal"] = typing.Literal
    exec(compile(const_src, str(CONST_PATH), "exec"), namespace)
    modules[f"{pkg}.shared.constants"].EVENT_DEDUP_HELP = namespace["EVENT_DEDUP_HELP"]

    for name, mod in modules.items():
        sys.modules[name] = mod

    spec = importlib.util.spec_from_file_location(
        f"{pkg}.application.commands.help_cmd",
        CMD_PATH,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = f"{pkg}.application.commands"
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.HelpCommandHandler, namespace["EVENT_DEDUP_HELP"]


HelpCommandHandler, EVENT_DEDUP_HELP = _load_help_command_handler()


class _FakeEvent:
    def __init__(self) -> None:
        self.image_calls: list[str] = []
        self.plain_calls: list[str] = []
        self.extras: dict = {}
        self.stopped = False

    def image_result(self, path: str):
        self.image_calls.append(path)
        return SimpleNamespace(kind="image", path=path)

    def plain_result(self, text: str):
        self.plain_calls.append(text)
        return SimpleNamespace(kind="plain", text=text)

    def get_extra(self, key: str | None = None, default=None):
        if key is None:
            return self.extras
        return self.extras.get(key, default)

    def set_extra(self, key, value) -> None:
        self.extras[key] = value

    def stop_event(self) -> None:
        self.stopped = True


def test_handle_help_sends_image_when_file_exists(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    help_png = assets / "help.png"
    help_png.write_bytes(b"fake-png")

    handler = HelpCommandHandler(tmp_path)
    event = _FakeEvent()

    results = asyncio.run(_collect(handler.handle_help(event)))

    assert len(results) == 1
    assert event.image_calls == [str(help_png.resolve())]
    assert event.plain_calls == []
    assert event.stopped is True
    assert event.extras.get(EVENT_DEDUP_HELP) is True


def test_handle_help_falls_back_to_text_when_missing(tmp_path: Path) -> None:
    handler = HelpCommandHandler(tmp_path)
    event = _FakeEvent()

    results = asyncio.run(_collect(handler.handle_help(event)))

    assert len(results) == 1
    assert event.image_calls == []
    assert event.plain_calls
    assert "缺失" in event.plain_calls[0]
    assert event.stopped is True


def test_handle_help_is_idempotent_on_same_event(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "help.png").write_bytes(b"fake-png")

    handler = HelpCommandHandler(tmp_path)
    event = _FakeEvent()

    first = asyncio.run(_collect(handler.handle_help(event)))
    second = asyncio.run(_collect(handler.handle_help(event)))

    assert len(first) == 1
    assert second == []
    assert len(event.image_calls) == 1


async def _collect(agen):
    return [item async for item in agen]
