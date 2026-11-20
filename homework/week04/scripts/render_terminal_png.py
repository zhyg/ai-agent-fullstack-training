#!/usr/bin/env python3
"""将真实终端运行日志渲染为高清深色终端风格 PNG 截图（支持中英文等宽对齐）。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

FONT_CANDIDATES: List[Tuple[str, int]] = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 7),  # Noto Sans Mono CJK SC
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),  # Noto Sans CJK SC
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
]

BOLD_CANDIDATES: List[Tuple[str, int]] = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 7),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
]


def load_font(candidates: List[Tuple[str, int]], size: int) -> ImageFont.FreeTypeFont:
    for path_str, index in candidates:
        if Path(path_str).exists():
            try:
                return ImageFont.truetype(path_str, size=size, index=index)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_line(line: str, max_cols: int = 104) -> List[str]:
    if not line:
        return [""]
    out: List[str] = []
    cur: List[str] = []
    width = 0
    for ch in line:
        w = 2 if ord(ch) > 127 else 1
        if width + w > max_cols and cur:
            out.append("".join(cur))
            cur = [ch]
            width = w
        else:
            cur.append(ch)
            width += w
    if cur:
        out.append("".join(cur))
    return out


def line_color(line: str) -> Tuple[int, int, int]:
    stripped = line.strip()
    if stripped.startswith("===="):
        return (98, 174, 239)
    if stripped.startswith("---") or stripped.startswith("【"):
        return (229, 192, 123)
    if stripped.startswith("$ ") or stripped.startswith("[实测执行]"):
        return (152, 195, 121)
    if "PASS" in stripped or "EXISTS" in stripped or "WRITE OK" in stripped or "UPDATE OK" in stripped or "DELETE OK" in stripped:
        return (152, 195, 121)
    if "MISSING" in stripped or "FAIL" in stripped or "WARN" in stripped:
        return (224, 108, 117)
    if stripped.startswith("[") and "]" in stripped[:6]:
        return (86, 182, 194)
    return (220, 223, 228)


def render_png(title: str, command: str, text: str, output: Path) -> None:
    clean = ANSI_RE.sub("", text).replace("\t", "    ")
    for emoji, repl in (("✅", "[OK]"), ("⚠️", "[WARN]"), ("⚠", "[WARN]"), ("❌", "[FAIL]"), ("→", "->")):
        clean = clean.replace(emoji, repl)
    raw_lines = [f"$ {command}", ""] + clean.splitlines()
    lines: List[str] = []
    for raw in raw_lines:
        lines.extend(wrap_line(raw, max_cols=108))

    font_size = 18
    line_height = 28
    pad_x = 28
    pad_y = 22
    header_h = 46

    font = load_font(FONT_CANDIDATES, font_size)
    bold_font = load_font(BOLD_CANDIDATES or FONT_CANDIDATES, 17)

    # 计算实际画布尺寸
    probe = Image.new("RGB", (10, 10))
    probe_draw = ImageDraw.Draw(probe)
    max_text_w = max((probe_draw.textlength(ln, font=font) for ln in lines), default=600)
    width = int(max(1080, min(1680, max_text_w + pad_x * 2 + 20)))
    height = header_h + pad_y * 2 + len(lines) * line_height + 10

    img = Image.new("RGB", (width, height), (24, 28, 36))
    draw = ImageDraw.Draw(img)

    # 顶部标题栏
    draw.rectangle([(0, 0), (width, header_h)], fill=(33, 38, 48))
    draw.line([(0, header_h), (width, header_h)], fill=(52, 60, 74), width=1)
    # 终端三色圆点
    for idx, color in enumerate([(237, 106, 94), (244, 191, 79), (97, 197, 84)]):
        cx = 22 + idx * 22
        cy = header_h // 2
        draw.ellipse([(cx - 6, cy - 6), (cx + 6, cy + 6)], fill=color)

    title_w = draw.textlength(title, font=bold_font)
    draw.text(((width - title_w) / 2, (header_h - 20) / 2), title, font=bold_font, fill=(195, 203, 216))

    # 绘制终端正文
    y = header_h + pad_y
    for ln in lines:
        draw.text((pad_x, y), ln, font=font, fill=line_color(ln))
        y += line_height

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG")


def main() -> int:
    parser = argparse.ArgumentParser(description="将终端日志渲染为 PNG 截图")
    parser.add_argument("--title", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    render_png(args.title, args.command, text, args.output)
    print(f"Rendered screenshot: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
