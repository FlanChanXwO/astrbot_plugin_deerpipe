"""用 Playwright 截取帮助图到 assets/help.png。

依赖本机已安装 playwright chromium：
  python -m playwright install chromium
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_PNG = ROOT / "assets" / "help.png"

# 与 main.py 实际命令/别名保持一致
SECTIONS = [
    (
        "日常打卡",
        [
            ("/deer · 鹿 · 🦌 · 撸 · 撸🦌", "自己打卡；也可纯文本 鹿 / 🦌"),
            ("/deer @用户 · 🦌@用户 · 帮🦌@用户", "帮他人打卡；可 @ 多人出批量报告"),
            ("/补鹿 <日> · 补🦌 · 补撸", "补录当月指定日期，如 /补鹿 5"),
        ],
    ),
    (
        "查询统计",
        [
            ("/鹿历 · 🦌历 · 撸历", "本月打卡月历图"),
            ("/上月鹿历 · 上月🦌历", "上月打卡月历图"),
            ("/鹿历 2025 3 · 2025年3月鹿历", "指定年月月历（命令或纯文本）"),
            ("/鹿力图 [年] · 鹿年历 · 🦌力图", "年度打卡热力图"),
        ],
    ),
    (
        "隐私与管理",
        [
            ("/允许被鹿 · 允许被🦌", "允许他人帮自己打卡"),
            ("/禁止被鹿 · 禁止被🦌", "禁止他人帮自己打卡"),
            ("/设置被鹿 开|关 @用户", "管理员设置他人是否可被帮打"),
            ("/管理鹿管数据 导出|导入", "管理员 JSON 备份与恢复"),
        ],
    ),
    (
        "帮助",
        [
            (
                "/鹿帮助 · 🦌帮助 · 鹿菜单 · deer_help · deerhelp",
                "查看本帮助图（也可纯文本 鹿帮助）",
            ),
        ],
    ),
]


def _data_uri(path: Path) -> str:
    data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def build_html() -> str:
    char_uri = _data_uri(ROOT / "resources" / "images" / "character_1.png")
    pipe_uri = _data_uri(ROOT / "resources" / "images" / "deerpipe.png")

    rows: list[str] = []
    for title, items in SECTIONS:
        rows.append(f'<div class="section-title">{title}</div>')
        for cmd, desc in items:
            rows.append(
                f'<div class="list-row"><div class="cmd">{cmd}</div>'
                f'<div class="desc">{desc}</div></div>'
            )

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=1100, initial-scale=1.0" />
  <link href="https://fonts.googleapis.com/css2?family=ADLaM+Display&family=Nunito:wght@400;700;800&display=swap" rel="stylesheet">
  <style>
    html, body {{
      margin: 0; padding: 0; width: 1100px;
      background: transparent !important;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }}
    .card {{
      width: 1100px; background: #ffffff; overflow: hidden;
      position: relative; display: inline-block;
      font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    }}
    .header {{
      background: linear-gradient(180deg, #fffcf9 0%, #ffffff 100%);
      padding: 42px 50px 36px; border-bottom: 2px solid #f0f0f0;
      position: relative; overflow: hidden;
    }}
    .title {{
      font-size: 46px; font-weight: 800; color: #4e342e; letter-spacing: -0.5px;
      font-family: "ADLaM Display", "Microsoft YaHei", sans-serif; margin-bottom: 8px;
    }}
    .subtitle {{
      font-size: 20px; color: #a1887f; letter-spacing: 4px; font-weight: 700;
      text-transform: uppercase; font-family: "Nunito", "Microsoft YaHei", sans-serif;
    }}
    .header-deco {{
      position: absolute; right: 20px; top: -8px; width: 170px; height: 170px;
      opacity: 0.85; pointer-events: none;
    }}
    .header-deco img {{ width: 100%; height: 100%; object-fit: contain; }}
    .body {{ padding: 18px 50px 10px; background: #fff; position: relative; z-index: 1; }}
    .section-title {{
      display: inline-block; margin: 18px 0 8px; padding: 8px 16px; border-radius: 12px;
      background: #fff3e0; color: #e65100; font-size: 22px; font-weight: 800;
      border-left: 6px solid #ff5722;
    }}
    .list-row {{
      display: flex; justify-content: space-between; align-items: flex-start;
      gap: 24px; padding: 18px 0; border-bottom: 2px dashed #eee;
    }}
    .cmd {{
      flex: 1.35; font-size: 24px; color: #333; font-weight: 700;
      line-height: 1.45; word-break: break-word;
    }}
    .desc {{
      flex: 1; text-align: right; font-size: 22px; color: #757575;
      line-height: 1.45; font-weight: 600;
    }}
    .footer {{
      background: #fafafa; padding: 28px 50px; border-top: 2px solid #eeeeee;
      display: flex; justify-content: space-between; align-items: center;
    }}
    .footer-left {{ font-size: 20px; color: #999; font-weight: 600; }}
    .footer-right {{
      font-size: 20px; color: #a1887f; font-weight: 700; letter-spacing: 1px;
      font-family: "Nunito", "Microsoft YaHei", sans-serif;
    }}
    .pipe-deco {{
      position: absolute; right: 24px; bottom: 70px; width: 120px; height: 120px;
      opacity: 0.12; pointer-events: none; z-index: 0;
    }}
    .pipe-deco img {{ width: 100%; height: 100%; object-fit: contain; }}
  </style>
</head>
<body>
  <div class="card" id="capture">
    <div class="header">
      <div class="title">🦌 鹿乃子 · 使用帮助</div>
      <div class="subtitle">DEER PIPE HELP</div>
      <div class="header-deco"><img src="{char_uri}" alt="character"/></div>
    </div>
    <div class="body">
      {"".join(rows)}
      <div class="pipe-deco"><img src="{pipe_uri}" alt="pipe"/></div>
    </div>
    <div class="footer">
      <div class="footer-left">发送「鹿帮助」可再次查看 · 纯文本短命令同样有效</div>
      <div class="footer-right">DEER PIPE</div>
    </div>
  </div>
</body>
</html>
"""


async def render() -> None:
    html_path = ROOT / "assets" / "_help_preview.html"
    html_path.write_text(build_html(), encoding="utf-8")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                viewport={"width": 1100, "height": 1600},
                device_scale_factor=2,
            )
            await page.goto(html_path.as_uri(), wait_until="networkidle")
            await page.evaluate(
                """async () => {
                  if (document.fonts) {
                    try { await document.fonts.ready; } catch (e) {}
                    try {
                      await Promise.all([
                        document.fonts.load('1em "ADLaM Display"'),
                        document.fonts.load('700 1em "Nunito"'),
                        document.fonts.load('800 1em "Nunito"'),
                      ]);
                    } catch (e) {}
                  }
                }"""
            )
            await page.wait_for_timeout(400)
            await page.locator("#capture").screenshot(path=str(OUT_PNG), type="png")
            await browser.close()
    finally:
        html_path.unlink(missing_ok=True)
    print(f"saved {OUT_PNG} ({OUT_PNG.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(render())
