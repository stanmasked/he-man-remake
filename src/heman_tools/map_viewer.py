"""Asset-free, read-only schematic SVG of decoded level object positions.

This deliberately does not infer collision geometry, physical platform sizes,
texture placements or executable script behaviour. The output uses basic SVG
primitives and coordinate ticks, never source-game images or embedded scripts.
"""
from __future__ import annotations

from collections import Counter
from html import escape
import math

from .objects import ParsedLevel
from .waypoints import LevelPointGroups

PALETTE = {
    "terrain": "#9fb6d1",
    "enemy": "#fb7185",
    "door": "#fbbf24",
    "camera": "#a78bfa",
    "checkpoint": "#34d399",
    "trigger": "#fb923c",
    "reward": "#38bdf8",
    "other": "#64748b",
    "point": "#4ade80",
}


def category(class_name: str) -> str:
    c = class_name.lower()
    if "enemy" in c or "boss" in c:
        return "enemy"
    if "door" in c or "gate" in c:
        return "door"
    if "camera" in c:
        return "camera"
    if "checkpoint" in c:
        return "checkpoint"
    if any(v in c for v in ("trigger", "sensor", "initializer", "cutscene", "tutorial")):
        return "trigger"
    if any(v in c for v in ("reward", "lore", "orb", "collect")):
        return "reward"
    if any(v in c for v in ("platform", "tilemap", "ground", "water", "background", "lava")):
        return "terrain"
    return "other"


