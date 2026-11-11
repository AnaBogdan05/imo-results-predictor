"""Crawl official IMO individual results from imo-official.org.

One page per year: /results/individual/year/<year>/ lists every contestant with
country, rank, award, total and the six problem scores. Besides the HTML table,
the page embeds the same rows as JSON in
<script type="application/json" data-results-individual-year-contestants>,
which we parse because the table layout changes between years (e.g. 2005 has an
extra special-prize column). The official contestant id is stored by
moresults.org as people[*].source_ids.imo and is used for linking.

robots.txt (checked 2026-10-20): no Disallow rules, no content-signal directives.

Output: data/cache/imo_official_individual.csv (contains names; not published).
"""
import argparse
import json
import re

import pandas as pd

from http_cache import CACHE_DIR, fetch

BASE = "https://www.imo-official.org"
OUTPUT = CACHE_DIR / "imo_official_individual.csv"

DATA_RE = re.compile(
    r'<script type="application/json" data-results-individual-year-contestants>(.*?)</script>',
    re.S,
)


def parse_year(year: int, page: str) -> list[dict]:
    rows = []
    for item in json.loads(DATA_RE.search(page).group(1)):
        scores = item["scores"] or [None] * 6
        rows.append({
            "year": year,
            "imo_contestant_id": item["contestantId"],
            "name": " ".join(filter(None, [item["name"], item["surname"]])) or None,
            "country_code": item["countryCode"],
            "rank": item["rank"],
            "award": item["award"],
            "total": item["total"],
            **{f"p{i + 1}": s for i, s in enumerate(scores)},
            "is_anonymous": item["isAnonymous"],
            "is_result_anomaly": item["isResultAnomaly"],
            "is_jury_decision_award": item["isJuryDecisionAward"],
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-year", type=int, default=2000)
    parser.add_argument("--last-year", type=int, default=2026)
    args = parser.parse_args()

    rows = []
    for year in range(args.first_year, args.last_year + 1):
        page = fetch(f"{BASE}/results/individual/year/{year}/").decode("utf-8")
        year_rows = parse_year(year, page)
        print(f"IMO {year}: {len(year_rows)} contestants")
        rows.extend(year_rows)

    df = pd.DataFrame(rows).astype({"imo_contestant_id": "Int64", "rank": "Int64", "total": "Int64"})
    df.to_csv(OUTPUT, index=False)
    print(f"saved {len(df)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
