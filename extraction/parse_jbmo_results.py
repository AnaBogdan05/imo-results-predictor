"""Parse JBMO editions missing from moresults.org: 2018, 2019, 2020, 2022.

Official result PDFs are kept in data/sources/jbmo/ (not committed: they contain names);
their origin is listed in data/sources/README.md. JBMO 2018 and 2020 come from hms.gr
(crawl_jbmo_hms.py).

  2018  hms.gr medal tables: code (e.g. ROMANIA2), four problem scores, total, medal;
        medallists only
  2019  jbmo2019-medals-{member,guest}-countries.pdf: name, country, medal; medallists
        only, no scores
  2020  jbmo2020-overall.pdf: code (e.g. ROM2), four problem scores, total, for every
        contestant; medals from the cut-offs in jbmo2020-medals.pdf
  2022  jbmo2022-medals.pdf: rank, name, four problem scores, total, medal; medallists
        and honourable mentions

In 2018 and 2020 a code's number is the contestant's position on the team page of
hms.gr: ROM2 is the second name listed for Romania. This mapping was checked against
later IMO results (check_jbmo_code_order.py -> data/raw/jbmo_code_order_check.txt).

Output: data/cache/jbmo_extra_results.csv (contains names; not published)
"""
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources" / "jbmo"
CACHE = ROOT / "data" / "cache"
OUTPUT = CACHE / "jbmo_extra_results.csv"

AWARDS = {"gold": "gold", "silver": "silver", "bronze": "bronze", "honorable mention": "hm"}
# Delegation codes and country names in the sources -> ISO codes used by moresults.org
COUNTRY_CODES = {"HEL": "GRC", "B&H": "BIH", "ROM": "ROU"}
COUNTRY_NAMES = {
    "AZERBAIJAN": "AZE", "BOSNIA&HERZEGOVINA": "BIH", "BULGARIA": "BGR", "CROATIA": "HRV",
    "CYPRUS": "CYP", "CYPRUS B": "CYP", "ECUADOR": "ECU", "FRA": "FRA", "FRANCE": "FRA",
    "GREECE": "GRC", "KAZAKHSTAN": "KAZ", "MOLDOVA": "MDA", "NORTH MACEDONIA": "MKD",
    "ROMANIA": "ROU", "SAUDI ARABIA": "SAU", "SERBIA": "SRB",
}
HMS_TEAMS = {
    "Albania": "ALB", "Azerbaijan": "AZE", "Bosnia and Herzegovina": "BIH", "Bulgaria": "BGR",
    "Croatia": "HRV", "Cyprus": "CYP", "Former Yugoslav Republic of Macedonia": "MKD",
    "France": "FRA", "Hellas": "GRC", "Indonesia": "IDN", "Kazakhstan": "KAZ", "Montenegro": "MNE",
    "North Macedonia": "MKD", "Philippines": "PHL", "Republic of Moldova": "MDA", "Romania": "ROU",
    "Saudi Arabia": "SAU", "Serbia": "SRB", "Tajikistan": "TJK", "Turkey": "TUR", "Turkmenistan": "TKM",
}

ROW_2019 = re.compile(r"^\s*\d+\s+(?P<name>.+?)\s{2,}(?P<country>[A-Z&' ]+?)\s+(?P<award>Gold|Silver|Bronze)\s*$")
ROW_2020 = re.compile(
    r"^\s*(?P<team>.+?)\s{2,}[A-Z]{3}(?P<number>\d)"
    r"\s+(?P<p1>\d+)\s+(?P<p2>\d+)\s+(?P<p3>\d+)\s+(?P<p4>\d+)\s+(?P<total>\d+)\s*(?P<award>GOLD|SILVER|BRONZE)?\s*$"
)
ROW_2022 = re.compile(
    r"^\s*(?P<rank>\d+)\s+(?P<code>[A-Z&]+)\d\s+(?P<name>.+?)"
    r"\s+(?P<p1>\d+)\s+(?P<p2>\d+)\s+(?P<p3>\d+)\s+(?P<p4>\d+)\s+(?P<total>\d+)"
    r"\s+(?P<award>Gold|Silver|Bronze|Honorable Mention)(?: and Special Prize)?\s*$"
)
PROBLEMS = ["p1", "p2", "p3", "p4"]


