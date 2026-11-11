"""Descriptive statistics and figures for the Phase 1 presentation.

Figures use the colours of the presentation template (navy #032A54) and are saved as
PDF (for the LaTeX slides) and PNG. They have no titles: the slide or caption gives one.

Input:  data/final/imo_contestants_full.csv, data/raw/participations.csv,
        data/raw/competitions.csv, extraction/competition_calendar.csv
Output: docs/figures/*.pdf, docs/figures/*.png, analysis/results/descriptives.md
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"
RESULTS = ROOT / "analysis" / "results"

INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#6f6e69"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"
NAVY, LIGHT = "#032A54", "#9DB9DA"
MISSING, NOT_HELD = "#D9603B", "#ECEBE6"
AWARD_RAMP = {"none": "#C3D5EA", "hm": "#8EAFD6", "bronze": "#4F7FB8",
              "silver": "#1F5394", "gold": "#032A54"}
AWARD_LABEL = {"none": "No award", "hm": "Honourable mention", "bronze": "Bronze",
               "silver": "Silver", "gold": "Gold"}
COMPETITIONS = ["IMO", "JBMO", "BMO", "EGMO", "RMM", "APMO", "MEMO", "PAMO"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 14, "axes.titlesize": 15,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
})


def save(fig, name: str) -> None:
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIGURES / f"{name}.{ext}", dpi=200)
    plt.close(fig)


def history_per_year(df: pd.DataFrame) -> None:
    g = df.assign(other=df.hist_n_other > 0).groupby(["id_year", "other"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.bar(g.index, g[True], color=NAVY, width=0.75, edgecolor=SURFACE, linewidth=1,
           label="With a prior non-IMO olympiad")
    ax.bar(g.index, g[False], bottom=g[True], color=LIGHT, width=0.75, edgecolor=SURFACE,
           linewidth=1, label="IMO history only, or none")
    ax.set_ylabel("Contestants")
    ax.grid(axis="x", visible=False)
    ax.set_xticks(g.index[::2])
    ax.legend(loc="upper left", ncols=1, bbox_to_anchor=(0, 1.0), fontsize=13)
    ax.set_ylim(0, g.sum(axis=1).max() * 1.15)
    save(fig, "contestants_per_year")


def score_distribution(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4))
    counts = df.target_total.value_counts().reindex(range(43), fill_value=0)
    ax.bar(counts.index, counts.values, color=NAVY, width=0.8)
    ax.set_xlabel("Total score (0–42)")
    ax.set_ylabel("Contestants")
    ax.grid(axis="x", visible=False)
    ax.set_xticks(range(0, 43, 7))
    save(fig, "imo_score_distribution")


def coverage_by_competition(df: pd.DataFrame) -> pd.Series:
    cov = pd.Series({c: (df[f"{c.lower()}_n"] > 0).mean() for c in COMPETITIONS[1:]})
    cov["IMO"] = (df.imo_n_prior > 0).mean()
    cov = cov.sort_values()
    fig, ax = plt.subplots(figsize=(6.5, 4.4))
    ax.barh(cov.index, cov.values * 100, color=NAVY, height=0.6)
    for y, v in enumerate(cov.values):
        ax.text(v * 100 + 0.6, y, f"{v:.1%}", va="center", color=INK_2, fontsize=13)
    ax.set_xlabel("% of IMO entries, 2008–2026")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, cov.max() * 100 * 1.25)
    save(fig, "history_coverage")
    return cov


def correlation_by_competition(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for comp in COMPETITIONS:
        col = "imo_best_rank_pct" if comp == "IMO" else f"{comp.lower()}_best_rank_pct"
        sub = df[df[col].notna()]
        rows.append({"competition": comp, "n": len(sub),
                     "spearman": sub[col].corr(sub.target_rank_pct, method="spearman")})
    corr = pd.DataFrame(rows).set_index("competition").sort_values("spearman")
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    ax.barh(corr.index, corr.spearman, color=NAVY, height=0.6)
    for y, (r, n) in enumerate(zip(corr.spearman, corr.n)):
        ax.text(r + 0.015, y, f"{r:.2f} (n={n:,})", va="center", color=INK_2, fontsize=13)
    ax.set_xlabel("Spearman correlation with the IMO percentile")
    ax.set_xlim(0, 1.2)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.grid(axis="y", visible=False)
    save(fig, "correlation_by_competition")
    return corr


def awards_by_prior_imo(df: pd.DataFrame) -> pd.DataFrame:
    n = df.imo_n_prior.clip(upper=3).map(lambda k: "3+" if k == 3 else str(k))
    share = pd.crosstab(n, df.target_award, normalize="index")[list(AWARD_RAMP)]
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    left = pd.Series(0.0, index=share.index)
    for award, color in AWARD_RAMP.items():
        ax.barh(share.index, share[award] * 100, left=left * 100, color=color, height=0.6,
                edgecolor=SURFACE, linewidth=2, label=AWARD_LABEL[award])
        left += share[award]
    ax.set_ylabel("Previous IMOs")
    ax.set_xlabel("% of contestants")
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.grid(visible=False)
    ax.legend(loc="lower center", ncols=3, bbox_to_anchor=(0.45, -0.46), fontsize=12)
    save(fig, "awards_by_prior_imo")
    return share


def coverage_matrix(comps: pd.DataFrame, calendar: pd.DataFrame) -> None:
    """Which editions are in the data: full, medallists only, missing, or not held yet."""
    years = range(2005, comps.year.max() + 1)
    first_held = calendar.set_index("source").first_held
    coverage = comps.set_index(["source", "year"]).coverage
    states = {"full": NAVY, "partial": LIGHT, "missing": MISSING, "not held": NOT_HELD}
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for row, source in enumerate(COMPETITIONS):
        for year in years:
            if year < first_held[source]:
                state = "not held"
            elif (source, year) not in coverage.index:
                state = "missing"
            else:
                state = "full" if coverage[(source, year)] == "full" else "partial"
            ax.add_patch(plt.Rectangle((year - 0.45, row - 0.4), 0.9, 0.8, color=states[state], lw=0))
    ax.set_xlim(min(years) - 0.6, max(years) + 0.6)
    ax.set_ylim(len(COMPETITIONS) - 0.5, -0.5)
    ax.set_yticks(range(len(COMPETITIONS)), COMPETITIONS)
    ax.set_xticks([y for y in years if y % 3 == 2])
    ax.grid(visible=False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in states.values()]
    labels = ["Full results", "Medallists only", "Missing", "Not held yet"]
    ax.legend(handles, labels, loc="lower center", ncols=4, bbox_to_anchor=(0.5, -0.36), fontsize=12)
    save(fig, "coverage_matrix")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ROOT / "data" / "final" / "imo_contestants_full.csv", low_memory=False)
    parts = pd.read_csv(ROOT / "data" / "raw" / "participations.csv")

    history_per_year(df)
    score_distribution(df)
    cov = coverage_by_competition(df)
    corr = correlation_by_competition(df)
    share = awards_by_prior_imo(df)
    coverage_matrix(pd.read_csv(ROOT / "data" / "raw" / "competitions.csv"),
                    pd.read_csv(ROOT / "extraction" / "competition_calendar.csv"))

    raw = parts.groupby("source").agg(editions=("competition_id", "nunique"), rows=("total", "size"),
                                      first=("year", "min"), last=("year", "max"))
    features = [c for c in df.columns if not c.startswith(("id_", "target_", "meta_"))]
    lines = [
        "# Dataset descriptives",
        "",
        f"- Raw participations: {len(parts):,} rows, {parts.contestant_id.nunique():,} contestants, "
        f"{parts.competition_id.nunique()} competition editions",
        f"- Final table: {len(df):,} IMO entries (IMO {df.id_year.min()}–{df.id_year.max()}), "
        f"{df.id_contestant.nunique():,} contestants, {df.id_country.nunique()} countries, "
        f"{len(features)} features",
        f"- With any prior international result: {(df.hist_n_events > 0).mean():.1%}; "
        f"with a prior non-IMO olympiad: {(df.hist_n_other > 0).mean():.1%}",
        f"- IMO total: mean {df.target_total.mean():.1f}, median {df.target_total.median():.0f}, "
        f"sd {df.target_total.std():.1f}",
        "",
        "## Raw participations by competition",
        "",
        raw.to_markdown(),
        "",
        "## IMO award distribution",
        "",
        df.target_award.value_counts(normalize=True).reindex(list(AWARD_RAMP)).rename("share").to_frame()
        .to_markdown(floatfmt=".3f"),
        "",
        "## Prior-history coverage (share of IMO entries)",
        "",
        cov.rename("share").to_frame().to_markdown(floatfmt=".3f"),
        "",
        "## Best prior percentile vs IMO percentile (Spearman)",
        "",
        corr.round(3).to_markdown(),
        "",
        "## IMO award by number of previous IMOs (row shares)",
        "",
        share.to_markdown(floatfmt=".3f"),
        "",
    ]
    (RESULTS / "descriptives.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
