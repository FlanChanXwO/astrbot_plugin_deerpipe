"""Rendering layer.

渲染相关实现，提供纯技术的模板渲染能力。
"""

from .html_renderer import DeerPipeHTMLRenderer, get_html_renderer, reset_html_renderer
from .template_renderer import TemplateRenderer

__all__ = [
    "DeerPipeHTMLRenderer",
    "TemplateRenderer",
    "get_html_renderer",
    "reset_html_renderer",
]
