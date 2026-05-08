from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeliveryWarning:
    code: str
    error: str


@dataclass
class ToolResult:
    """LLM工具结果数据类."""

    success: bool = False
    user_id: str | None = None
    date: str | None = None
    target_date: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    calendar: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)
    user_settings: dict[str, Any] = field(default_factory=dict)
    note: str | None = None
    message: str | None = None
    error: str | None = None
    reasons: list[Any] = field(default_factory=list)
    result: list[Any] = field(default_factory=list)
    delivery_warning: str | None = None
    delivery_error: str | None = None
    delivery_warnings: list[DeliveryWarning] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResult:
        warnings_raw = data.get("delivery_warnings", [])
        warnings: list[DeliveryWarning] = []
        if isinstance(warnings_raw, list):
            for item in warnings_raw:
                if not isinstance(item, dict):
                    continue
                code = item.get("code")
                error = item.get("error")
                if isinstance(code, str) and isinstance(error, str):
                    warnings.append(DeliveryWarning(code=code, error=error))

        known_keys = {
            "success",
            "user_id",
            "date",
            "target_date",
            "stats",
            "calendar",
            "analysis",
            "user_settings",
            "note",
            "message",
            "error",
            "reasons",
            "result",
            "delivery_warning",
            "delivery_error",
            "delivery_warnings",
        }

        extra = {k: v for k, v in data.items() if k not in known_keys}

        return cls(
            success=bool(data.get("success", False)),
            user_id=data.get("user_id")
            if isinstance(data.get("user_id"), str)
            else None,
            date=data.get("date") if isinstance(data.get("date"), str) else None,
            target_date=(
                data.get("target_date")
                if isinstance(data.get("target_date"), str)
                else None
            ),
            stats=data.get("stats") if isinstance(data.get("stats"), dict) else {},
            calendar=(
                data.get("calendar") if isinstance(data.get("calendar"), dict) else {}
            ),
            analysis=(
                data.get("analysis") if isinstance(data.get("analysis"), dict) else {}
            ),
            user_settings=(
                data.get("user_settings")
                if isinstance(data.get("user_settings"), dict)
                else {}
            ),
            note=data.get("note") if isinstance(data.get("note"), str) else None,
            message=(
                data.get("message") if isinstance(data.get("message"), str) else None
            ),
            error=data.get("error") if isinstance(data.get("error"), str) else None,
            reasons=data.get("reasons")
            if isinstance(data.get("reasons"), list)
            else [],
            result=data.get("result") if isinstance(data.get("result"), list) else [],
            delivery_warning=(
                data.get("delivery_warning")
                if isinstance(data.get("delivery_warning"), str)
                else None
            ),
            delivery_error=(
                data.get("delivery_error")
                if isinstance(data.get("delivery_error"), str)
                else None
            ),
            delivery_warnings=warnings,
            extra=extra,
        )

    def append_delivery_warning(self, warning_code: str, exc: Exception) -> None:
        error_text = str(exc)
        if self.delivery_warning is None:
            self.delivery_warning = warning_code
        if self.delivery_error is None:
            self.delivery_error = error_text
        self.delivery_warnings.append(
            DeliveryWarning(code=warning_code, error=error_text)
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "success": self.success,
        }
        if self.user_id is not None:
            data["user_id"] = self.user_id
        if self.date is not None:
            data["date"] = self.date
        if self.target_date is not None:
            data["target_date"] = self.target_date
        if self.stats:
            data["stats"] = self.stats
        if self.calendar:
            data["calendar"] = self.calendar
        if self.analysis:
            data["analysis"] = self.analysis
        if self.user_settings:
            data["user_settings"] = self.user_settings
        if self.note is not None:
            data["note"] = self.note
        if self.message is not None:
            data["message"] = self.message
        if self.error is not None:
            data["error"] = self.error
        if self.reasons:
            data["reasons"] = self.reasons
        if self.result:
            data["result"] = self.result
        if self.delivery_warning is not None:
            data["delivery_warning"] = self.delivery_warning
        if self.delivery_error is not None:
            data["delivery_error"] = self.delivery_error
        if self.delivery_warnings:
            data["delivery_warnings"] = [
                {"code": w.code, "error": w.error} for w in self.delivery_warnings
            ]
        data.update(self.extra)
        return data
