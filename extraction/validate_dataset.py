"""Consistency checks on the raw and final tables.

Every check recomputes a quantity independently of the build scripts and compares.
Run after build_raw_tables.py and build_features.py; exits with status 1 if a check fails.

Input:  data/raw/*.csv, data/final/imo_contestants_full.csv, data/final/imo_contestants.csv,
        docs/data_dictionary.md
Output: data/final/validation_report.txt
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AWARD_CODE = {"none": 0, "hm": 1, "bronze": 2, "silver": 3, "gold": 4}
CHECK_YEARS = [2010, 2015, 2020, 2024, 2026]
OTHER = ["jbmo", "bmo", "egmo", "rmm", "apmo", "memo", "pamo"]
KEY = ["contestant_id", "id_year"]

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def problem_sum(scores) -> float:
    if not isinstance(scores, str):
        return float("nan")
    return sum(int(x) for x in scores.split(";") if x != "")


def documented_columns() -> set[str]:
    """Column names written in backticks in the data dictionary, with <c> expanded."""
    text = (ROOT / "docs" / "data_dictionary.md").read_text()
    names = set()
    for name in re.findall(r"`([a-z0-9_<>]+)`", text):
        names.update(name.replace("<c>", c) for c in OTHER) if "<c>" in name else names.add(name)
    for first, last in re.findall(r"`(\w+?)1`\s*…\s*`(\w+?)6`", text):
        names.update(f"{first}{i}" for i in range(1, 7))
    return names


def main() -> None:
    raw = {name: pd.read_csv(ROOT / "data" / "raw" / f"{name}.csv")
           for name in ["participations", "competitions", "contestants", "countries"]}
    parts, comps = raw["participations"], raw["competitions"]
    full = pd.read_csv(ROOT / "data" / "final" / "imo_contestants_full.csv", low_memory=False)
    compact = pd.read_csv(ROOT / "data" / "final" / "imo_contestants.csv")
    final = full.rename(columns={"id_contestant": "contestant_id"})

    # Raw tables
    dup = parts.duplicated(["contestant_id", "competition_id"]).sum()
    check("one row per contestant per edition", dup == 0, f"{dup} duplicates")
    bad = ((parts.total < 0) | (parts.total > parts.max_total)).sum()
    check("0 <= total <= maximum", bad == 0, f"{bad} rows outside")
    sums = parts.problem_scores.map(problem_sum)
    has_scores = sums.notna()
    diff = parts[has_scores & (sums != parts.total)]
    check("problem scores add up to the total", len(diff) <= 5,
          f"{len(diff)} of {has_scores.sum()} rows differ ({', '.join(diff.competition_id)})")
    n = parts.groupby("competition_id").size()
    check("participant counts match competitions.csv",
          comps.set_index("competition_id").n_participants.sort_index().equals(n.sort_index()))
    check("no participation without a country", parts.country.notna().all())
    span = parts.groupby("contestant_id").year.agg(lambda y: y.max() - y.min())
    check("no contestant career longer than 7 years", (span <= 7).all(), f"{(span > 7).sum()} contestants")
    partial = parts.competition_id.map(comps.set_index("competition_id").coverage) != "full"
    check("no percentile on partially published editions", parts[partial].rank_pct.isna().all(),
          f"{partial.sum()} rows in {parts[partial].competition_id.nunique()} editions")

    contestants = raw["contestants"]
    check("contestants.csv matches participations",
          len(contestants) == parts.contestant_id.nunique() and contestants.n_events.sum() == len(parts))
    check("countries.csv covers every country with a continent",
          set(parts.country) == set(raw["countries"].country) and raw["countries"].continent.notna().all())

    # Final tables
    imo = parts[(parts.source == "IMO") & (parts.year >= final.id_year.min())]
    check("final table has every IMO participation", len(final) == len(imo), f"{len(final)} vs {len(imo)}")
    check("one row per contestant per IMO", not final.duplicated(KEY).any())
    check("compact table = same rows, subset of columns",
          set(compact.columns) <= set(full.columns) and compact.equals(full[compact.columns]))
    documented = documented_columns()
    undocumented = [c for table in [*raw.values(), full] for c in table.columns if c not in documented]
    check("every column is in docs/data_dictionary.md", not undocumented, ", ".join(undocumented[:10]))

    # Leakage: recount prior events with a vectorised join
    before = comps.set_index("competition_id").same_year_before_imo
    ev = parts.assign(before=parts.competition_id.map(before))[["contestant_id", "year", "source", "before"]]
    joined = final[KEY].merge(ev, on="contestant_id")
    prior = joined[(joined.year < joined.id_year) | ((joined.year == joined.id_year) & joined.before)]
    counts = prior.groupby(KEY).size()
    expected = counts.reindex(pd.MultiIndex.from_frame(final[KEY])).fillna(0)
    mismatch = (expected.values != final.hist_n_events.values).sum()
    check("prior event counts (no future events)", mismatch == 0, f"{mismatch} rows differ")
    late = prior[(prior.year == prior.id_year) & prior.source.isin(["MEMO", "PAMO", "EMO", "IMO"])]
    check("no same-year MEMO/PAMO/EMO/IMO in history", late.empty, f"{len(late)} events")
    check("no history -> NaN scores, not 0",
          final[final.hist_n_events == 0][["hist_mean_pct", "hist_years_active"]].isna().all().all())
    check("imo_attempt = earlier IMOs + 1", (final.imo_attempt == final.imo_n_prior + 1).all())

    bad_status = []
    for c in OTHER:
        took_part = final[f"{c}_n"] > 0
        if not ((final[f"{c}_status"] == "participated") == took_part).all():
            bad_status.append(f"{c}: status vs count")
        if final.loc[took_part, f"{c}_best_award"].isna().any() or final.loc[~took_part, f"{c}_best_award"].notna().any():
            bad_status.append(f"{c}: award vs count")
        if (final.loc[final[f"{c}_status"] == "not_participated", f"{c}_missing_editions"] != 0).any():
            bad_status.append(f"{c}: not_participated with missing editions")
    check("<competition>_status consistent with counts and coverage", not bad_status, "; ".join(bad_status))
    per_year = final.groupby("id_year").target_z.mean().abs().max()
    check("target_z centred in every year", per_year < 0.05, f"max |mean| {per_year:.3f}")

    # Country features recomputed for a few years
    imo_all = parts[parts.source == "IMO"].assign(a=parts.award.map(AWARD_CODE))
    worst = {"mean": 0.0, "medal": 0.0, "modal": 0}
    for year in CHECK_YEARS:
        w = imo_all[(imo_all.year >= year - 3) & (imo_all.year < year)].groupby("country")
        ref = pd.DataFrame({"mean": w.score_pct.mean(), "medal": w.a.agg(lambda a: (a >= 2).mean()),
                            "modal": w.a.agg(lambda a: a.mode().max())})
        got = final[final.id_year == year].groupby("id_country")[
            ["country_imo_mean_pct_3y", "country_medal_rate_3y", "country_modal_award_3y"]].first()
        got.columns = ["mean", "medal", "modal"]
        both = got.join(ref, rsuffix="_ref").dropna()
        worst["mean"] = max(worst["mean"], (both["mean"] - both.mean_ref).abs().max())
        worst["medal"] = max(worst["medal"], (both.medal - both.medal_ref).abs().max())
        worst["modal"] += int((both.modal != both.modal_ref).sum())
    check("country features match a direct recomputation",
          worst["mean"] < 1e-9 and worst["medal"] < 1e-9 and worst["modal"] == 0,
          f"max |diff| mean {worst['mean']:.1e}, medal {worst['medal']:.1e}, modal mismatches {worst['modal']}")

    # Targets agree with the raw table
    t = final.merge(parts[parts.source == "IMO"].rename(columns={"year": "id_year"}), on=KEY)
    p_sum = t[[f"target_p{i}" for i in range(1, 7)]].sum(axis=1)
    check("targets equal the raw IMO results",
          (t.target_total == t.total).all() and (t.target_award == t.award).all() and (p_sum == t.total).all())

    lines = ["Dataset validation", ""]
    for name, ok, detail in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    report = "\n".join(lines) + "\n"
    (ROOT / "data" / "final" / "validation_report.txt").write_text(report)
    print(report)
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


if __name__ == "__main__":
    main()
