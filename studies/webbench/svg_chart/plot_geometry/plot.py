"""Draw the measured browser geometry of the two researcher-set axis options."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "artifacts/svg-chart-requirement-conflict-20261123/variants.json"
SUMMARY = ROOT / "studies/results/svg-chart-requirement-conflict-20261123.json"
PDF = ROOT / "DNA_latex/figures/chart-axis-conflict.pdf"
PALETTE = ("#245787", "#2B817A", "#A15029")


def label(fig, x, y, words, size, bold=False):
    # Vector outlines keep the lettering portable in the conference PDF.
    path = TextPath((0, 0), words, size=size,
                    prop=FontProperties(family="DejaVu Sans", weight="bold" if bold else "normal"))
    bounds = path.get_extents()
    transform = Affine2D().translate(x - bounds.x0 - bounds.width / 2, y - bounds.y0)
    transform = transform.scale(1 / 72) + fig.dpi_scale_trans
    fig.add_artist(PathPatch(path, transform=transform, facecolor="#172633", edgecolor="none"))


def draw(output):
    summary = json.loads(SUMMARY.read_text())
    if hashlib.sha256(RAW.read_bytes()).hexdigest() != summary["variant_raw_sha256"]:
        raise ValueError("Measured browser geometry differs from the study manifest")
    raw = json.loads(RAW.read_text())
    fig = plt.figure(figsize=(3.25, 1.25), facecolor="white")
    for center, name, title in [(58.5, "axes_false", "Task 3   ·   axes off"),
                                (175.5, "axes_true", "Task 4   ·   axes on")]:
        key = raw["variants"]["ai"][name]["page"]
        first, second = raw["pages"][key]
        if first != second or first["viewBox"] != [0, 0, 100, 70]:
            raise ValueError("Two independent measurements must agree on the common drawing frame")
        paths = [line["points"] for line in first["lines"]]
        left = min(x for path in paths for x, y in path)
        bottom = max(y for path in paths for x, y in path)
        # Both panels have 0.85 physical points per SVG user unit.
        axis = fig.add_axes([(center - 42.5) / 234, 16 / 90, 85 / 234, 59.5 / 90])
        axis.set(xlim=(0, 100), ylim=(70, 0), aspect="equal")
        axis.set_axis_off()
        if left > 0:
            axis.add_patch(Rectangle((0, 0), left, 70, linewidth=0, facecolor="#EEEAE1"))
        if bottom < 70:
            axis.add_patch(Rectangle((left, bottom), 100 - left, 70 - bottom,
                                     linewidth=0, facecolor="#EEEAE1"))
        axis.add_patch(Rectangle((0, 0), 100, 70, edgecolor="#909AA1", facecolor="none",
                                 linewidth=.55, clip_on=False))
        for points, color in zip(paths, PALETTE, strict=True):
            xs, ys = zip(*points, strict=True)
            axis.plot(xs, ys, color=color, linewidth=1.05, solid_capstyle="butt",
                      solid_joinstyle="round", clip_on=False)
        for endpoints in (first["xAxis"], first["yAxis"]):
            if endpoints:
                xs, ys = zip(*endpoints, strict=True)
                axis.plot(xs, ys, color="#182B39", linewidth=.95, solid_capstyle="butt")
        label(fig, center, 79, title, 8.3, bold=True)
        label(fig, center, 3.1, f"Left {left:g}   ·   Bottom {70 - bottom:g}", 7.5)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"Title":"Left and bottom margins in the lineAxes chart",
                "Subject":"Redrawing of browser-measured polylines and axes for two researcher-set "
                          "configurations of one GPT-5 library. Units are SVG viewBox coordinates.",
                "CreationDate":datetime(2026, 11, 23, tzinfo=timezone.utc)}
    fig.savefig(output, format="pdf", metadata=metadata)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PDF)
    draw(parser.parse_args().output)
