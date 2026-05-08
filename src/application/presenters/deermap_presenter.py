"""Deermap presenter.

鹿力图展示器，负责协调领域服务和基础设施。
"""

from __future__ import annotations

import base64
from pathlib import Path

from ...domain.services import DeermapDataBuilder
from ...infrastructure import (
    ResourceLoader,
    TemplateRenderer,
    get_cached_avatar,
    get_logger,
)

logger = get_logger()


class DeermapPresenter:
    """鹿力图展示器.

    负责组装鹿力图展示所需的数据并调用渲染。
    """

    def __init__(
        self,
        resource_loader: ResourceLoader,
        template_renderer: TemplateRenderer,
        base_dir: Path,
    ) -> None:
        """初始化鹿力图展示器.

        Args:
            resource_loader: 资源加载器
            template_renderer: 模板渲染器
            base_dir: 插件根目录
        """
        self.resource_loader = resource_loader
        self.template_renderer = template_renderer
        self.base_dir = base_dir
        self.data_builder = DeermapDataBuilder()
        self.logger = logger

    async def present_deermap(
        self,
        html_render_func,
        stats_data: dict[str, int],
        year: int,
        user_id: str,
        platform_name: str | None = None,
    ) -> str:
        """展示鹿力图图片.

        协调流程：
        1. 使用 domain service 构建业务数据
        2. 使用 infrastructure 加载资源
        3. 使用 infrastructure 渲染模板

        Args:
            html_render_func: HTML渲染函数
            stats_data: 日期到打卡次数的映射
            year: 年份
            user_id: 用户ID
            platform_name: 平台名称

        Returns:
            渲染后的图片URL
        """
        # 1. 加载模板和CSS
        html = self.resource_loader.load_template("deermap")
        css_content = self.resource_loader.load_css("deermap")

        # 2. 使用 domain service 构建业务数据
        weeks_data, months, week_to_month = self.data_builder.build_heatmap_data(
            stats_data, year
        )
        total_days, total_count, max_count, avg_count = (
            self.data_builder.calculate_statistics(stats_data)
        )

        # 3. 加载资源
        avatar_b64 = await get_cached_avatar(user_id, platform_name)
        shot_b64 = self._load_shot_image()

        # 4. 组装渲染数据
        payload = {
            "css_style": css_content,
            "title": f"{year}年鹿力图",
            "year": year,
            "months": months,
            "week_to_month": week_to_month,
            "weeks": weeks_data,
            "total_days": total_days,
            "total_count": total_count,
            "max_count": max_count,
            "avg_count": avg_count,
            "avatar_base64": avatar_b64,
            "shot_image": shot_b64,
        }

        # 5. 调用渲染器
        return await self.template_renderer.render(html, payload, html_render_func)

    def _load_shot_image(self) -> str:
        """加载shot图片并转换为base64.

        Returns:
            base64 data URI 或空字符串
        """
        shot_path = self.base_dir / "resources" / "images" / "shot.png"
        if not shot_path.exists():
            return ""

        return (
            "data:image/png;base64,"
            + base64.b64encode(shot_path.read_bytes()).decode()
        )

    def format_fallback_text(
        self,
        stats_data: dict[str, int],
        year: int,
    ) -> str:
        """格式化鹿力图文本.

        Args:
            stats_data: 日期到打卡次数的映射
            year: 年份

        Returns:
            格式化的文本
        """
        # 使用 domain service 计算统计信息
        total_days, total_count, max_count, _ = self.data_builder.calculate_statistics(
            stats_data
        )

        lines = [
            f"{year}年鹿力图",
            "",
            "统计信息:",
            f"  鹿天数: {total_days}天",
            f"  总鹿次数: {total_count}次",
            f"  单日最多: {max_count}次",
        ]

        return "\n".join(lines)
