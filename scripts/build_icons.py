#!/usr/bin/env python3
"""Rebuild the icon files from icons/design.py. Needs: pip install fonttools shapely

    python scripts/build_icons.py

Writes icons/svg/*.svg, assets/icons.svg (the overview sheet) and fonts/ClaudeHudIcons.ttf.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from icons import design  # noqa: E402

BG, LABEL = "#1b1d27", "#9aa0b8"
# Colours the HUD gives each icon when the custom set is on (xterm 256 -> hex, see render_preview)
SHEET_COLOURS = {
    "model": "#af87ff", "active": "#5fd7d7", "open": "#5fd7d7", "today": "#5fd7d7", "month": "#5fd7d7",
    "cost": "#ffd787", "folder": "#87afd7", "branch": "#87d787", "note": "#d7af5f", "book": "#d7af5f",
    "context": "#87d787", "cache_warm": "#ff8700", "cache_cold": "#5fafff", "reset": "#8a8a8a",
}


def sheet():
    names = list(design.ICONS)
    cols, cell_w, cell_h, size = 7, 110, 104, 44
    rows = -(-len(names) // cols)
    width, height = cols * cell_w + 20, rows * cell_h + 20
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" '
           'aria-label="The 14 icons used by claude-code-hud">' % (width, height, width, height),
           '<rect width="100%%" height="100%%" rx="10" fill="%s"/>' % BG]
    for i, name in enumerate(names):
        x = 10 + (i % cols) * cell_w + (cell_w - size) / 2
        y = 18 + (i // cols) * cell_h
        out.append('<g transform="translate(%g %g) scale(%g)" fill="none" stroke="%s" stroke-width="%g" '
                   'stroke-linecap="round" stroke-linejoin="round" color="%s">%s</g>'
                   % (x, y, size / 24.0, SHEET_COLOURS[name], design.STROKE, SHEET_COLOURS[name],
                      design.svg_elements(name)))
        out.append('<text x="%g" y="%d" fill="%s" font-family="system-ui, sans-serif" font-size="12" '
                   'text-anchor="middle">%s</text>' % (10 + (i % cols) * cell_w + cell_w / 2, y + size + 20, LABEL,
                                                       name.replace("_", " ")))
    out.append("</svg>\n")
    return "\n".join(out)


def main():
    svg_dir = os.path.join(ROOT, "icons", "svg")
    os.makedirs(svg_dir, exist_ok=True)
    for name in design.ICONS:
        with open(os.path.join(svg_dir, name + ".svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(design.svg_file(name))
    with open(os.path.join(ROOT, "assets", "icons.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(sheet())
    os.makedirs(os.path.join(ROOT, "fonts"), exist_ok=True)
    font_path = os.path.join(ROOT, "fonts", "ClaudeHudIcons.ttf")
    design.build_font(font_path)
    print("wrote %d icons, assets/icons.svg, %s (%d bytes)" % (len(design.ICONS), os.path.normpath(font_path),
                                                              os.path.getsize(font_path)))


if __name__ == "__main__":
    main()
