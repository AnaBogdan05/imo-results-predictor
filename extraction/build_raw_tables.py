"""Join the crawled sources into the two raw tables described in the proposal.

Inputs (produced by the crawlers, in data/cache/):
  moresults.org/olympiad_data.json.gz   all olympiads, people linked across competitions
  imo_official_individual.csv           official IMO results 2000-2026
  jbmo_extra_results.csv                JBMO 2018-2020 and 2022 from organisers (parse_jbmo_results.py)
  extraction/competition_calendar.csv   month of each competition (for time ordering)

Outputs (in data/raw/, no names):
  participations.csv   one row per contestant per individual competition edition
  competitions.csv     one row per individual competition edition
  contestants.csv      one row per contestant: career summary
  countries.csv        one row per country: name, continent, participation summary
  linkage_report.txt   agreement between imo-official.org and moresults.org,
                       repaired person links, coverage gaps

IMO rows from 2000 on come from imo-official.org; earlier IMOs and all other
competitions come from moresults.org. moresults.org sometimes splits one person
into several profiles when the name is written in a different order or spelling
("Gualdi Pietro" / "Pietro Gualdi"); these are merged back (merge_split_people).
Contestants are identified by a salted hash of the person id, so the published
tables contain no names.
"""
import gzip
import hashlib
import json
import re
import secrets
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
RAW = ROOT / "data" / "raw"

AWARDS = {"honourable_mention": "hm", "hm": "hm", "bronze": "bronze", "silver": "silver", "gold": "gold"}
# IMO 2022-2025: the Russian team took part without a flag; neither site lists a country.
NEUTRAL_TEAM = {2022: "country-rus", 2023: "country-rus", 2024: "country-rus", 2025: "country-rus"}
# Longest plausible olympiad career, first to last event (e.g. JBMO at 13, IMO at 19).
MAX_CAREER_YEARS = 7
# JBMO editions missing on moresults.org, added from the organisers' results.
EXTRA_JBMO_EDITIONS = {
    "jbmo-2018": {"edition": 22, "coverage": "medallists only", "source": "hms.gr"},
    "jbmo-2019": {"edition": 23, "coverage": "medallists only, no scores", "source": "cms.org.cy (PDF)"},
    "jbmo-2020": {"edition": 24, "coverage": "full", "source": "hms.gr (PDF)"},
    "jbmo-2022": {"edition": 26, "coverage": "medallists and honourable mentions",
                  "source": "jbmo2022.pmf.unsa.ba (PDF)"},
}


def award_label(series: pd.Series) -> pd.Series:
    return series.map(AWARDS).fillna("none")


def pseudonymizer():
    salt_file = CACHE / "pseudonym_salt.txt"
    if not salt_file.exists():
        salt_file.write_text(secrets.token_hex(16))
    salt = salt_file.read_text().strip()
    return lambda person_id: "c" + hashlib.sha256((salt + person_id).encode()).hexdigest()[:10]


def load_moresults():
    data = json.load(gzip.open(CACHE / "moresults.org" / "olympiad_data.json.gz"))
    competitions = pd.DataFrame(data["competitions"].values())
    competitions = competitions[competitions.competition_type == "individual"]
    participations = pd.DataFrame(data["participations"].values())
    participations = participations[participations.competition_id.isin(competitions.id)]
    people = pd.DataFrame(data["people"].values()).set_index("id")
    country_names = {c["code"].upper(): c["name"] for c in data["countries"].values()}
    return competitions, participations, people, country_names


def name_key(name: str) -> str:
    """Name without accents, case, punctuation or word order."""
    ascii_name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(sorted(re.findall(r"[a-z]+", ascii_name)))


