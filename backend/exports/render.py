"""Draws slide visuals (and whole slides for the PDF) with matplotlib in the Solar palette."""

import logging
import textwrap
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display; exports only
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # font fallbacks are expected

from matplotlib.axes import Axes  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

BG = "#0D0A08"
PANEL = "#1E140E"
ACC, ACC2, ACC3 = "#FF9B3D", "#FF4D5E", "#FFD27A"
TEXT, MUTE, DIM = "#F7EBDD", "#BFA58F", "#6B4A30"
SERIES = [ACC, ACC3, ACC2, "#5CE1E6", "#6FD98A"]
SANS = ["IBM Plex Sans", "Calibri", "DejaVu Sans"]
DISPLAY = ["Oxanium", "Arial", "DejaVu Sans"]
MONO = ["IBM Plex Mono", "Consolas", "DejaVu Sans Mono"]


def _box(ax: Axes, x: float, y: float, w: float, h: float, label: str, edge: str = ACC) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.01,rounding_size=0.02", fc=PANEL, ec=edge, lw=1.4,
        )
    )  # fmt: skip
    ax.text(x, y, textwrap.fill(label, 16), ha="center", va="center", color=TEXT,
            fontsize=9, family=SANS)  # fmt: skip


def _arrow(ax: Axes, start: tuple[float, float], end: tuple[float, float], label: str = "") -> None:
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": MUTE, "lw": 1.2})
    if label:
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.03)
        ax.text(*mid, label, ha="center", va="bottom", color=MUTE, fontsize=7, family=SANS)


def _architecture(ax: Axes, spec: dict[str, Any]) -> None:
    groups: list[str] = []
    for node in spec["nodes"]:
        if node["group"] not in groups:
            groups.append(node["group"])
    pos: dict[str, tuple[float, float]] = {}
    for gi, group in enumerate(groups):
        members = [n for n in spec["nodes"] if n["group"] == group]
        x = (gi + 0.5) / len(groups)
        ax.text(x, 0.97, group.upper(), ha="center", va="top", color=ACC3, fontsize=8,
                family=DISPLAY)  # fmt: skip
        for ni, node in enumerate(members):
            y = 0.85 - (ni + 0.5) * (0.8 / len(members))
            pos[node["id"]] = (x, y)
    width = min(0.8 / len(groups), 0.24)
    for node in spec["nodes"]:
        _box(ax, *pos[node["id"]], width, 0.12, node["label"])
    for edge in spec["edges"]:
        if edge["from"] in pos and edge["to"] in pos:
            (x1, y1), (x2, y2) = pos[edge["from"]], pos[edge["to"]]
            shift = width / 2 if x2 != x1 else 0
            sign = 1 if x2 >= x1 else -1
            _arrow(ax, (x1 + sign * shift, y1), (x2 - sign * shift, y2), edge.get("label", ""))


def _flow(ax: Axes, spec: dict[str, Any]) -> None:
    steps = spec["steps"]
    width = min(0.8 / len(steps), 0.2)
    xs = [(i + 0.5) / len(steps) for i in range(len(steps))]
    for x, label in zip(xs, steps, strict=True):
        _box(ax, x, 0.5, width, 0.25, label)
    for a, b in zip(xs, xs[1:], strict=False):
        _arrow(ax, (a + width / 2, 0.5), (b - width / 2, 0.5))