def pdf_lines(path: Path) -> list[str]:
    return subprocess.run(["pdftotext", "-layout", str(path), "-"],
                          capture_output=True, text=True, check=True).stdout.splitlines()


def hms_teams(year: int) -> pd.DataFrame:
    teams = pd.read_csv(CACHE / "jbmo_hms_teams.csv")
    return teams[teams.year == year][["team", "number", "name"]]


def parse_2018() -> list[dict]:
    results = pd.read_csv(CACHE / "jbmo2018_hms_results.csv")
    labels = {team.lower(): team for team in hms_teams(2018).team.unique()}
    labels["saudia arabia"] = "Saudi Arabia"  # spelling on the gold/silver/bronze pages
    results["team"] = results.code.str.replace(r"\d+$", "", regex=True).str.lower().map(labels)
    results["number"] = results.code.str.extract(r"(\d+)$")[0].astype(int)
    df = results.merge(hms_teams(2018), on=["team", "number"], how="left", validate="one_to_one")
    assert df.name.notna().all(), f"codes without a team-page name: {df[df.name.isna()].code.tolist()}"
    return [{"year": 2018, "name": r.name, "country": HMS_TEAMS[r.team],
             **{p: getattr(r, p) for p in PROBLEMS}, "total": r.total, "award": r.award,
             "source_file": "hms.gr/22jbmo2018"} for r in df.itertuples()]


def parse_2019() -> list[dict]:
    rows = []
    for path in sorted(SOURCES.glob("jbmo2019-medals-*.pdf")):
        for line in pdf_lines(path):
            m = ROW_2019.match(line)
            if m:
                rows.append({"year": 2019, "name": m["name"], "country": COUNTRY_NAMES[m["country"].strip()],
                             "award": AWARDS[m["award"].lower()], "source_file": path.name})
    return rows


def parse_2020() -> list[dict]:
    overall = pd.DataFrame([m.groupdict() for line in pdf_lines(SOURCES / "jbmo2020-overall.pdf")
                            if (m := ROW_2020.match(line))])
    overall[PROBLEMS + ["total", "number"]] = overall[PROBLEMS + ["total", "number"]].astype(int)
    overall["team"] = overall.team.str.strip()

    # The medals PDF wraps some rows over several lines; its readable rows give the cut-offs.
    medals = pd.DataFrame([m.groupdict() for line in pdf_lines(SOURCES / "jbmo2020-medals.pdf")
                           if (m := ROW_2020.match(line)) and m["award"]])
    cutoffs = medals.assign(total=medals.total.astype(int)).groupby("award").total.min()
    overall["award"] = "none"
    for award in ["BRONZE", "SILVER", "GOLD"]:
        overall.loc[overall.total >= cutoffs[award], "award"] = award.lower()

    df = overall.merge(hms_teams(2020), on=["team", "number"], how="left", validate="one_to_one")
    assert df.name.notna().all(), "codes without a team-page name"
    return [{"year": 2020, "name": r.name, "country": HMS_TEAMS[r.team],
             **{p: getattr(r, p) for p in PROBLEMS}, "total": r.total, "award": r.award,
             "source_file": "jbmo2020-overall.pdf"} for r in df.itertuples()]


def parse_2022() -> list[dict]:
    path = SOURCES / "jbmo2022-medals.pdf"
    rows = []
    for line in pdf_lines(path):
        m = ROW_2022.match(line)
        if m:
            code = m["code"]
            rows.append({"year": 2022, "name": " ".join(m["name"].split()),
                         "country": COUNTRY_CODES.get(code, code), "rank": int(m["rank"]),
                         **{p: int(m[p]) for p in PROBLEMS}, "total": int(m["total"]),
                         "award": AWARDS[m["award"].lower()], "source_file": path.name})
    return rows


def main() -> None:
    df = pd.DataFrame(parse_2018() + parse_2019() + parse_2020() + parse_2022())
    df.insert(0, "competition_id", "jbmo-" + df.year.astype(str))
    bad = df[df.total.notna() & (df[PROBLEMS].sum(axis=1) != df.total)]
    assert bad.empty, f"problem scores do not add up:\n{bad}"
    df.to_csv(OUTPUT, index=False)
    print(df.groupby(["competition_id", "award"]).size().unstack(fill_value=0).to_string())
    print(f"saved {len(df)} rows to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