def split_overmerged_people(rows: pd.DataFrame, report: list[str]) -> pd.Series:
    """Split profiles whose events span more than MAX_CAREER_YEARS.

    Such a profile joins different people with the same name (e.g. one Takuya Inoue
    at IMO 2007 and another at IMO 2014-2016). Events are cut wherever more than
    MAX_GAP_YEARS separate consecutive years; the latest part keeps the original id.
    """
    max_gap_years = 3
    person_ids = rows.person_id.copy()
    span = rows.groupby("person_id").year.agg(lambda y: y.max() - y.min())
    n_split = 0
    for pid in span[span > MAX_CAREER_YEARS].index:
        years = rows.loc[rows.person_id == pid, "year"]
        ordered = sorted(set(years))
        cuts = [b for a, b in zip(ordered, ordered[1:]) if b - a > max_gap_years]
        if not cuts:
            continue
        n_split += 1
        part = years.map(lambda y: sum(y >= c for c in cuts))
        last = part.max()
        person_ids[years.index] = [pid if k == last else f"{pid}#part{k}" for k in part]
    report += [
        "",
        f"Profiles covering more than {MAX_CAREER_YEARS} years, split at gaps over {max_gap_years} years: {n_split}",
    ]
    return person_ids


def merge_split_people(rows: pd.DataFrame, people: pd.DataFrame, report: list[str]) -> pd.Series:
    """Map each person id to a canonical id, merging profiles of the same person.

    Profiles are merged when they share the normalised name and a country, never
    meet in the same competition edition, and all their events fit in
    MAX_CAREER_YEARS. A group that breaks either rule is left unmerged.
    """
    known = rows[rows.person_id.isin(people.index)]
    known = known.assign(name=known.person_id.map(people.name).map(name_key))
    canonical = {}
    merged_groups, rejected = [], {"same edition": 0, "career too long": 0}
    for _, group in known.groupby(["name", "country_id"]):
        ids = sorted(set(group.person_id))
        if len(ids) < 2:
            continue
        if group.competition_id.duplicated().any():
            rejected["same edition"] += 1
            continue
        if group.year.max() - group.year.min() > MAX_CAREER_YEARS:
            rejected["career too long"] += 1
            continue
        target = canonical.get(ids[0], ids[0])
        for pid in ids:
            canonical[pid] = target
        merged_groups.append(group.assign(merged_into=target))

    audit = pd.concat(merged_groups)
    audit["display_name"] = audit.person_id.map(people.name)
    audit.sort_values(["merged_into", "year"])[
        ["merged_into", "person_id", "display_name", "country_id", "competition_id", "total"]
    ].to_csv(CACHE / "person_merges.csv", index=False)  # has names: stays in the cache

    report += [
        "",
        "Person profiles split on moresults.org (same name up to order/accents, same country):",
        f"  groups merged:                                 {len(merged_groups)}",
        f"  profiles merged into another:                  {sum(k != v for k, v in canonical.items())}",
        f"  participations whose person changed:          {audit.person_id.ne(audit.merged_into).sum()}",
        f"  groups left unmerged (two people in one edition): {rejected['same edition']}",
        f"  groups left unmerged (events > {MAX_CAREER_YEARS} years apart): {rejected['career too long']}",
    ]
    return rows.person_id.map(lambda pid: canonical.get(pid, pid))


