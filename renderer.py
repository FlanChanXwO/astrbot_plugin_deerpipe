"""Deer-pipe plugin calendar renderer.

日历图片渲染模块，负责构建 HTML 模板数据并调用渲染服务。
"""

from __future__ import annotations

import base64
import calendar
from pathlib import Path
from typing import Literal

from astrbot.api import logger

from .models import CalendarAssets, CalendarDay, CalendarPayload


class CalendarRenderer:
    """日历渲染器.

    负责构建日历 HTML 模板数据并调用 AstrBot 的 html_render 服务。
    """

    # 字体文件大小限制: 1MB (避免 HTTP 422 payload too large)
    MAX_FONT_SIZE = 1 * 1024 * 1024

    def __init__(self, base_dir: Path) -> None:
        """初始化日历渲染器.

        Args:
            base_dir: 插件根目录
        """
        self.base_dir = base_dir
        self.template_path = base_dir / "templates" / "calendar.html"
        self.css_path = base_dir / "templates" / "res" / "css" / "calendar.css"
        self.images_dir = base_dir / "templates" / "res" / "images"
        self.font_path = (
            base_dir / "templates" / "res" / "font" / "ADLaMDisplay-Regular.ttf"
        )

    def _get_image_data_uri(self, image_name: str) -> str:
        """获取图片的 base64 data URI.

        Args:
            image_name: 图片文件名

        Returns:
            base64 data URI 或空字符串
        """
        from .utils import image_to_data_uri

        image_path = self.images_dir / image_name
        return image_to_data_uri(image_path)

    def _build_calendar_data(
        self, month_map: dict[int, int], year: int, month: int
    ) -> list[list[CalendarDay]]:
        """构建日历数据结构.

        Args:
            month_map: 日期到打卡次数的映射
            year: 年份
            month: 月份

        Returns:
            按周分组的日历数据
        """
        cal = calendar.Calendar(firstweekday=0)
        weeks: list[list[CalendarDay]] = []

        for week in cal.monthdayscalendar(year, month):
            # 跳过完全为空的周（比如月初之前的周）
            if all(day == 0 for day in week):
                continue
            week_data: list[CalendarDay] = []
            for day in week:
                week_data.append(
                    {
                        "day_of_month": day,
                        "count": month_map.get(day, 0) if day else 0,
                    }
                )
            weeks.append(week_data)

        return weeks

    def _get_font_for_embedding(self) -> Path | None:
        """获取适合嵌入的字体文件路径.

        Returns:
            字体文件路径，或 None 如果没有可用字体
        """
        if self.font_path.exists():
            size = self.font_path.stat().st_size
            if size < self.MAX_FONT_SIZE:
                return self.font_path
            logger.warning(
                f"字体过大 ({size / 1024 / 1024:.2f}MB > "
                f"{self.MAX_FONT_SIZE / 1024 / 1024:.2f}MB)，跳过嵌入"
            )
        return None

    def _get_font_data_uri(self, font_path: Path | None = None) -> str:
        """获取字体文件的 base64 data URI.

        Args:
            font_path: 字体文件路径，如果为 None 则自动选择

        Returns:
            base64 data URI 或空字符串
        """
        if font_path is None:
            font_path = self._get_font_for_embedding()

        if not font_path or not font_path.exists():
            return ""

        try:
            data = font_path.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            ext = font_path.suffix.lower()
            mime = "font/ttf" if ext == ".ttf" else "font/otf"
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.error(f"读取字体文件失败: {e}")
            return ""

    def _inline_fonts_in_css(self, css: str) -> str:
        """将 CSS 中的字体相对路径替换为 base64 data URI.

        Args:
            css: 原始 CSS 内容

        Returns:
            处理后的 CSS 内容
        """
        if not self.font_path.exists():
            return css

        # 检查字体大小限制
        if self.font_path.stat().st_size >= self.MAX_FONT_SIZE:
            logger.warning(f"字体过大，跳过嵌入: {self.font_path.name}")
            return css

        try:
            data_uri = self._get_font_data_uri(self.font_path)
            if data_uri:
                # 替换相对路径为 data URI
                # CSS 中使用的是相对路径如: url('../font/ADLaMDisplay-Regular.ttf')
                rel_path = f"url('../font/{self.font_path.name}')"
                css = css.replace(rel_path, f"url('{data_uri}')")
        except Exception as e:
            logger.warning(f"内嵌字体失败: {e}")

        return css

    def _get_character_image(self, total_count: int, user_id: str) -> str:
        """根据打卡次数和用户ID确定性地选择角色图片.

        参考Java实现的分组逻辑:
        - count >= 50: character_9~11
        - count >= 20: character_5~8
        - 其他: character_1~4

        使用user_id哈希确保同一用户同月渲染结果稳定。

        Args:
            total_count: 当月总打卡次数
            user_id: 用户ID，用于确定性选择

        Returns:
            角色图片的 base64 data URI
        """
        # 根据打卡次数确定范围
        if total_count >= 50:
            # 高阶: character_9.png ~ character_11.png
            start, end = 9, 11
        elif total_count >= 20:
            # 中阶: character_5.png ~ character_8.png
            start, end = 5, 8
        else:
            # 初阶: character_1.png ~ character_4.png
            start, end = 1, 4

        # 使用user_id哈希确定性地选择索引
        hash_value = hash(f"{user_id}:{total_count}")
        index = start + (abs(hash_value) % (end - start + 1))

        return self._get_image_data_uri(f"character_{index}.png")

    def _load_assets(
        self, user_id: str, month_map: dict[int, int] | None = None
    ) -> CalendarAssets:
        """加载日历所需的图片资源.

        Args:
            user_id: 用户ID，用于确定性选择角色图片
            month_map: 日期到打卡次数的映射，用于确定角色图片

        Returns:
            图片资源字典
        """
        # 计算总打卡次数，用于选择角色图片
        total_count = sum(month_map.values()) if month_map else 0

        return {
            "character": self._get_character_image(total_count, user_id),
            "deer_pipe": self._get_image_data_uri("deerpipe.png"),
            "check": self._get_image_data_uri("check.png"),
            "undeer_pipe": self._get_image_data_uri("undeerpipe.png"),
        }

    async def build_payload(
        self,
        user_id: str,
        year: int,
        month: int,
        month_map: dict[int, int],
        count_display_mode: Literal["additive", "count"] = "additive",
        show_check_mark: bool = True,
    ) -> CalendarPayload:
        """构建日历渲染所需的完整数据负载.

        该方法会读取 CSS 文件内容并包装在 <style> 标签中，
        同时获取用户头像和所需图片资源，最终组装成渲染所需的数据结构。

        Args:
            user_id: 用户 ID (用于获取头像)
            year: 年份
            month: 月份
            month_map: 日期到打卡次数的映射
            count_display_mode: 打卡次数显示模式
            show_check_mark: 是否显示打勾图标

        Returns:
            日历渲染数据负载
        """
        from .models import CalendarPayload
        from .utils import fetch_avatar_base64

        # 读取 CSS 并处理字体嵌入
        css_content = ""
        if self.css_path.exists():
            raw_css = self.css_path.read_text(encoding="utf-8")
            # 将 CSS 中的字体相对路径替换为 base64 data URI
            processed_css = self._inline_fonts_in_css(raw_css)
            css_content = f"<style>{processed_css}</style>"

        # 验证并规范化 count_display_mode
        if count_display_mode not in ("additive", "count"):
            logger.warning(f"Invalid count_display_mode: {count_display_mode}, using 'additive'")
            count_display_mode = "additive"
        calendar_weeks = self._build_calendar_data(month_map, year, month)

        # 获取用户头像
        avatar_b64 = await fetch_avatar_base64(user_id)

        # 加载图片资源（根据打卡次数选择角色图片）
        assets = self._load_assets(user_id, month_map)

        return CalendarPayload(
            css_style=css_content,
            year=year,
            month=month,
            calendar=calendar_weeks,
            avatar_base64=avatar_b64,
            assets=assets,
            count_display_mode=count_display_mode,
            show_check_mark=show_check_mark,
        )

    async def render(
        self,
        html_render_func,
        user_id: str,
        year: int,
        month: int,
        month_map: dict[int, int],
        count_display_mode: Literal["additive", "count"] = "additive",
        show_check_mark: bool = True,
    ) -> str:
        """渲染日历图片.

        Args:
            html_render_func: AstrBot 的 html_render 方法
            user_id: 用户 ID
            year: 年份
            month: 月份
            month_map: 日期到打卡次数的映射
            count_display_mode: 打卡次数显示模式
            show_check_mark: 是否显示打勾图标

        Returns:
            渲染后的图片 URL

        Raises:
            FileNotFoundError: 模板文件不存在
            Exception: 渲染失败
        """
        if not self.template_path.exists():
            raise FileNotFoundError(f"日历模板不存在: {self.template_path}")

        # 读取 HTML 模板
        html = self.template_path.read_text(encoding="utf-8")

        # 构建数据负载
        payload = await self.build_payload(
            user_id, year, month, month_map, count_display_mode, show_check_mark
        )

        # 转换为字典 (html_render 需要字典格式)
        payload_dict = {
            "css_style": payload.css_style,
            "year": payload.year,
            "month": payload.month,
            "calendar": payload.calendar,
            "avatar_base64": payload.avatar_base64,
            "assets": payload.assets,
            "count_display_mode": payload.count_display_mode,
            "show_check_mark": payload.show_check_mark,
        }

        # 调用渲染服务
        image_url = await html_render_func(
            html,
            payload_dict,
            return_url=True,
            options={
                "type": "png",
                "full_page": True,
                "scale": "device",
            },
        )

        return image_url

    def format_fallback_text(
        self, year: int, month: int, month_map: dict[int, int]
    ) -> str:
        """生成渲染失败时的纯文本日历.

        Args:
            year: 年份
            month: 月份
            month_map: 日期到打卡次数的映射

        Returns:
            格式化的纯文本日历 (包含日历表格和统计信息)
        """
        total = sum(month_map.values())
        days_recorded = len(month_map)

        # 构建日历表头
        header = f"📅 {year}年{month}月 鹿历"
        separator = "=" * 28

        # 星期标题
        weekday_header = " 日   一   二   三   四   五   六 "

        # 构建日历主体
        cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
        lines: list[str] = []

        for week in cal.monthdayscalendar(year, month):
            week_strs: list[str] = []
            for day in week:
                if day == 0:
                    week_strs.append("    ")  # 空位
                elif day in month_map:
                    count = month_map[day]
                    # 有记录的日期显示次数
                    if count >= 10:
                        week_strs.append(f"{count:>3} ")
                    else:
                        week_strs.append(f" {count}  ")
                else:
                    week_strs.append(f"{day:>3} ")
            lines.append("".join(week_strs))

        calendar_body = "\n".join(lines)

        # 统计信息
        stats = f"📊 统计: 共{days_recorded}天 {total}次\n💡 带数字的日期为已打卡次数"

        return (
            f"{header}\n"
            f"{separator}\n"
            f"{weekday_header}\n"
            f"{calendar_body}\n"
            f"{separator}\n"
            f"{stats}"
        )
