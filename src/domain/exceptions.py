"""DeerPipe 插件异常类.

集中管理插件中所有自定义异常类型.
"""

from __future__ import annotations


class TemplateKeyError(KeyError):
    """模板键缺失错误.

    当请求的消息模板键不存在或缺少必需的格式化参数时抛出.

    Attributes:
        message: 错误描述信息
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class DeerPipeError(Exception):
    """DeerPipe 插件基础异常类.

    所有插件特定异常的基类.

    Attributes:
        message: 错误描述信息
        error_code: 错误代码，用于程序识别
    """

    def __init__(self, message: str, error_code: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class DatabaseError(DeerPipeError):
    """数据库操作错误.

    当数据库操作失败时抛出.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="DB_ERROR")


class ValidationError(DeerPipeError):
    """数据验证错误.

    当输入数据验证失败时抛出.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="VALIDATION_ERROR")


class RateLimitError(DeerPipeError):
    """速率限制错误.

    当操作超出频率限制时抛出（如补打卡次数超限）.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message, error_code="RATE_LIMIT")
        self.retry_after = retry_after


class PermissionError(DeerPipeError):
    """权限错误.

    当用户没有权限执行某操作时抛出.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="PERMISSION_DENIED")


class ConfigurationError(DeerPipeError):
    """配置错误.

    当插件配置不正确时抛出.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="CONFIG_ERROR")


class RenderError(DeerPipeError):
    """渲染错误.

    当日历或图片渲染失败时抛出.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="RENDER_ERROR")


class DataImportError(DeerPipeError):
    """数据导入错误.

    当数据导入失败时抛出.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="IMPORT_ERROR")


class DataExportError(DeerPipeError):
    """数据导出错误.

    当数据导出失败时抛出.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="EXPORT_ERROR")
