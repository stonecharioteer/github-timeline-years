# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "matplotlib",
#     "numpy",
#     "pillow",
# ]
# ///
"""Generate a GitHub contribution timeline infographic from JSON data."""

import argparse
import io
import json
import urllib.request
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch, Circle
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent / "data"
OUTPUT = Path(__file__).parent / "contribution_timeline.png"

# GitHub dark theme exact colors
BG_CANVAS = "#0d1117"
BG_CARD = "#161b22"
BORDER = "#30363d"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_MUTED = "#484f58"
GREEN_ACCENT = "#39d353"

# GitHub dark theme contribution colors
COLOR_MAP = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_year(year: int) -> dict:
    path = DATA_DIR / f"{year}.json"
    with open(path) as f:
        data = json.load(f)
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def build_year_grid(calendar: dict) -> tuple[np.ndarray, list[dict], int]:
    grid = np.zeros((7, 53), dtype=int)
    total = calendar["totalContributions"]
    days = []

    for week_idx, week in enumerate(calendar["weeks"]):
        if week_idx >= 53:
            break
        for day in week["contributionDays"]:
            date = datetime.strptime(day["date"], "%Y-%m-%d")
            dow = (date.weekday() + 1) % 7
            count = day["contributionCount"]
            if count == 0:
                level = 0
            elif count <= 3:
                level = 1
            elif count <= 6:
                level = 2
            elif count <= 9:
                level = 3
            else:
                level = 4
            grid[dow, week_idx] = level
            days.append({"date": date, "count": count, "week": week_idx, "dow": dow})

    return grid, days, total


def find_month_starts(days_data: list[dict]) -> list[tuple[int, str]]:
    seen = set()
    starts = []
    for d in days_data:
        m = d["date"].month
        if m not in seen and d["dow"] == 0:
            seen.add(m)
            starts.append((d["week"], MONTH_LABELS[m - 1]))
    return starts


