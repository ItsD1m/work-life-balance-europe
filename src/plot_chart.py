"""Φτιάχνει το γράφημα τεταρτημορίων: μισθός vs ισορροπία εργασίας-ζωής, μόνο Ευρώπη.

    python src/plot_chart.py              # ελληνικά + αγγλικά, light + dark
    python src/plot_chart.py --lang en    # μόνο αγγλικά
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "europe_work_life_balance.csv"
OUTDIR = ROOT / "output"


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    text_primary: str
    text_secondary: str
    text_muted: str
    grid: str
    series: str
    accent: str


THEMES = {
    "light": Theme("light", "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984",
                   "#e6e5e1", "#2a78d6", "#eb6834"),
    "dark": Theme("dark", "#1a1a19", "#ffffff", "#c3c2b7", "#8a8984",
                  "#2e2e2c", "#3987e5", "#d95926"),
}

STRINGS = {
    "el": {
        "title": "Πού δουλεύεις, πόσο πληρώνεσαι και τι κερδίζεις στη ζωή",
        "subtitle": "{n} ευρωπαϊκές πόλεις: μέσος καθαρός μηνιαίος μισθός έναντι δείκτη "
                    "ισορροπίας εργασίας–προσωπικής ζωής",
        "xlabel": "Μέσος καθαρός μηνιαίος μισθός (USD)",
        "ylabel": "Δείκτης ισορροπίας εργασίας–προσωπικής ζωής",
        "q_tl": "Περισσότερη ζωή,\nχαμηλότερες αποδοχές",
        "q_tr": "Το καλύτερο και από τα δύο",
        "q_bl": "Χαμηλότερες αποδοχές,\nμικρότερη ισορροπία",
        "q_br": "Υψηλότερες αποδοχές,\nπερισσότερη πίεση",
        "median": "διάμεσος",
        "source": "Πηγές: Blueground – Global Work-Life Balance City Index 2025 · "
                  "Numbeo – μέσος καθαρός μηνιαίος μισθός",
        "name_field": "city_el",
    },
    "en": {
        "title": "Where you work, what you earn, and what life you get",
        "subtitle": "{n} European cities: average net monthly salary against the "
                    "work-life balance index",
        "xlabel": "Average monthly net salary (USD)",
        "ylabel": "Work-life balance index",
        "q_tl": "More life,\nlower pay",
        "q_tr": "Best of both worlds",
        "q_bl": "Lower pay,\nless balance",
        "q_br": "Higher pay,\nmore pressure",
        "median": "median",
        "source": "Sources: Blueground – Global Work-Life Balance City Index 2025 · "
                  "Numbeo – average monthly net salary",
        "name_field": "city",
    },
}

HIGHLIGHT = "Athens"


def load_rows() -> list[dict[str, str]]:
    if not DATA.exists():
        raise SystemExit(f"Λείπει το {DATA.name}. Τρέξε: python src/build_dataset.py")
    with DATA.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


# --- τοποθέτηση ετικετών -----------------------------------------------------
# Οι πόλεις στοιβάζονται στην ίδια γωνία του γραφήματος, οπότε δοκιμάζουμε οκτώ
# θέσεις γύρω από κάθε κουκκίδα και κρατάμε αυτήν με τη μικρότερη επικάλυψη.

OFFSETS = [
    (1, 0, "left", "center"), (-1, 0, "right", "center"),
    (0, 1, "center", "bottom"), (0, -1, "center", "top"),
    (0.75, 0.75, "left", "bottom"), (-0.75, 0.75, "right", "bottom"),
    (0.75, -0.75, "left", "top"), (-0.75, -0.75, "right", "top"),
]


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return dx * dy if dx > 0 and dy > 0 else 0.0


RADII_PT = (6.0, 11.0, 17.0, 25.0)
MARKER_HALF_PT = 5.5


def place_labels(ax, points, labels, fontsize, color_of, bounds, theme):
    """points: [(x_disp, y_disp)] σε pixel οθόνης.

    Όλα τα μεγέθη δηλώνονται σε points και μετατρέπονται σε pixel με το dpi,
    αλλιώς σε υψηλό dpi τα πλαίσια βγαίνουν μικροσκοπικά και δεν ανιχνεύεται καμία
    επικάλυψη.
    """
    scale = ax.figure.dpi / 72.0
    radii = [r * scale for r in RADII_PT]
    marker_half = MARKER_HALF_PT * scale
    taken: list[tuple[float, float, float, float]] = []
    dots = [(x - marker_half, y - marker_half, x + marker_half, y + marker_half)
            for x, y in points]

    # Ξεκινάμε από τις απομονωμένες πόλεις· οι στριμωγμένες παίρνουν ό,τι μείνει.
    order = sorted(range(len(points)), key=lambda i: -points[i][1])
    placements: dict[int, tuple[float, float, str, str, float]] = {}

    for i in order:
        px, py = points[i]
        width = len(labels[i]) * fontsize * 0.56 * scale
        height = fontsize * 1.25 * scale
        best, best_box, best_cost, best_penalty = None, None, float("inf"), float("inf")

        for radius in radii:
            for dx, dy, ha, va in OFFSETS:
                cx = px + dx * radius + (0 if ha == "center" else (width / 2) * (1 if dx > 0 else -1))
                cy = py + dy * radius + (0 if va == "center" else (height / 2) * (1 if dy > 0 else -1))
                box = (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)

                penalty = sum(_overlap(box, t) for t in taken) * 8
                penalty += sum(_overlap(box, d) for d in dots) * 8
                # ποινή αν βγαίνει έξω από τους άξονες
                penalty += 9000 * (box[0] < bounds[0]) + 9000 * (box[2] > bounds[2])
                penalty += 9000 * (box[1] < bounds[1]) + 9000 * (box[3] > bounds[3])
                cost = penalty + (radius - radii[0]) * 40  # προτίμησε την κοντινή θέση
                if cost < best_cost:
                    best_cost, best_penalty = cost, penalty
                    best, best_box = (dx, dy, ha, va, radius), box
            if best_penalty == 0:
                break  # καθαρή θέση· μην ψάχνεις πιο μακριά

        taken.append(best_box)
        placements[i] = best

    inv = ax.transData.inverted()
    for i, (dx, dy, ha, va, radius) in placements.items():
        px, py = points[i]
        anchor = inv.transform((px + dx * radius, py + dy * radius))
        if radius > radii[0] * 1.5:  # μακρινή ετικέτα -> λεπτή γραμμή οδηγός
            ax.plot(*zip(inv.transform((px, py)), anchor),
                    color=theme.text_muted, linewidth=0.7, zorder=3)
        ax.annotate(
            labels[i], xy=anchor, ha=ha, va=va, fontsize=fontsize, color=color_of(i),
            fontweight="bold" if color_of(i) != color_of(-1) else "normal", zorder=6,
        )


def render(rows, lang: str, theme: Theme, out_path: Path) -> None:
    strings = STRINGS[lang]
    name_field = strings["name_field"]

    salaries = [float(r["net_salary_usd"]) for r in rows]
    scores = [float(r["baseline_index"]) for r in rows]
    x_mid, y_mid = median(salaries), median(scores)

    fig, ax = plt.subplots(figsize=(13, 9), dpi=200)
    fig.patch.set_facecolor(theme.surface)
    ax.set_facecolor(theme.surface)

    pad_x = (max(salaries) - min(salaries)) * 0.10
    pad_y = (max(scores) - min(scores)) * 0.12
    ax.set_xlim(min(salaries) - pad_x, max(salaries) + pad_x)
    ax.set_ylim(min(scores) - pad_y, max(scores) + pad_y)

    ax.grid(True, color=theme.grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(theme.grid)

    # γραμμές διαμέσου = τα όρια των τεταρτημορίων
    ax.axvline(x_mid, color=theme.text_muted, linewidth=1.1, linestyle=(0, (5, 4)), zorder=1)
    ax.axhline(y_mid, color=theme.text_muted, linewidth=1.1, linestyle=(0, (5, 4)), zorder=1)

    corners = [
        (0.015, 0.975, "left", "top", strings["q_tl"]),
        (0.985, 0.975, "right", "top", strings["q_tr"]),
        (0.015, 0.025, "left", "bottom", strings["q_bl"]),
        (0.985, 0.025, "right", "bottom", strings["q_br"]),
    ]
    for fx, fy, ha, va, text in corners:
        ax.text(fx, fy, text, transform=ax.transAxes, ha=ha, va=va,
                fontsize=10.5, color=theme.text_muted, linespacing=1.4, zorder=2)

    highlight = [i for i, r in enumerate(rows) if r["city"] == HIGHLIGHT]
    base = [i for i in range(len(rows)) if i not in highlight]

    ax.scatter([salaries[i] for i in base], [scores[i] for i in base],
               s=90, color=theme.series, edgecolor=theme.surface, linewidth=1.6, zorder=4)
    ax.scatter([salaries[i] for i in highlight], [scores[i] for i in highlight],
               s=190, color=theme.accent, edgecolor=theme.surface, linewidth=2.0, zorder=5)

    ax.set_xlabel(strings["xlabel"], fontsize=11.5, color=theme.text_secondary, labelpad=10)
    ax.set_ylabel(strings["ylabel"], fontsize=11.5, color=theme.text_secondary, labelpad=10)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.tick_params(colors=theme.text_secondary, labelsize=10, length=0)

    fig.suptitle(strings["title"], x=0.055, y=0.975, ha="left",
                 fontsize=20, fontweight="bold", color=theme.text_primary)
    fig.text(0.055, 0.925, strings["subtitle"].format(n=len(rows)),
             ha="left", fontsize=11.5, color=theme.text_secondary)
    fig.text(0.055, 0.025, strings["source"], ha="left",
             fontsize=9, color=theme.text_muted)

    fig.subplots_adjust(left=0.075, right=0.975, top=0.885, bottom=0.095)
    fig.canvas.draw()

    points = [ax.transData.transform((salaries[i], scores[i])) for i in range(len(rows))]
    bounds = (*ax.transData.transform((ax.get_xlim()[0], ax.get_ylim()[0])),
              *ax.transData.transform((ax.get_xlim()[1], ax.get_ylim()[1])))
    place_labels(
        ax, points, [r[name_field] for r in rows], 9.5,
        lambda i: theme.accent if i in highlight else theme.text_primary, bounds, theme,
    )

    # σημείωση στις γραμμές διαμέσου
    ax.annotate(f"{strings['median']}  ${x_mid:,.0f}", xy=(x_mid, ax.get_ylim()[0]),
                xytext=(5, 8), textcoords="offset points", fontsize=8.5,
                color=theme.text_muted, zorder=3)
    ax.annotate(f"{strings['median']}  {y_mid:.1f}", xy=(ax.get_xlim()[1], y_mid),
                xytext=(-5, 6), textcoords="offset points", ha="right", fontsize=8.5,
                color=theme.text_muted, zorder=3)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=theme.surface)
    plt.close(fig)
    print(f"-> {out_path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=["el", "en", "both"], default="both")
    parser.add_argument("--theme", choices=["light", "dark", "both"], default="both")
    args = parser.parse_args()

    rows = load_rows()
    langs = ["el", "en"] if args.lang == "both" else [args.lang]
    themes = ["light", "dark"] if args.theme == "both" else [args.theme]

    for lang in langs:
        for theme_name in themes:
            suffix = "" if theme_name == "light" else "_dark"
            render(rows, lang, THEMES[theme_name],
                   OUTDIR / f"work_life_balance_europe_{lang}{suffix}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
