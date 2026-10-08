"""The claude-code-hud icon set: one drawing, three outputs.

Every icon is a list of primitives on a 24x24 grid (y down, 2 unit round stroke).
The same drawing becomes standalone SVG files, inline SVG for the README preview, and
the glyphs of fonts/ClaudeHudIcons.ttf, so the icons a terminal shows are the SVGs.

Building the font needs fonttools and shapely. Importing this module does not.
Run it through scripts/build_icons.py.
"""
import math

STROKE = 2.0
FIRST_CODEPOINT = 0xE900  # private use area, clear of the Nerd Fonts ranges


def star(cx, cy, r, inner=0.36):
    """Four-point sparkle."""
    pts = []
    for i in range(8):
        ang = math.radians(-90 + i * 45)
        rad = r if i % 2 == 0 else r * inner
        pts.append((round(cx + rad * math.cos(ang), 2), round(cy + rad * math.sin(ang), 2)))
    return pts


def snowflake(cx, cy, r):
    prims = []
    for deg in (0, 60, 120):
        a = math.radians(deg)
        dx, dy = r * math.cos(a), r * math.sin(a)
        prims.append(("line", [(cx - dx, cy - dy), (cx + dx, cy + dy)]))
    for deg in range(0, 360, 60):
        a = math.radians(deg)
        ux, uy = math.cos(a), math.sin(a)
        bx, by = cx + 0.58 * r * ux, cy + 0.58 * r * uy
        for turn in (-55, 55):
            t = math.radians(deg + turn)
            prims.append(("line", [(bx, by), (bx + 0.34 * r * math.cos(t), by + 0.34 * r * math.sin(t))]))
    return [("line", [tuple(round(v, 2) for v in p) for p in prim[1]]) for prim in prims]


CALENDAR_FRAME = [
    ("rect", 3, 5, 18, 16, 2.5),
    ("line", [(3, 10), (21, 10)]),
    ("line", [(8, 2.8), (8, 6.8)]),
    ("line", [(16, 2.8), (16, 6.8)]),
]