def add_extra_jbmo_editions(rows: pd.DataFrame, competitions: pd.DataFrame, people: pd.DataFrame,
                            report: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append the JBMO editions missing on moresults.org, linked to existing people.

    A row joins an existing person when exactly one person has the same normalised
    name and country and the joined career stays within MAX_CAREER_YEARS; otherwise
    it starts a new person.
    """
    pdf = pd.read_csv(CACHE / "jbmo_extra_results.csv")
    known = rows[rows.person_id.isin(people.index)][["person_id", "country_id", "year"]]
    known = known.assign(name=known.person_id.map(people.name).map(name_key))
    span = known.groupby("person_id").year.agg(["min", "max"])
    candidates = known.drop_duplicates(["person_id", "country_id"]).groupby(["name", "country_id"]).person_id.agg(list)

    person_ids, linked = [], 0
    for i, row in pdf.iterrows():
        country_id = "country-" + row.country.lower()
        found = candidates.get((name_key(row["name"]), country_id), [])
        if len(found) == 1:
            first, last = span.loc[found[0]]
            if max(last, row.year) - min(first, row.year) <= MAX_CAREER_YEARS:
                person_ids.append(found[0])
                linked += 1
                continue
        person_ids.append(f"jbmo-extra-{row.year}-{i}")
    pdf["person_id"] = person_ids

    new_rows = pd.DataFrame({
        "competition_id": pdf.competition_id,
        "person_id": pdf.person_id,
        "country_id": "country-" + pdf.country.str.lower(),
        "problem_scores": pdf[["p1", "p2", "p3", "p4"]].astype("Int64").astype(object)
                          .where(pdf[["p1", "p2", "p3", "p4"]].notna(), None).values.tolist(),
        "total": pdf.total,
        "award": pdf.award,
        "data_source": pdf.competition_id.map(lambda cid: EXTRA_JBMO_EDITIONS[cid]["source"]),
    })
    new_comps = pd.DataFrame([
        {"id": cid, "source": "JBMO", "year": int(cid[-4:]), "edition": meta["edition"],
         "host_country_id": None, "competition_type": "individual", "num_problems": 4,
         "max_score_per_problem": 10, "coverage": meta["coverage"]}
        for cid, meta in EXTRA_JBMO_EDITIONS.items()
    ])
    report += [
        "",
        "JBMO editions added from the organisers' results (missing on moresults.org):",
        *[f"  {cid}: {(pdf.competition_id == cid).sum()} rows ({meta['coverage']}; {meta['source']})"
          for cid, meta in EXTRA_JBMO_EDITIONS.items()],
        f"  linked to an existing person:                  {linked} of {len(pdf)}",
    ]
    competitions = pd.concat([competitions.assign(coverage="full"), new_comps], ignore_index=True)
    return pd.concat([rows, new_rows], ignore_index=True), competitions


def coverage_gaps(comp: pd.DataFrame, rows: pd.DataFrame, report: list[str]) -> None:
    report += ["", "Coverage (missing editions within each competition's range, after adding PDFs):"]
    for source, group in comp.groupby("source"):
        years = set(group.year)
        missing = sorted(set(range(min(years), max(years) + 1)) - years)
        report.append(f"  {source:5} {min(years)}-{max(years)}  missing: {missing or 'none'}")
    per_country = rows[rows.source == "APMO"].groupby(["competition_id", "country"]).size().max()
    report.append(f"  APMO publishes only the top {per_country} contestants per country; "
                  "APMO percentiles are relative to them")


def official_imo_rows(mo_imo: pd.DataFrame, report: list[str]) -> pd.DataFrame:
    """Official IMO rows with the moresults person id attached."""
    off = pd.read_csv(CACHE / "imo_official_individual.csv")
    off["imo_contestant_id"] = off.imo_contestant_id.astype(str)
    mo_imo = mo_imo.assign(year=mo_imo.competition_id.str[4:].astype(int))
    mo_imo = mo_imo[mo_imo.year >= off.year.min()]

    merged = off.merge(
        mo_imo[["year", "source_contestant_id", "person_id", "country_id", "total", "award"]],
        left_on=["year", "imo_contestant_id"], right_on=["year", "source_contestant_id"],
        how="left", suffixes=("", "_mo"),
    )
    by_id = merged.person_id.notna()

    # imo-official country codes (e.g. UNK, GER) -> moresults country ids (gbr, deu).
    country_map = dict(merged[by_id & merged.country_code.notna()][["country_code", "country_id"]].values)

    # Rows whose ids differ between the sites: match on year, country and total.
    matched = set(zip(merged.year[by_id], merged.source_contestant_id[by_id]))
    leftover = mo_imo[[k not in matched for k in zip(mo_imo.year, mo_imo.source_contestant_id)]]
    for i in merged.index[~by_id]:
        row = merged.loc[i]
        cand = leftover[(leftover.year == row.year) & (leftover.total == row.total)
                        & (leftover.country_id == country_map.get(row.country_code))]
        if len(cand) == 1:
            merged.loc[i, ["person_id", "country_id"]] = cand.iloc[0][["person_id", "country_id"]].values
            leftover = leftover.drop(cand.index)
    by_fallback = merged.person_id.notna() & ~by_id

    both = merged[by_id]
    report += [
        f"imo-official.org rows (IMO {off.year.min()}-{off.year.max()}): {len(off)}",
        f"  linked to moresults by contestant id:          {by_id.sum()}",
        f"  linked by year + total (ids differ):           {by_fallback.sum()}",
        f"  not linked (kept, no cross-competition history): {merged.person_id.isna().sum()}",
        f"  total score disagreements (id-linked rows):    {(both.total != both.total_mo).sum()}",
        f"  award disagreements (id-linked rows):          "
        f"{(award_label(both.award) != award_label(both.award_mo)).sum()}",
        f"  official ids at more than one IMO:             {(both.groupby('imo_contestant_id').year.nunique() > 1).sum()}",
        f"    of which split over several moresults people: {(both.groupby('imo_contestant_id').person_id.nunique() > 1).sum()}",
        f"  moresults people joining several official ids:  {(both.groupby('person_id').imo_contestant_id.nunique() > 1).sum()}",
    ]

    # Unlinked official rows get their own person id.
    merged["person_id"] = merged.person_id.fillna("imo-official-" + merged.imo_contestant_id)
    merged["country_id"] = merged.country_id.fillna(merged.country_code.map(country_map))
    neutral = merged.country_id.isna() & merged.country_code.isna()
    merged.loc[neutral, "country_id"] = merged.loc[neutral, "year"].map(NEUTRAL_TEAM)
    report += [
        f"  rows without a flag assigned to the neutral team: {neutral.sum()} (Russia, 2022-2025)",
        f"  rows without any country:                      {merged.country_id.isna().sum()}",
    ]

    return pd.DataFrame({
        "competition_id": "imo-" + merged.year.astype(str),
        "person_id": merged.person_id,
        "country_id": merged.country_id,
        "problem_scores": merged[[f"p{i}" for i in range(1, 7)]].values.tolist(),
        "total": merged.total,
        "award": award_label(merged.award),
        "data_source": "imo-official.org",
    })


def contestant_table(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per contestant. gender_proxy is 'female' for anyone who took part in
    EGMO (a competition for girls) and 'unknown' otherwise, never 'male'."""
    order = {"none": 0, "hm": 1, "bronze": 2, "silver": 3, "gold": 4}
    imo = rows[rows.source == "IMO"]
    g = rows.groupby("contestant_id")
    table = pd.DataFrame({
        "country": g.country.agg(lambda c: c.mode().iloc[0]),
        "n_countries": g.country.nunique(),
        "first_year": g.year.min(),
        "last_year": g.year.max(),
        "n_events": g.size(),
        "n_imo": imo.groupby("contestant_id").size(),
        "competitions": g.source.agg(lambda s: ";".join(sorted(set(s)))),
        "best_imo_award": imo.assign(code=imo.award.map(order)).sort_values("code")
                            .groupby("contestant_id").award.last(),
        "gender_proxy": g.source.agg(lambda s: "female" if (s == "EGMO").any() else "unknown"),
    })
    table["n_imo"] = table.n_imo.fillna(0).astype(int)
    return table.reset_index().sort_values(["first_year", "contestant_id"])


def country_table(rows: pd.DataFrame, country_names: dict) -> pd.DataFrame:
    continents = pd.read_csv(ROOT / "extraction" / "country_continents.csv").set_index("country").continent
    imo = rows[rows.source == "IMO"]
    g = rows.groupby("country")
    table = pd.DataFrame({
        "name": g.size().index.map(country_names),
        "continent": g.size().index.map(continents),
        "first_year": g.year.min(),
        "last_year": g.year.max(),
        "n_imo_years": imo.groupby("country").year.nunique(),
        "n_contestants": g.contestant_id.nunique(),
        "competitions": g.source.agg(lambda s: ";".join(sorted(set(s)))),
    }, index=g.size().index)
    table["n_imo_years"] = table.n_imo_years.fillna(0).astype(int)
    return table.rename_axis("country").reset_index()


def main() -> None:
    report: list[str] = []
    pseudonym = pseudonymizer()
    competitions, parts, people, country_names = load_moresults()
    calendar = pd.read_csv(ROOT / "extraction" / "competition_calendar.csv")

    is_imo = parts.competition_id.str.startswith("imo-")
    official = official_imo_rows(parts[is_imo], report)
    official_years = set(official.competition_id)
    mo_rows = parts[~parts.competition_id.isin(official_years)].assign(
        award=lambda d: award_label(d.award), data_source="moresults.org")
    rows = pd.concat([mo_rows[official.columns], official], ignore_index=True)
    rows["year"] = rows.competition_id.map(competitions.set_index("id").year)
    rows["person_id"] = split_overmerged_people(rows, report)
    rows["person_id"] = merge_split_people(rows, people, report)
    rows, competitions = add_extra_jbmo_editions(rows, competitions, people, report)
    rows = rows.drop(columns="year")

    comp = competitions.rename(columns={"id": "competition_id"}).merge(calendar, on="source", how="left")
    comp["max_total"] = comp.num_problems * comp.max_score_per_problem
    rows = rows.merge(comp[["competition_id", "source", "year", "typical_month", "max_total"]], on="competition_id")

    rows = rows[rows.total.notna() | rows.competition_id.isin(EXTRA_JBMO_EDITIONS)].copy()
    rows["score_pct"] = rows.total / rows.max_total
    rows["rank_pct"] = rows.groupby("competition_id").total.rank(pct=True, method="average")
    # A percentile among medallists only would be inflated: leave it missing.
    partial = rows.competition_id.map(competitions.set_index("id").coverage) != "full"
    rows.loc[partial, "rank_pct"] = float("nan")
    rows["n_problems_scored"] = rows.problem_scores.map(lambda s: sum(x is not None and x == x for x in s))
    rows["problem_scores"] = rows.problem_scores.map(
        lambda s: ";".join("" if x is None or x != x else str(int(x)) for x in s).rstrip(";"))
    rows["contestant_id"] = rows.person_id.map(pseudonym)
    rows["country"] = rows.country_id.str.replace("country-", "", regex=False).str.upper()

    cutoffs = (rows[rows.award.isin(["gold", "silver", "bronze"])]
               .groupby(["competition_id", "award"]).total.min().unstack())
    stats = rows.groupby("competition_id").agg(
        n_participants=("total", "size"), n_countries=("country", "nunique"),
        mean_score_pct=("score_pct", "mean"))
    comp = (comp.set_index("competition_id")
            .join(stats).join(cutoffs.add_suffix("_cutoff"))
            .reset_index())
    comp["host_country"] = comp.host_country_id.str.replace("country-", "", regex=False).str.upper()
    coverage_gaps(comp, rows, report)

    RAW.mkdir(parents=True, exist_ok=True)
    part_cols = ["contestant_id", "competition_id", "source", "year", "typical_month", "country",
                 "problem_scores", "total", "max_total", "score_pct", "rank_pct", "award", "data_source"]
    rows.sort_values(["year", "typical_month", "source", "total"], ascending=[True, True, True, False])[
        part_cols].to_csv(RAW / "participations.csv", index=False)
    comp_cols = ["competition_id", "source", "year", "edition", "coverage", "typical_month", "same_year_before_imo",
                 "first_held", "host_country", "num_problems", "max_score_per_problem", "max_total", "n_participants",
                 "n_countries", "mean_score_pct", "gold_cutoff", "silver_cutoff", "bronze_cutoff"]
    comp.sort_values(["year", "typical_month"])[comp_cols].to_csv(RAW / "competitions.csv", index=False)

    contestants = contestant_table(rows)
    contestants.to_csv(RAW / "contestants.csv", index=False)
    countries = country_table(rows, country_names)
    countries.to_csv(RAW / "countries.csv", index=False)

    report += ["", f"participations.csv: {len(rows)} rows, {rows.contestant_id.nunique()} contestants",
               f"competitions.csv:   {len(comp)} editions",
               f"contestants.csv:    {len(contestants)} contestants",
               f"countries.csv:      {len(countries)} countries",
               rows.groupby("source").size().rename("rows").to_string()]
    (RAW / "linkage_report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