def _chart(ax: Axes, spec: dict[str, Any]) -> None:
    ax.set_facecolor(BG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(DIM)
    ax.tick_params(colors=MUTE, labelsize=8)
    count = len(spec["series"])
    for i, series in enumerate(spec["series"]):
        color = SERIES[i % len(SERIES)]
        x, y = series["x"], series["y"]
        if spec["type"] == "bar":
            offsets = [j + (i - (count - 1) / 2) * 0.8 / count for j in range(len(x))]
            ax.bar(offsets, y, width=0.8 / count, color=color, label=series["name"])
            ax.set_xticks(range(len(x)), [str(v) for v in x])
        elif spec["type"] == "line":
            ax.plot(x, y, color=color, lw=2, marker="o", label=series["name"])
        else:
            ax.scatter(x, y, color=color, s=18, label=series["name"])
    ax.set_xlabel(spec["x_label"], color=MUTE, fontsize=9)
    ax.set_ylabel(spec["y_label"], color=MUTE, fontsize=9)
    if count > 1:
        ax.legend(frameon=False, labelcolor=TEXT, fontsize=8)


def _code(ax: Axes, spec: dict[str, Any], code: list[str]) -> None:
    start = spec["lines"][0]
    shown = code[:25]
    step = 0.9 / max(len(shown), 18)  # short excerpts keep a normal line height
    for i, line in enumerate(shown):
        number = start + i
        y = 0.95 - (i + 0.5) * step
        if number in spec["highlight"]:
            ax.add_patch(FancyBboxPatch((0.0, y - step / 2), 1.0, step, boxstyle="square,pad=0",
                                        fc="#3A2414", ec="none"))  # fmt: skip
        ax.text(0.02, y, f"{number:>4}  {line[:90]}", va="center", ha="left", color=TEXT,
                fontsize=8, family=MONO)  # fmt: skip
    ax.text(0.02, 0.98, spec["path"], va="top", color=ACC3, fontsize=8, family=MONO)


def _table(ax: Axes, spec: dict[str, Any]) -> None:
    table = ax.table(cellText=spec["rows"] or [[""] * len(spec["columns"])],
                     colLabels=spec["columns"], loc="center", cellLoc="left")  # fmt: skip
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor(DIM)
        cell.set_facecolor(PANEL if row else "#2A1A10")
        cell.get_text().set_color(ACC3 if row == 0 else TEXT)


def draw_visual(ax: Axes, visual: dict[str, Any], code: list[str] | None) -> None:
    kind, spec = visual["kind"], visual["spec"]
    if kind == "chart":  # charts scale to their data; the rest draw on a unit square
        _chart(ax, spec)
        return
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    if kind == "architecture":
        _architecture(ax, spec)
    elif kind == "flow":
        _flow(ax, spec)
    elif kind == "code":
        _code(ax, spec, code or ["(code not found in the commit)"])
    else:
        _table(ax, spec)


def visual_figure(visual: dict[str, Any], code: list[str] | None) -> Figure:
    fig = Figure(figsize=(8, 4.5), facecolor=BG)
    draw_visual(fig.add_axes((0.04, 0.06, 0.92, 0.88), facecolor=BG), visual, code)
    return fig


def _bullets(items: list[str], width: int) -> str:
    return "\n".join(textwrap.fill(f"• {item}", width, subsequent_indent="  ") for item in items)


def slide_figure(slide: dict[str, Any], code: list[str] | None) -> Figure:
    """A whole 16:9 slide, laid out like the PowerPoint export (DESIGN section 6)."""
    fig = Figure(figsize=(13.333, 7.5), facecolor=BG)
    fig.text(0.04, 0.93, slide["kicker"].upper(), color=ACC, fontsize=11, family=DISPLAY)
    fig.text(0.04, 0.86, slide["title"], color=TEXT, fontsize=26, family=DISPLAY, weight="bold")
    fig.text(0.04, 0.81, textwrap.fill(slide["what"], 110), color=MUTE, fontsize=12, family=SANS)
    draw_visual(fig.add_axes((0.04, 0.17, 0.6, 0.6), facecolor=BG), slide["visual"], code)
    right = []
    if slide["decisions"]:
        right.append("DECISIONS\n" + _bullets([f"{d['choice']}: {d['tradeoff']}" for d in slide["decisions"]], 44))
    if slide["failure_and_scale"]:
        right.append("FAILURE AND SCALE\n" + _bullets(slide["failure_and_scale"], 44))
    fig.text(0.67, 0.77, "\n\n".join(right), color=TEXT, fontsize=10, family=SANS, va="top",
             linespacing=1.4)  # fmt: skip
    if slide["struggled"]:
        footer = "  ·  ".join(f"{s['question']} ({s['hints']} hints)" for s in slide["struggled"])
        fig.text(0.04, 0.06, textwrap.fill("Questions I struggled with: " + footer, 170),
                 color=ACC3, fontsize=9, family=SANS)  # fmt: skip
    return fig