# Order fixes the code points: U+E900 + position.
ICONS = {
    "model": [("solid", star(10.5, 13.5, 8.5), 1.4), ("solid", star(18.6, 5.4, 3.6), 1.0)],
    "active": [("line", [(2, 12), (7, 12), (10, 4.5), (14, 19.5), (17, 12), (22, 12)])],
    "open": [("circle", 12, 12, 9), ("line", [(12, 6.5), (12, 12), (16, 14.5)])],
    "today": CALENDAR_FRAME + [("dot", 12, 15.6, 2.0)],
    "month": CALENDAR_FRAME + [("dot", x, y, 1.25) for y in (13.8, 17.8) for x in (8, 12, 16)],
    "cost": [
        ("bez", [(15.8, 8.6), (15.8, 6.6), (14, 5.8), (12, 5.8), (10, 5.8), (8.3, 6.9), (8.3, 8.7),
                 (8.3, 10.6), (10, 11.3), (12, 12), (14, 12.7), (15.8, 13.4), (15.8, 15.3),
                 (15.8, 17.1), (14, 18.2), (12, 18.2), (10, 18.2), (8.2, 17.3), (8.2, 15.4)], False),
        ("line", [(12, 3.2), (12, 5.8)]),
        ("line", [(12, 18.2), (12, 20.8)]),
    ],
    "folder": [("poly", [(3, 6), (9, 6), (11.4, 8.8), (21, 8.8), (21, 19), (3, 19)])],
    "branch": [
        ("circle", 6, 5, 2.2),
        ("circle", 6, 19, 2.2),
        ("circle", 18, 7, 2.2),
        ("line", [(6, 7.2), (6, 16.8)]),
        ("bez", [(18, 9.2), (18, 14.5), (6, 11), (6, 14.5)], False),
    ],
    "note": [
        ("poly", [(6, 3), (14, 3), (19, 8), (19, 21), (6, 21)]),
        ("line", [(14, 3), (14, 8), (19, 8)]),
        ("line", [(9.5, 13), (15.5, 13)]),
        ("line", [(9.5, 17), (15.5, 17)]),
    ],
    "book": [
        ("bez", [(12, 6.2), (10, 4.4), (6.5, 4), (3, 4.6), (3, 9.2), (3, 13.8), (3, 18.4),
                 (6.5, 17.9), (10, 18.3), (12, 20)], False),
        ("bez", [(12, 6.2), (14, 4.4), (17.5, 4), (21, 4.6), (21, 9.2), (21, 13.8), (21, 18.4),
                 (17.5, 17.9), (14, 18.3), (12, 20)], False),
        ("line", [(12, 6.2), (12, 20)]),
    ],
    "context": (
        [("rect", 6, 6, 12, 12, 1.8)]
        + [("line", [(x, 2.6), (x, 6)]) for x in (9.5, 14.5)]
        + [("line", [(x, 18), (x, 21.4)]) for x in (9.5, 14.5)]
        + [("line", [(2.6, y), (6, y)]) for y in (9.5, 14.5)]
        + [("line", [(18, y), (21.4, y)]) for y in (9.5, 14.5)]
    ),
    "cache_warm": [
        ("bez", [(12, 2.6), (7.6, 7.2), (5.6, 10.6), (5.6, 14.6), (5.6, 18.6), (8.4, 21.4), (12, 21.4),
                 (15.6, 21.4), (18.4, 18.6), (18.4, 14.6), (18.4, 12), (17.4, 10.2), (16.2, 8.6),
                 (15.4, 11.2), (14, 12), (12.8, 12), (12.8, 8.8), (12.4, 5.6), (12, 2.6)], True),
    ],
    "cache_cold": snowflake(12, 12, 9.2),
    "reset": [
        ("line", [(5.5, 3), (18.5, 3)]),
        ("line", [(5.5, 21), (18.5, 21)]),
        ("line", [(7.5, 3), (7.5, 6.8), (12, 12), (7.5, 17.2), (7.5, 21)]),
        ("line", [(16.5, 3), (16.5, 6.8), (12, 12), (16.5, 17.2), (16.5, 21)]),
    ],
}

CODEPOINTS = {name: FIRST_CODEPOINT + i for i, name in enumerate(ICONS)}


# ---------------------------------------------------------------- SVG output

def _pts(points):
    return " ".join("%g,%g" % p for p in points)


def _bez_d(points, closed):
    d = "M%g %g" % points[0]
    for i in range(1, len(points), 3):
        d += " C" + " ".join("%g %g" % p for p in points[i:i + 3])
    return d + (" Z" if closed else "")


def svg_elements(name):
    """Inner SVG markup for one icon. The caller supplies stroke, fill and colour."""
    out = []
    for prim in ICONS[name]:
        kind = prim[0]
        if kind == "line":
            out.append('<polyline points="%s"/>' % _pts(prim[1]))
        elif kind == "poly":
            out.append('<polygon points="%s"/>' % _pts(prim[1]))
        elif kind == "circle":
            out.append('<circle cx="%g" cy="%g" r="%g"/>' % prim[1:4])
        elif kind == "rect":
            out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%g"/>' % prim[1:6])
        elif kind == "dot":
            out.append('<circle cx="%g" cy="%g" r="%g" fill="currentColor" stroke="none"/>' % prim[1:4])
        elif kind == "solid":
            out.append('<polygon points="%s" fill="currentColor" stroke-width="%g"/>' % (_pts(prim[1]), prim[2]))
        elif kind == "bez":
            out.append('<path d="%s"/>' % _bez_d(prim[1], prim[2]))
    return "".join(out)


def svg_file(name, size=24, color="currentColor"):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 24 24" fill="none" '
        'stroke="%s" stroke-width="%g" stroke-linecap="round" stroke-linejoin="round" color="%s">'
        '<title>%s</title>%s</svg>\n' % (size, size, color, STROKE, color, name, svg_elements(name)))


