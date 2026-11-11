"""Crawl team lists (and 2018 results) of JBMO 2018 and 2020 from hms.gr.

The Hellenic Mathematical Society hosted both editions. Their result tables identify
contestants by a code made of the team and a number (ROMANIA2 in 2018, ROM2 in 2020);
each team page lists the contestants in code order, so the k-th name on the team page
is contestant k. This crawler collects those lists, and the 2018 medal tables
(the 2020 results are in PDFs, read by parse_jbmo_results.py).

robots.txt (checked 2026-11-11): disallows only /wp-admin/.

Output: data/cache/jbmo_hms_teams.csv     year, team, team_page, number, name
        data/cache/jbmo2018_hms_results.csv  code, rank, p1-p4, total, award
(both contain names; not published)
"""
import html
import re

import pandas as pd

from http_cache import CACHE_DIR, fetch

EDITIONS = {2018: "https://www.hms.gr/22jbmo2018/", 2020: "https://www.hms.gr/24jbmo2020/"}
TEAMS_OUT = CACHE_DIR / "jbmo_hms_teams.csv"
RESULTS_2018_OUT = CACHE_DIR / "jbmo2018_hms_results.csv"

TEAM_LINK_RE = re.compile(r'<a[^>]+href="(team\w+\.htm)"[^>]*>(.*?)</a>', re.S | re.I)
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")


def decode(body: bytes) -> str:
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError:
        return body.decode("iso-8859-7")


def text(fragment: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", fragment)).replace("\xa0", " ").split())


def team_lists(year: int, base: str) -> list[dict]:
    rows = []
    for page, label in TEAM_LINK_RE.findall(decode(fetch(base + "countries.htm"))):
        team_html = decode(fetch(base + page))
        contestants = team_html[team_html.lower().find("contestant"):]
        names = [text(li) for li in re.split(r"<li>", contestants, flags=re.I)[1:]]
        names = [n for n in (re.split(r"\s*(?:</ul>|Back)", n)[0] for n in names) if n]
        for number, name in enumerate(names, start=1):
            rows.append({"year": year, "team": text(label).replace("(Guest)", "").strip(),
                         "team_page": page, "number": number, "name": name})
    return rows


def results_2018(base: str) -> list[dict]:
    rows = []
    for award in ["gold", "silver", "bronze"]:
        page = decode(fetch(base + f"{award}.htm"))
        for row in ROW_RE.findall(page):
            cells = [text(c) for c in CELL_RE.findall(row)]
            cells = [c for c in cells if c]
            if len(cells) == 7 and cells[2].isdigit():
                rows.append({"rank": cells[0], "code": cells[1],
                             **{f"p{i}": int(cells[1 + i]) for i in range(1, 5)},
                             "total": int(cells[6]), "award": award})
    return rows


def main() -> None:
    teams = pd.DataFrame([row for year, base in EDITIONS.items() for row in team_lists(year, base)])
    teams.to_csv(TEAMS_OUT, index=False)
    print(teams.groupby("year").agg(teams=("team", "nunique"), contestants=("name", "size")).to_string())

    results = pd.DataFrame(results_2018(EDITIONS[2018]))
    results.to_csv(RESULTS_2018_OUT, index=False)
    print(f"JBMO 2018 medallists: {len(results)} ({results.award.value_counts().to_dict()})")


if __name__ == "__main__":
    main()
