"""Tests for plain-message command trigger patterns."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.constants import (  # noqa: E402
    PLAIN_CALENDAR_TRIGGER_PATTERN,
    PLAIN_DEER_TRIGGER_PATTERN,
    PLAIN_HELP_TRIGGER_PATTERN,
)


def test_plain_deer_trigger_accepts_short_commands() -> None:
    pattern = re.compile(PLAIN_DEER_TRIGGER_PATTERN)

    for text in (
        "鹿",
        "🦌",
        "撸",
        "撸🦌",
        "🦌 @用户",
        "🦌@用户",
        "鹿@用户",
        "帮🦌 @用户",
        "帮🦌@用户",
        "帮鹿 @用户",
        "撸🦌@用户",
    ):
        assert pattern.match(text), text


def test_plain_deer_trigger_rejects_normal_text() -> None:
    pattern = re.compile(PLAIN_DEER_TRIGGER_PATTERN)

    for text in (
        "鹿乃子月历",
        "鹿历",
        "今天鹿一下",
        "我想看鹿乃子",
        "/鹿",
        "鹿帮助",
        "鹿 帮助",
        "鹿菜单",
        "鹿 菜单",
    ):
        assert not pattern.match(text), text


def test_plain_calendar_trigger_accepts_calendar_queries() -> None:
    pattern = re.compile(PLAIN_CALENDAR_TRIGGER_PATTERN)

    for text in ("鹿历", "🦌历", "上月鹿历", "2025年3月鹿历"):
        assert pattern.match(text), text


def test_plain_help_trigger_accepts_help_commands() -> None:
    pattern = re.compile(PLAIN_HELP_TRIGGER_PATTERN)

    for text in (
        "鹿帮助",
        "🦌帮助",
        "鹿菜单",
        "鹿 帮助",
        "🦌 帮助",
        "鹿 菜单",
        "deer help",
        "deerhelp",
        "deer_help",
        "Deer_help",
        "DEERHELP",
        "Deer help",
    ):
        assert pattern.match(text), text


def test_plain_help_trigger_rejects_other_text() -> None:
    pattern = re.compile(PLAIN_HELP_TRIGGER_PATTERN)

    for text in ("/鹿帮助", "鹿", "帮鹿", "查看鹿帮助一下", "deer-help"):
        assert not pattern.match(text), text