# ---------------------------------------------------------------- outlines for the font

def _flatten_bez(points, closed, steps=18):
    out = [points[0]]
    for i in range(1, len(points), 3):
        p0, p1, p2, p3 = points[i - 1], points[i], points[i + 1], points[i + 2]
        for s in range(1, steps + 1):
            t = s / steps
            u = 1 - t
            out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                        u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    if closed:
        out.append(out[0])
    return out


def geometry(name):
    """One shapely shape per icon: strokes widened to STROKE, solids filled."""
    from shapely.geometry import LineString, Point, Polygon, box
    from shapely.ops import unary_union

    half = STROKE / 2
    parts = []

    def stroke(points):
        return LineString(points).buffer(half, cap_style=1, join_style=1, resolution=12)

    for prim in ICONS[name]:
        kind = prim[0]
        if kind == "line":
            parts.append(stroke(prim[1]))
        elif kind == "poly":
            parts.append(stroke(list(prim[1]) + [prim[1][0]]))
        elif kind == "circle":
            cx, cy, r = prim[1:4]
            parts.append(Point(cx, cy).buffer(r + half, resolution=24).difference(Point(cx, cy).buffer(r - half, resolution=24)))
        elif kind == "rect":
            x, y, w, h, r = prim[1:6]
            ring = box(x + r, y + r, x + w - r, y + h - r).buffer(r, resolution=12).exterior
            parts.append(stroke(list(ring.coords)))
        elif kind == "dot":
            parts.append(Point(prim[1], prim[2]).buffer(prim[3], resolution=16))
        elif kind == "solid":
            parts.append(Polygon(prim[1]).buffer(prim[2] / 2, join_style=1, resolution=8))
        elif kind == "bez":
            parts.append(stroke(_flatten_bez(prim[1], prim[2])))
    return unary_union(parts).buffer(0).simplify(0.03)


def build_font(path, upm=1000, advance=1000, box_em=0.90, centre=350):
    """Write the TrueType icon font. Glyphs are box_em tall, centred on `centre` units above the baseline."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from shapely.geometry import MultiPolygon
    from shapely.geometry.polygon import orient

    scale = upm * box_em / 24.0
    x_off = (advance - 24 * scale) / 2

    def to_font(x, y):
        return (round(x_off + x * scale), round(centre + (12 - y) * scale))

    names = list(ICONS)
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (advance, 0)}
    for name in names:
        shape = geometry(name)
        polys = list(shape.geoms) if isinstance(shape, MultiPolygon) else [shape]
        pen = TTGlyphPen(None)
        xs = []
        for poly in polys:
            poly = orient(type(poly)([to_font(*c) for c in poly.exterior.coords],
                                     [[to_font(*c) for c in ring.coords] for ring in poly.interiors]), sign=-1.0)
            for ring in [poly.exterior] + list(poly.interiors):
                pts = []
                for c in list(ring.coords)[:-1]:
                    p = (round(c[0]), round(c[1]))
                    if not pts or pts[-1] != p:
                        pts.append(p)
                if len(pts) < 3:
                    continue
                pen.moveTo(pts[0])
                for p in pts[1:]:
                    pen.lineTo(p)
                pen.closePath()
                xs.extend(p[0] for p in pts)
        glyphs[name] = pen.glyph()
        metrics[name] = (advance, min(xs) if xs else 0)

    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder([".notdef"] + names)
    fb.setupCharacterMap({CODEPOINTS[n]: n for n in names})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-250)
    fb.setupNameTable({"familyName": "Claude HUD Icons", "styleName": "Regular",
                       "uniqueFontIdentifier": "ClaudeHudIcons-Regular", "fullName": "Claude HUD Icons Regular",
                       "psName": "ClaudeHudIcons-Regular", "version": "Version 1.000",
                       "licenseDescription": "MIT License"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-250, usWinAscent=900, usWinDescent=250, sxHeight=500,
                sCapHeight=700, achVendID="CHUD")
    fb.setupPost(isFixedPitch=0)
    fb.save(path)