def render_level_svg(level: ParsedLevel, graph: LevelPointGroups, *,
                     width: int = 1600, height: int = 850,
                     min_x: float | None = None,
                     max_x: float | None = None) -> str:
    """Create an X/Y point diagram using independent scales, with labels & hover tips.

    Coordinates from the original transform/point records; no hitbox/geometry.
    SVG is inert (no JS, external resources or foreignObject).
    """
    if level.level_name != graph.level_name:
        raise ValueError("level and point groups refer to different maps")
    if not (800 <= width <= 8192 and 460 <= height <= 4096):
        raise ValueError("canvas dimensions out of bounds")
    values_x = [o.x for o in level.objects]
    values_y = [o.y for o in level.objects]
    for group in graph.groups:
        values_x.extend(p.x for p in group.points)
        values_y.extend(p.y for p in group.points)
    if not values_x:
        values_x = [0.0]
        values_y = [0.0]
    if not all(math.isfinite(v) for v in (*values_x, *values_y)):
        raise ValueError("non-finite source coordinates")
    left_x = float(min_x) if min_x is not None else min(values_x)
    right_x = float(max_x) if max_x is not None else max(values_x)
    if min_x is None and max_x is None and left_x == right_x:
        left_x -= 100.0
        right_x += 100.0
    if not math.isfinite(left_x) or not math.isfinite(right_x) or left_x >= right_x:
        raise ValueError("invalid horizontal view bounds")
    y0, y1 = min(values_y), max(values_y)
    if abs(y1 - y0) < 1e-8:
        y0 -= 100
        y1 += 100
    dy = y1 - y0
    y0 -= 0.09 * dy
    y1 += 0.09 * dy

    lx, rx, top, bottom = 94, width - 46, 170, height - 145
    pw, ph = rx - lx, bottom - top
    fx = lambda x: lx + (x - left_x) / (right_x - left_x) * pw
    fy = lambda y: top + (y - y0) / (y1 - y0) * ph
    fmt = lambda v: f"{v:.2f}"
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0b1221"/>',
        f'<text x="{lx}" y="61" fill="#f8fafc" font-family="sans-serif" font-size="32" font-weight="700">{escape(level.level_name)}</text>',
        f'<text x="{lx}" y="93" fill="#94a3b8" font-family="sans-serif" font-size="17">SCHEMATIC • decoded positions only • objects are points, NOT collision shapes</text>',
        f'<text x="{lx}" y="119" fill="#94a3b8" font-family="sans-serif" font-size="15">{len(level.objects)} objects  •  {graph.total_points} named points  •  {graph.total_links} links  •  X {left_x:g}…{right_x:g}</text>',
        f'<rect x="{lx}" y="{top}" width="{pw}" height="{ph}" fill="#132035" stroke="#334155" stroke-width="2"/>',
    ]
    # Coordinate ruler, gridlines and numbers; labels state the measurement is not known to be pixels.
    for i in range(11):
        v = left_x + (right_x - left_x) * i / 10
        x = fx(v)
        lines.append(f'<line x1="{fmt(x)}" y1="{top}" x2="{fmt(x)}" y2="{bottom}" stroke="#334155" stroke-opacity="0.65" stroke-dasharray="3 7"/>')
        lines.append(f'<text x="{fmt(x)}" y="{bottom + 26}" text-anchor="middle" fill="#94a3b8" font-size="14" font-family="sans-serif">{v:.0f}</text>')
    for i in range(6):
        v = y0 + (y1-y0) * i / 5
        y = fy(v)
        lines.append(f'<line x1="{lx}" y1="{fmt(y)}" x2="{rx}" y2="{fmt(y)}" stroke="#334155" stroke-opacity="0.5"/>')
        lines.append(f'<text x="{lx-12}" y="{fmt(y+5)}" text-anchor="end" fill="#94a3b8" font-family="sans-serif" font-size="13">{v:.0f}</text>')
    lines.append(f'<text x="{lx}" y="{bottom + 55}" fill="#cbd5e1" font-size="15" font-family="sans-serif">X from object transform / point record (independent X/Y scaling)</text>')

    def visible(x: float, y: float) -> bool:
        return left_x <= x <= right_x and y0 <= y <= y1

    # Draw any cross-links as dotted edges. Do not claim their game semantics.
    for group in graph.groups:
        for point in group.points:
            for edge in point.link_indices:
                destination = group.points[edge]
                if visible(point.x, point.y) and visible(destination.x, destination.y):
                    lines.append(f'<line x1="{fmt(fx(point.x))}" y1="{fmt(fy(point.y))}" x2="{fmt(fx(destination.x))}" y2="{fmt(fy(destination.y))}" stroke="#4ade80" stroke-opacity="0.60" stroke-width="2" stroke-dasharray="6 5"/>')

    for obj in level.objects:
        if not visible(obj.x, obj.y):
            continue
        cat = category(obj.class_name)
        x, y = fx(obj.x), fy(obj.y)
        color = PALETTE[cat]
        tooltip = escape(f"{obj.index}: {obj.class_name} / {obj.instance_name or '(unnamed)'} — ({obj.x:g}, {obj.y:g})")
        radius = 6 if cat in {"enemy", "door", "checkpoint", "camera"} else 4.2
        lines.append(f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="{radius}" fill="{color}" stroke="#0b1221" stroke-width="1.5"><title>{tooltip}</title></circle>')

    # Only selected labels are drawn. Preserve full metadata in hover tooltips.
    labelled = 0
    previous_labels: list[tuple[float, float]] = []
    for obj in level.objects:
        cat = category(obj.class_name)
        if cat not in {"door", "camera", "checkpoint"} or not visible(obj.x, obj.y):
            continue
        if labelled >= 14:
            break
        x, y = fx(obj.x) + 8, fy(obj.y) - 12
        if any(abs(x - px) < 115 and abs(y - py) < 28 for px, py in previous_labels):
            continue
        title = obj.instance_name or obj.class_name
        if len(title) > 22:
            title = title[:19] + "…"
        lines.append(f'<text x="{fmt(x)}" y="{fmt(y)}" fill="{PALETTE[cat]}" font-size="12" font-family="sans-serif" opacity="0.9">{escape(title)}</text>')
        labelled += 1
        previous_labels.append((x, y))

    for group in graph.groups:
        for idx, p in enumerate(group.points):
            if not visible(p.x, p.y):
                continue
            x, y = fx(p.x), fy(p.y)
            lines.append(f'<rect x="{fmt(x-4)}" y="{fmt(y-4)}" width="8" height="8" transform="rotate(45 {fmt(x)} {fmt(y)})" fill="none" stroke="{PALETTE["point"]}" stroke-width="2"><title>{escape(group.name)}[{idx}] ({p.x:g}, {p.y:g}, {p.z:g})</title></rect>')

    counts = Counter(category(o.class_name) for o in level.objects if left_x <= o.x <= right_x)
    legend = ["enemy", "door", "camera", "checkpoint", "trigger", "terrain", "reward", "other", "point"]
    x0 = lx
    ly = height - 54
    for cat in legend:
        lines.append(f'<circle cx="{x0+6}" cy="{ly-5}" r="6" fill="{PALETTE[cat]}"/>')
        label = "named points" if cat == "point" else f"{cat} ({counts[cat]})"
        lines.append(f'<text x="{x0+19}" y="{ly}" fill="#cbd5e1" font-family="sans-serif" font-size="14">{label}</text>')
        x0 += max(110, len(label)*8+37)
    lines.append('</svg>')
    return "\n".join(lines) + "\n"
