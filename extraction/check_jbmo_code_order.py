"""Check that JBMO 2018/2020 contestant codes follow the order of the hms.gr team pages.

parse_jbmo_results.py assumes that code ROM2 is the second name on Romania's team page.
If that is right, a contestant's JBMO score should predict their later IMO results
better than when names are shuffled within each team (which keeps the country effect
but breaks the individual link). This permutation test compares the two.

Input:  data/cache/jbmo_hms_teams.csv, data/cache/jbmo2018_hms_results.csv,
        data/sources/jbmo/jbmo2020-overall.pdf, data/cache/moresults.org/olympiad_data.json.gz
Output: data/raw/jbmo_code_order_check.txt (no names)
"""
import gzip
import json

import numpy as np
import pandas as pd

from build_raw_tables import CACHE, RAW, name_key
from parse_jbmo_results import HMS_TEAMS, ROW_2020, SOURCES, hms_teams, pdf_lines

N_PERMUTATIONS = 2000


def later_imo_percentiles() -> pd.DataFrame:
    data = json.load(gzip.open(CACHE / "moresults.org" / "olympiad_data.json.gz"))
    comps, people = data["competitions"], data["people"]
    rows = [(name_key(people[p["person_id"]]["name"]), (p["country_id"] or "")[8:].upper(),
             comps[p["competition_id"]]["year"], p["total"])
            for p in data["participations"].values() if comps[p["competition_id"]]["source"] == "IMO"]
    imo = pd.DataFrame(rows, columns=["key", "country", "year", "total"])
    imo["pct"] = imo.groupby("year").total.rank(pct=True)
    return imo


def results(year: int) -> pd.DataFrame:
    if year == 2020:
        df = pd.DataFrame([m.groupdict() for line in pdf_lines(SOURCES / "jbmo2020-overall.pdf")
                           if (m := ROW_2020.match(line))])
        df["team"] = df.team.str.strip()
    else:
        df = pd.read_csv(CACHE / "jbmo2018_hms_results.csv")
        labels = {t.lower(): t for t in hms_teams(2018).team.unique()} | {"saudia arabia": "Saudi Arabia"}
        df["team"] = df.code.str.replace(r"\d+$", "", regex=True).str.lower().map(labels)
        df["number"] = df.code.str.extract(r"(\d+)$")[0]
    return df.assign(number=df.number.astype(int), total=df.total.astype(int))[["team", "number", "total"]]


def correlation(res: pd.DataFrame, teams: pd.DataFrame, later: pd.Series) -> tuple[float, int]:
    m = res.merge(teams, on=["team", "number"])
    m["later"] = [later.get((k, c)) for k, c in zip(m.key, m.country)]
    m = m.dropna(subset=["later"])
    return m.total.corr(m.later, method="spearman"), len(m)


def main() -> None:
    imo = later_imo_percentiles()
    rng = np.random.default_rng(0)
    lines = ["JBMO contestant codes vs order on the hms.gr team pages",
             f"Spearman correlation between the JBMO total and the best later IMO percentile,",
             f"real mapping vs names shuffled within each team ({N_PERMUTATIONS} permutations).", ""]
    for year in [2018, 2020]:
        teams = hms_teams(year).assign(key=lambda d: d.name.map(name_key), country=lambda d: d.team.map(HMS_TEAMS))
        later = imo[imo.year > year].groupby(["key", "country"]).pct.max()
        res = results(year)
        real, n = correlation(res, teams, later)
        null = []
        for _ in range(N_PERMUTATIONS):
            shuffled = teams.assign(number=teams.groupby("team").number.transform(lambda s: rng.permutation(s.values)))
            null.append(correlation(res, shuffled, later)[0])
        null = np.array(null)
        lines.append(f"JBMO {year}: {n} contestants found at a later IMO; real {real:.3f}; "
                     f"shuffled mean {null.mean():.3f}, 95th percentile {np.percentile(null, 95):.3f}; "
                     f"p = {(null >= real).mean():.3f}")
    report = "\n".join(lines) + "\n"
    (RAW / "jbmo_code_order_check.txt").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
