"""PDF export: the same slides, one page each, in deck order."""

from pathlib import Path
from typing import Any

from matplotlib.backends.backend_pdf import PdfPages

from backend.exports.render import BG, slide_figure


def export(deck: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(path) as pdf:
        for entry in deck:
            pdf.savefig(slide_figure(entry["slide"], entry["code"]), facecolor=BG)
