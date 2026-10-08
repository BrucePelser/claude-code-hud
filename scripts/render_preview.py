#!/usr/bin/env python3
"""Render real HUD output to assets/preview.svg for the README.

    python scripts/render_preview.py
"""
import os
import re
import sys
from xml.sax.saxutils import escape

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import hud  # noqa: E402
from icons import design  # noqa: E402

GLYPH_NAMES = {chr(cp): name for name, cp in design.CODEPOINTS.items()}
CELL_W, LINE_H, FONT = 9.0, 24, 15
PAD_X, PAD_TOP = 22, 20
BG, FG, MUTED = "#1b1d27", "#d6d9e5", "#6c7086"
FONT_STACK = "Cascadia Mono, Consolas, Menlo, DejaVu Sans Mono, monospace"
SGR = re.compile(r"\x1b\[([0-9;]*)m")


def xterm(code):
    if code < 16:
        base = ["#000000", "#cd3131", "#0dbc79", "#e5e510", "#2472c8", "#bc3fbc", "#11a8cd", "#e5e5e5",
                "#666666", "#f14c4c", "#23d18b", "#f5f543", "#3b8eea", "#d670d6", "#29b8db", "#ffffff"]
        return base[code]
    if code >= 232:
        v = 8 + (code - 232) * 10
        return "#%02x%02x%02x" % (v, v, v)
    code -= 16
    steps = [0, 95, 135, 175, 215, 255]
    return "#%02x%02x%02x" % (steps[code // 36], steps[(code // 6) % 6], steps[code % 6])


def cells(ch):
    return hud.vis_len(ch)


def icon_group(name, x, baseline, color):
    """Draw an icon where the font would put it: 0.9em tall, centred 0.35em above the baseline."""
    size = 0.9 * FONT
    top = baseline - 0.35 * FONT - size / 2
    return ('<g transform="translate(%.1f %.1f) scale(%.4f)" fill="none" stroke="%s" stroke-width="%g" '
            'stroke-linecap="round" stroke-linejoin="round" color="%s">%s</g>'
            % (x + 0.05 * FONT, top, size / 24.0, color, design.STROKE, color, design.svg_elements(name)))


def line_to_svg(text, y):
    """One terminal line to <text> elements, each glyph pinned to its own cell column."""
    out, col, color, bold = [], 0, FG, False
    run, run_x = [], []

    def flush():
        if run:
            out.append('<text x="%s" y="%d" fill="%s"%s>%s</text>' % (
                " ".join("%.1f" % x for x in run_x), y, color,
                ' font-weight="700"' if bold else "", escape("".join(run))))
            run.clear()
            run_x.clear()

    pos = 0
    for m in list(SGR.finditer(text)) + [None]:
        chunk = text[pos:m.start()] if m else text[pos:]
        for ch in chunk:
            x = PAD_X + col * CELL_W
            if ch == " ":
                flush()  # SVG collapses spaces and shifts the x list, so spaces are just column advances
                col += 1
                continue
            if ch in GLYPH_NAMES:
                flush()
                out.append(icon_group(GLYPH_NAMES[ch], x, y, color))
                col += 1
                continue
            if ord(ch) > 0xFFFF or cells(ch) == 2:
                flush()  # wide and astral glyphs get their own element
                out.append('<text x="%.1f" y="%d" fill="%s">%s</text>' % (x, y, color, escape(ch)))
            else:
                run.append(ch)
                run_x.append(x)
            col += cells(ch)
        flush()
        if not m:
            break
        codes = (m.group(1) or "0").split(";")
        if codes[0] == "0":
            color, bold = FG, False
        elif codes[0] == "1":
            bold = True
        elif codes[:2] == ["38", "5"]:
            color = xterm(int(codes[2]))
        pos = m.end()
    return "\n    ".join(out), col


def config(**over):
    cfg = hud.make_config(over)
    cfg["color"] = True
    return cfg


def frames():
    pressure_data = hud.demo_data()
    pressure_data["context_window"]["used_percentage"] = 91
    pressure_data["rate_limits"]["five_hour"]["used_percentage"] = 92
    pressure_data["rate_limits"]["seven_day"]["used_percentage"] = 88
    pressure_data["prompt_cache"] = {"warm": False, "caching_observed": True, "expires_at": None}
    pressure_state = dict(hud.DEMO_STATE, project={
        "name": "my-app", "git": {"branch": "feature/login", "dirty": False, "ahead": 0, "behind": 2,
                                   "repo": "acme/my-app"}})
    brain_state = dict(
        hud.DEMO_STATE,
        project={"name": "my-app", "git": {"branch": "main", "dirty": True, "ahead": 1, "behind": 0,
                                           "repo": "acme/my-app"}},
        brain_name={"name": "brain", "ok": True},
        brain={"files": ["plans/launch/plan.md", "reference/style-guide.md", "sessions/hud-notes-2026-10-07.md"]})
    return [
        ('icons "custom", brain_path set. Row 1: you. Row 2: limits. Row 3: the GitHub repo, the brain and its file.',
         hud.render(hud.demo_data(), config(icons="custom"), brain_state)),
        ("Same icons under pressure: context hint, hot limits, cold cache, month against a 160h target",
         hud.render(pressure_data, config(icons="custom", monthly_target_hours=160), pressure_state)),
        ('Without the icon font: "icons": "emoji" (the default)',
         hud.render(hud.demo_data(), config(), brain_state)),
        ('"icons": "plain", "layout": "compact" (two rows)',
         hud.render(hud.demo_data(), config(icons="plain", layout="compact"), brain_state)),
    ]


def main():
    body, y, max_cols = [], PAD_TOP, 0
    for caption, rendered in frames():
        y += 14
        body.append('<text x="%d" y="%d" fill="%s" font-size="12" font-family="system-ui, sans-serif">%s</text>'
                    % (PAD_X, y, MUTED, escape(caption)))
        y += 8
        for line in rendered.split("\n"):
            y += LINE_H
            svg, cols = line_to_svg(line, y)
            max_cols = max(max_cols, cols)
            body.append("<g>\n    %s\n  </g>" % svg)
        y += 18
    width = int(PAD_X * 2 + max_cols * CELL_W)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" '
           'aria-label="claude-code-hud preview: two status lines showing model, session time, git branch, context and rate limit bars">\n'
           '  <rect width="100%%" height="100%%" rx="10" fill="%s"/>\n'
           '  <g font-family="%s" font-size="%d" xml:space="preserve">\n  %s\n  </g>\n</svg>\n'
           % (width, y, width, y, BG, FONT_STACK, FONT, "\n  ".join(body)))
    out = os.path.join(ROOT, "assets", "preview.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", os.path.normpath(out), "(%dx%d)" % (width, y))


if __name__ == "__main__":
    main()
