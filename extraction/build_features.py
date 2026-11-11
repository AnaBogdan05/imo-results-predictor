"""Build the final tables: one row per contestant per IMO, features from earlier events only.

An event counts as prior to IMO year Y if it took place in an earlier year, or in
year Y at a competition always held before the IMO (same_year_before_imo in
competition_calendar.csv: RMM, APMO, EGMO, BMO, JBMO).

Column prefixes (described in docs/data_dictionary.md):
  id_       identifiers                      not features
  target_   what is predicted                not features
  meta_     for error analysis only          not features
  imo_      the contestant's earlier IMOs
  hist_     all earlier international events
  jbmo_, bmo_, egmo_, rmm_, apmo_, memo_, pamo_   one block per other olympiad
  team_     the contestant's IMO team that year
  country_  the country's earlier results
  context_  the IMO edition itself

Missing history is explicit: counts are 0, scores are NaN, and <competition>_status
says why a competition is absent (not held, no data, or did not take part).

Input:  data/raw/participations.csv, competitions.csv, contestants.csv, countries.csv,
        extraction/competition_calendar.csv, extraction/imo_hosts.csv
Output: data/final/imo_contestants_full.csv   every column
        data/final/imo_contestants.csv        compact selection (COMPACT_COLUMNS)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FINAL = ROOT / "data" / "final"

FIRST_YEAR = 2008  # first IMO with linked regional olympiads (RMM, MEMO, BMO, PAMO)
# EMO (first held 2026) is kept in the raw table but cannot precede any IMO in range yet.
OTHER_COMPETITIONS = ["JBMO", "BMO", "EGMO", "RMM", "APMO", "MEMO", "PAMO"]
AWARD_CODE = {"none": 0, "hm": 1, "bronze": 2, "silver": 3, "gold": 4}
COUNTRY_WINDOW = 3
STATUS_WINDOW = 6  # years before the IMO in which a contestant could have taken part
ONLINE_IMOS = {2020, 2021}
KEY = ["contestant_id", "imo_year"]

COMPACT_COLUMNS = [
    "id_contestant", "id_year", "id_country",
    "target_total", "target_rank_pct", "target_z", "target_award",
    "meta_gender_proxy", "meta_continent",
    "imo_attempt", "imo_best_pct", "imo_last_award",
    "hist_n_events", "hist_n_other", "hist_best_award", "hist_mean_rank_pct", "hist_best_rank_pct", "hist_trend",
    "jbmo_best_rank_pct", "bmo_best_rank_pct", "egmo_best_rank_pct", "rmm_best_rank_pct", "apmo_best_rank_pct",
    "team_rank_by_history",
    "country_imo_mean_pct_3y", "country_medal_rate_3y", "country_modal_award_3y", "country_n_regional_3y",
    "context_is_host",
]


def problem_z_scores(imo: pd.DataFrame) -> pd.Series:
    """Mean over problems of the score standardised by year and problem (Berg, 2021)."""
    scores = imo.problem_scores.fillna("").str.split(";", expand=True).replace("", np.nan).astype(float)
    scores.index = imo.index
    by_year = scores.groupby(imo.year)
    z = (scores - by_year.transform("mean")) / by_year.transform("std", ddof=0).replace(0, np.nan)
    return z.mean(axis=1)


def slope(points: pd.DataFrame, x: str, y: str) -> pd.Series:
    """Least-squares slope of y on x per KEY group; NaN with fewer than two x values."""
    g = points.assign(xy=points[x] * points[y], xx=points[x] ** 2).groupby(KEY)
    n = g.size()
    cov = g.xy.sum() - g[x].sum() * g[y].sum() / n
    var = g.xx.sum() - g[x].sum() ** 2 / n
    return (cov / var.replace(0, np.nan)).where(n >= 2)


def best_and_last(events: pd.DataFrame, prefix: str) -> pd.DataFrame:
    g = events.groupby(KEY)
    last = events.sort_values("year").groupby(KEY).last()
    return pd.DataFrame({
        f"{prefix}_n": g.size(),
        f"{prefix}_best_pct": g.score_pct.max(),
        f"{prefix}_best_rank_pct": g.rank_pct.max(),
        f"{prefix}_best_award": g.award_code.max(),
        f"{prefix}_last_pct": last.score_pct,
        f"{prefix}_last_rank_pct": last.rank_pct,
        f"{prefix}_last_award": last.award_code,
        f"{prefix}_years_ago": g.imo_year.first() - g.year.max(),
    })


def history_features(prior: pd.DataFrame) -> pd.DataFrame:
    g = prior.groupby(KEY)
    by_key = [prior.contestant_id, prior.imo_year]
    yearly = prior.groupby(KEY + ["year"]).rank_pct.mean().dropna().reset_index()
    return pd.DataFrame({
        "hist_n_events": g.size(),
        "hist_n_other": (prior.source != "IMO").groupby(by_key).sum(),
        "hist_n_competitions": g.source.nunique(),
        "hist_n_same_year": (prior.year == prior.imo_year).groupby(by_key).sum(),
        "hist_n_medals": (prior.award_code >= 2).groupby(by_key).sum(),
        "hist_best_award": g.award_code.max(),
        "hist_mean_pct": g.score_pct.mean(),
        "hist_mean_rank_pct": g.rank_pct.mean(),
        "hist_best_rank_pct": g.rank_pct.max(),
        "hist_years_active": g.imo_year.first() - g.year.min(),
        "hist_trend": slope(yearly, "year", "rank_pct"),
    })


def imo_features(prior: pd.DataFrame) -> pd.DataFrame:
    imo = prior[prior.source == "IMO"]
    f = best_and_last(imo, "imo").rename(columns={"imo_n": "imo_n_prior"})
    f["imo_best_z"] = imo.groupby(KEY).z.max()
    return f


def competition_status(comps: pd.DataFrame, calendar: pd.DataFrame, years: range) -> pd.DataFrame:
    """Status of an absent competition, per (competition, IMO year).

    not_held          no edition in the window (competition did not exist yet)
    no_data           an edition in the window is missing or only partly published
    not_participated  all editions in the window are fully published

    missing_editions counts the editions of the window that are missing or partial.
    """
    cal = calendar.set_index("source")
    coverage = comps.set_index(["source", "year"]).coverage
    rows = []
    for source in OTHER_COMPETITIONS:
        for year in years:
            window = [y for y in range(year - STATUS_WINDOW, year + 1)
                      if y >= cal.first_held[source] and (y < year or cal.same_year_before_imo[source])]
            missing = sum(coverage.get((source, y)) != "full" for y in window)
            if not window:
                status = "not_held"
            elif missing == 0:
                status = "not_participated"
            else:
                status = "no_data"
            rows.append({"source": source, "imo_year": year, "absent_status": status, "missing_editions": missing})
    return pd.DataFrame(rows)


def competition_features(prior: pd.DataFrame, status: pd.DataFrame, keys: pd.DataFrame) -> pd.DataFrame:
    blocks = []
    for source in OTHER_COMPETITIONS:
        p = source.lower()
        f = best_and_last(prior[prior.source == source], p).drop(columns=[f"{p}_last_pct", f"{p}_last_rank_pct"])
        f = keys.join(f, on=KEY)
        by_year = status[status.source == source].set_index("imo_year")
        f.insert(2, f"{p}_status", np.where(f[f"{p}_n"].notna(), "participated", keys.imo_year.map(by_year.absent_status)))
        f.insert(3, f"{p}_missing_editions", keys.imo_year.map(by_year.missing_editions))
        f[f"{p}_n"] = f[f"{p}_n"].fillna(0).astype(int)
        blocks.append(f.set_index(KEY))
    return pd.concat(blocks, axis=1)


def team_features(df: pd.DataFrame) -> pd.DataFrame:
    by_team = [df.imo_year, df.country]
    strength = df.hist_best_rank_pct
    total = strength.fillna(0).groupby(by_team).transform("sum")
    known = strength.notna().groupby(by_team).transform("sum")
    others_known = known - strength.notna()
    return pd.DataFrame({
        "team_size": df.groupby(["imo_year", "country"]).contestant_id.transform("size"),
        "team_n_with_history": (df.hist_n_events > 0).groupby(by_team).transform("sum"),
        "team_rank_by_history": strength.fillna(-1).groupby(by_team).rank(ascending=False, method="min").astype(int),
        "team_others_mean_best_rank_pct": (total - strength.fillna(0)) / others_known.replace(0, np.nan),
    }, index=df.index)


def country_features(parts: pd.DataFrame, years: range) -> pd.DataFrame:
    imo = parts[parts.source == "IMO"]
    others = parts[parts.source.isin(OTHER_COMPETITIONS)]
    access_cols = [f"country_access_{c.lower()}" for c in OTHER_COMPETITIONS]
    rows = []
    for year in years:
        window = imo[(imo.year >= year - COUNTRY_WINDOW) & (imo.year < year)].groupby("country")
        recent = others[(others.year >= year - COUNTRY_WINDOW) & (others.year < year)]
        agg = pd.DataFrame({
            "country_imo_mean_pct_3y": window.score_pct.mean(),
            "country_imo_mean_pct_1y": imo[imo.year == year - 1].groupby("country").score_pct.mean(),
            "country_medal_rate_3y": window.award_code.agg(lambda a: (a >= 2).mean()),
            "country_gold_rate_3y": window.award_code.agg(lambda a: (a == 4).mean()),
            "country_modal_award_3y": window.award_code.agg(lambda a: a.mode().max()),
            "country_n_imo_3y": window.year.nunique(),
            "country_n_regional_3y": recent.groupby("country").source.nunique(),
        })
        access = recent.groupby(["country", "source"]).size().unstack(fill_value=0).gt(0).astype(int)
        access = access.reindex(columns=OTHER_COMPETITIONS, fill_value=0)
        access.columns = access_cols
        agg = agg.join(access, how="outer")
        rows.append(agg.rename_axis("country").reset_index().assign(imo_year=year))
    out = pd.concat(rows, ignore_index=True)
    fill = ["country_n_imo_3y", "country_n_regional_3y", *access_cols]
    out[fill] = out[fill].fillna(0).astype(int)
    return out


def main() -> None:
    parts = pd.read_csv(RAW / "participations.csv")
    comps = pd.read_csv(RAW / "competitions.csv")
    contestants = pd.read_csv(RAW / "contestants.csv").set_index("contestant_id")
    countries = pd.read_csv(RAW / "countries.csv").set_index("country")
    calendar = pd.read_csv(ROOT / "extraction" / "competition_calendar.csv")
    hosts = pd.read_csv(ROOT / "extraction" / "imo_hosts.csv").set_index("year").host_country

    parts["award_code"] = parts.award.map(AWARD_CODE)
    parts = parts.merge(comps[["competition_id", "same_year_before_imo"]], on="competition_id", how="left")
    is_imo = parts.source == "IMO"
    parts.loc[is_imo, "z"] = problem_z_scores(parts[is_imo])

    targets = parts[is_imo & (parts.year >= FIRST_YEAR)].rename(columns={"year": "imo_year"})
    years = range(FIRST_YEAR, parts.year.max() + 1)
    keys = targets[KEY].reset_index(drop=True)

    events = keys.merge(parts, on="contestant_id")
    prior = events[(events.year < events.imo_year)
                   | ((events.year == events.imo_year) & events.same_year_before_imo)]

    df = targets.reset_index(drop=True)
    df = df.join(imo_features(prior), on=KEY).join(history_features(prior), on=KEY)
    df = df.join(competition_features(prior, competition_status(comps, calendar, years), keys), on=KEY)
    df = pd.concat([df, team_features(df)], axis=1)
    df = df.merge(country_features(parts, years), on=["country", "imo_year"], how="left")

    counts = ["imo_n_prior", "hist_n_events", "hist_n_other", "hist_n_competitions", "hist_n_same_year",
              "hist_n_medals", "country_n_imo_3y", "country_n_regional_3y",
              *[f"country_access_{c.lower()}" for c in OTHER_COMPETITIONS]]
    df[counts] = df[counts].fillna(0).astype(int)

    scores = df.problem_scores.str.split(";", expand=True).astype(float)
    out = pd.DataFrame({
        "id_contestant": df.contestant_id,
        "id_year": df.imo_year,
        "id_country": df.country,
        "target_total": df.total.astype(int),
        "target_pct": df.score_pct,
        "target_rank_pct": df.rank_pct,
        "target_z": df.z,
        "target_award": df.award,
        "target_award_code": df.award_code,
        **{f"target_p{i + 1}": scores[i].astype("Int64") for i in range(6)},
        "meta_gender_proxy": df.contestant_id.map(contestants.gender_proxy),
        "meta_continent": df.country.map(countries.continent),
        "imo_attempt": df.imo_n_prior + 1,
    })
    blocks = {"imo", "hist", "team", "country", *[c.lower() for c in OTHER_COMPETITIONS]}
    features = [c for c in df.columns if "_" in c and c.split("_")[0] in blocks and c != "imo_year"]
    out = pd.concat([out, df[features]], axis=1)
    out["context_is_host"] = (df.country == df.imo_year.map(hosts)).astype(int)
    out["context_online"] = df.imo_year.isin(ONLINE_IMOS).astype(int)

    out = out.sort_values(["id_year", "target_total"], ascending=[True, False])
    FINAL.mkdir(parents=True, exist_ok=True)
    out.to_csv(FINAL / "imo_contestants_full.csv", index=False)
    out[COMPACT_COLUMNS].to_csv(FINAL / "imo_contestants.csv", index=False)
    print(f"imo_contestants_full.csv: {len(out)} rows x {out.shape[1]} columns")
    print(f"imo_contestants.csv:      {len(out)} rows x {len(COMPACT_COLUMNS)} columns")
    print(f"IMO {out.id_year.min()}-{out.id_year.max()}, "
          f"{(out.hist_n_events > 0).mean():.0%} with prior international history, "
          f"{(out.hist_n_other > 0).mean():.0%} with a prior non-IMO olympiad")


if __name__ == "__main__":
    main()