def main():
    parser = argparse.ArgumentParser()
    current_year = datetime.now().year
    parser.add_argument("--from", dest="from_year", type=int, default=current_year - 10)
    parser.add_argument("--to", dest="to_year", type=int, default=current_year)
    args = parser.parse_args()

    years = list(range(args.to_year, args.from_year - 1, -1))
    grids, all_days, totals = [], [], []
    for year in years:
        cal = load_year(year)
        grid, days, total = build_year_grid(cal)
        grids.append(grid)
        all_days.append(days)
        totals.append(total)

    grand_total = sum(totals)
    max_total = max(totals)

    cmap = mcolors.ListedColormap(COLOR_MAP)
    n = len(years)

    # Sizing: calculate to ensure square cells
    fig_w = 14
    axes_width_frac = 0.70
    axes_width_inch = axes_width_frac * fig_w
    cell_size = axes_width_inch / 53
    grid_height_inch = cell_size * 7
    row_h = grid_height_inch + 0.6  # grid + padding for labels
    header_h = 2.2
    bar_h = 2.0
    footer_h = 1.2
    fig_h = header_h + n * row_h + bar_h + footer_h
    axes_height_frac = grid_height_inch / fig_h

    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG_CANVAS)

    # ── Header with avatar ──
    avatar_url = "https://avatars.githubusercontent.com/u/11478411?v=4&s=128"
    avatar_img = None
    try:
        from PIL import Image
        with urllib.request.urlopen(avatar_url) as resp:
            avatar_data = resp.read()
        pil_img = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
        # Apply circular mask
        size = pil_img.size[0]
        mask = Image.new("L", pil_img.size, 0)
        from PIL import ImageDraw
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        bg = Image.new("RGBA", pil_img.size, BG_CANVAS + "ff")
        bg.paste(pil_img, mask=mask)
        avatar_img = np.array(bg).astype(np.float32) / 255.0
    except Exception as e:
        print(f"Warning: Could not load avatar: {e}")

    avatar_x = 0.04
    profile_top = 1 - 0.25 / fig_h
    if avatar_img is not None:
        avatar_size_inch = 0.5
        ax_avatar = fig.add_axes(
            [avatar_x, profile_top - avatar_size_inch / fig_h,
             avatar_size_inch / fig_w, avatar_size_inch / fig_h],
            frameon=False,
        )
        ax_avatar.imshow(avatar_img)
        ax_avatar.set_xticks([])
        ax_avatar.set_yticks([])
        for spine in ax_avatar.spines.values():
            spine.set_visible(False)

    text_x = 0.04 + 0.06
    fig.text(text_x, 1 - 0.35 / fig_h, "Vinay Keerthi",
             fontsize=11, fontweight="bold", color=TEXT_PRIMARY, fontfamily="monospace", va="top")
    fig.text(text_x, 1 - 0.65 / fig_h, "@stonecharioteer  \u00b7  member since 2015",
             fontsize=7, color=TEXT_MUTED, fontfamily="monospace", va="top")
    fig.text(0.04, 1 - 1.0 / fig_h,
             f"{grand_total:,} contributions across {n} years",
             fontsize=26, fontweight="bold", color=TEXT_PRIMARY, fontfamily="monospace", va="top")
    fig.text(0.04, 1 - 1.45 / fig_h,
             f"{args.from_year} \u2013 {args.to_year}",
             fontsize=10, color=TEXT_MUTED, fontfamily="monospace", va="top")

    # Stats in header
    stats_text = [
        f"Best: {years[totals.index(max_total)]} ({max_total:,})",
        f"Avg/year: {grand_total // n:,}",
    ]
    fig.text(0.96, 1 - 0.6 / fig_h, "  \u00b7  ".join(stats_text),
             fontsize=9, color=TEXT_MUTED, fontfamily="monospace", va="top", ha="right")

    # ── Year heatmap rows ──
    day_labels = ["", "Mon", "", "Wed", "", "Fri", ""]
    y_top = 1 - header_h / fig_h

    for idx, (year, grid, days, total) in enumerate(zip(years, grids, all_days, totals)):
        row_top = y_top - idx * (row_h / fig_h)
        ax_left = 0.06
        ax_bottom = row_top - axes_height_frac - 0.2 / fig_h
        ax = fig.add_axes([ax_left, ax_bottom, axes_width_frac, axes_height_frac])
        ax.set_facecolor(BG_CANVAS)

        # Draw cells as rounded rects
        for wi in range(53):
            for di in range(7):
                color = COLOR_MAP[grid[di, wi]]
                rect = FancyBboxPatch(
                    (wi - 0.43, di - 0.43), 0.86, 0.86,
                    boxstyle="round,pad=0.04", facecolor=color, edgecolor="none",
                )
                ax.add_patch(rect)

        ax.set_xlim(-0.5, 52.5)
        ax.set_ylim(6.5, -0.5)

        # Month labels on top
        month_starts = find_month_starts(days)
        if idx == 0:
            ax.set_xticks([w for w, _ in month_starts])
            ax.set_xticklabels([m for _, m in month_starts], fontsize=5.5, color=TEXT_MUTED, fontfamily="monospace")
            ax.xaxis.tick_top()
        else:
            ax.set_xticks([])

        ax.set_yticks(range(7))
        ax.set_yticklabels(day_labels, fontsize=5, color=TEXT_MUTED, fontfamily="monospace")
        ax.tick_params(axis="both", length=0, pad=2)
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Year label
        row_center_y = ax_bottom + axes_height_frac / 2
        fig.text(0.02, row_center_y, str(year),
                 fontsize=11, fontweight="bold", color=TEXT_PRIMARY, fontfamily="monospace",
                 va="center", ha="left")

        # Total + bar
        bar_x = ax_left + axes_width_frac + 0.02
        bar_w = 0.06
        bar_fill = (total / max_total) * bar_w if max_total > 0 else 0
        bar_y = row_center_y - axes_height_frac * 0.15

        # Background bar
        rect_bg = FancyBboxPatch(
            (bar_x, bar_y), bar_w, row_h / fig_h * 0.15,
            boxstyle="round,pad=0.001", facecolor=BG_CARD, edgecolor="none",
            transform=fig.transFigure,
        )
        fig.patches.append(rect_bg)

        # Fill bar
        if bar_fill > 0:
            rect_fill = FancyBboxPatch(
                (bar_x, bar_y), bar_fill, row_h / fig_h * 0.15,
                boxstyle="round,pad=0.001", facecolor=GREEN_ACCENT, edgecolor="none",
                alpha=0.7, transform=fig.transFigure,
            )
            fig.patches.append(rect_fill)

        fig.text(0.97, row_center_y, f"{total:,}",
                 fontsize=8, color=TEXT_SECONDARY, fontfamily="monospace", va="center", ha="right")

    # ── Yearly bar chart at bottom ──
    bar_bottom = footer_h / fig_h
    bar_ax = fig.add_axes([0.06, bar_bottom + 0.1 / fig_h, 0.88, bar_h / fig_h * 0.75])
    bar_ax.set_facecolor(BG_CANVAS)

    # Bar chart uses chronological order (oldest to newest, left to right)
    bar_years = list(reversed(years))
    bar_totals = list(reversed(totals))
    bar_colors = [GREEN_ACCENT if t == max_total else "#26a641" if t > grand_total / n else "#006d32" for t in bar_totals]
    bars = bar_ax.bar(range(n), bar_totals, color=bar_colors, width=0.7, edgecolor="none", alpha=0.85)

    for i, (bar, total) in enumerate(zip(bars, bar_totals)):
        if total > 0:
            bar_ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_total * 0.02,
                        f"{total:,}", ha="center", va="bottom", fontsize=6.5,
                        color=TEXT_SECONDARY, fontfamily="monospace")

    bar_ax.set_xticks(range(n))
    bar_ax.set_xticklabels([str(y) for y in bar_years], fontsize=7, color=TEXT_SECONDARY, fontfamily="monospace")
    bar_ax.set_yticks([])
    bar_ax.tick_params(axis="x", length=0, pad=4)
    bar_ax.spines["top"].set_visible(False)
    bar_ax.spines["right"].set_visible(False)
    bar_ax.spines["left"].set_visible(False)
    bar_ax.spines["bottom"].set_color(BORDER)
    bar_ax.set_xlim(-0.6, n - 0.4)

    # ── Legend ──
    legend_y = 0.015
    fig.text(0.42, legend_y, "Less", fontsize=6, color=TEXT_MUTED, fontfamily="monospace", va="center")
    for i, color in enumerate(COLOR_MAP):
        rect = FancyBboxPatch(
            (0.45 + i * 0.02, legend_y - 0.005), 0.012, 0.012,
            boxstyle="round,pad=0.001", facecolor=color, edgecolor="none",
            transform=fig.transFigure,
        )
        fig.patches.append(rect)
    fig.text(0.45 + 5 * 0.02, legend_y, "More", fontsize=6, color=TEXT_MUTED, fontfamily="monospace", va="center")

    # ── GitHub repo link ──
    fig.text(0.5, legend_y - 0.025, "github.com/stonecharioteer/github-timeline-years",
             fontsize=7, color=TEXT_SECONDARY, fontfamily="monospace", va="center", ha="center")

    plt.savefig(OUTPUT, dpi=200, bbox_inches="tight", facecolor=BG_CANVAS, pad_inches=0.4)
    print(f"Saved infographic to {OUTPUT}")


if __name__ == "__main__":
    main()
