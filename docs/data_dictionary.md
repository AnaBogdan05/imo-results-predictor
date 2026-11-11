# Data dictionary

The dataset has two levels.

- **Raw tables** (`data/raw/`) are relational and close to the sources. Each has one row per
  natural unit: a participation, a competition edition, a contestant, a country.
- **Final tables** (`data/final/`) have one row per contestant per IMO (2008–2026) and are
  ready for modelling. `imo_contestants_full.csv` has every column; `imo_contestants.csv` is a
  compact selection of 29 columns for baselines and presentations.

No table contains names. Contestants are identified by a salted hash (`c` + 10 hex digits).
Countries use ISO 3166 alpha-3 codes, plus historical codes: `USS` (Soviet Union), `YUG`,
`SCG` (Serbia and Montenegro), `CSK`, `GDR`, `CIS`, and `NCY` (Northern Cyprus), `XKX` (Kosovo).

Conventions used throughout:

| Term | Meaning |
|---|---|
| `_pct` | score as a fraction of the maximum, 0–1 |
| `_rank_pct` | percentile rank within the edition, 0–1, ties averaged; 1 = best. Missing for editions published only in part (see `coverage`) |
| award code | 0 none, 1 honourable mention, 2 bronze, 3 silver, 4 gold |
| prior | events before the IMO: an earlier year, or the same year at RMM, APMO, EGMO, BMO or JBMO (always held before the IMO) |
| NaN in a score | the contestant has no such event, never "scored zero" |

---

## Raw tables

### `participations.csv` — one row per contestant per competition edition

| Column | Type | Description |
|---|---|---|
| `contestant_id` | str | pseudonymous contestant id |
| `competition_id` | str | `<competition>-<year>`, e.g. `jbmo-2022` |
| `source` | str | competition: IMO, JBMO, BMO, EGMO, RMM, APMO, MEMO, PAMO, EMO |
| `year` | int | year of the edition |
| `typical_month` | int | usual month of the competition (from `extraction/competition_calendar.csv`) |
| `country` | str | country the contestant represented |
| `problem_scores` | str | points per problem separated by `;`; empty when not published |
| `total` | int | total score; empty for JBMO 2019 (only medals published) |
| `max_total` | int | maximum possible total |
| `score_pct` | float | `total / max_total` |
| `rank_pct` | float | percentile rank within the edition |
| `award` | str | none, hm, bronze, silver, gold |
| `data_source` | str | imo-official.org, moresults.org, or the JBMO organiser's site: hms.gr, hms.gr (PDF), cms.org.cy (PDF), jbmo2022.pmf.unsa.ba (PDF) |

### `competitions.csv` — one row per competition edition

| Column | Type | Description |
|---|---|---|
| `competition_id` | str | `<competition>-<year>` |
| `source` | str | competition |
| `year` | int | year |
| `edition` | int | edition number |
| `coverage` | str | `full`; or, for JBMO editions added from the organisers: `medallists only` (2018), `medallists only, no scores` (2019), `medallists and honourable mentions` (2022) |
| `typical_month` | int | usual month |
| `same_year_before_imo` | bool | always held before the IMO of the same year |
| `first_held` | int | year of the competition's first edition |
| `host_country` | str | host country, when known |
| `num_problems` | int | number of problems |
| `max_score_per_problem` | int | points per problem (7 at most olympiads, 10 at BMO and JBMO, 8 at MEMO) |
| `max_total` | int | maximum total |
| `n_participants` | int | rows in `participations.csv` for this edition |
| `n_countries` | int | countries represented |
| `mean_score_pct` | float | mean `score_pct` |
| `gold_cutoff`, `silver_cutoff`, `bronze_cutoff` | int | lowest total with that medal |

### `contestants.csv` — one row per contestant

| Column | Type | Description |
|---|---|---|
| `contestant_id` | str | pseudonymous contestant id |
| `country` | str | country represented most often |
| `n_countries` | int | number of countries represented (2 for 23 contestants) |
| `first_year`, `last_year` | int | first and last international event |
| `n_events` | int | number of participations |
| `n_imo` | int | number of IMO participations |
| `competitions` | str | competitions attended, separated by `;` |
| `best_imo_award` | str | best IMO award; empty if never at the IMO |
| `gender_proxy` | str | `female` if the contestant ever took part in EGMO (a competition for girls), otherwise `unknown`. Never `male`: absence from EGMO says nothing about gender. EGMO exists only since 2012 |

### `countries.csv` — one row per country

| Column | Type | Description |
|---|---|---|
| `country` | str | country code |
| `name` | str | country name |
| `continent` | str | UN M49 continent (Caucasus, Türkiye and Cyprus in Asia; Russia in Europe) |
| `first_year`, `last_year` | int | first and last year with a participation |
| `n_imo_years` | int | number of IMOs attended |
| `n_contestants` | int | distinct contestants |
| `competitions` | str | competitions ever attended, separated by `;` |

---

## Final table: `imo_contestants_full.csv`

One row per contestant per IMO, 2008–2026. Columns are grouped by prefix. Only the groups
from `imo_` onward are model features; `id_`, `target_` and `meta_` are not.

### `id_` — identifiers

| Column | Description |
|---|---|
| `id_contestant` | pseudonymous contestant id |
| `id_year` | year of the IMO |
| `id_country` | country at this IMO |

### `target_` — what is predicted

| Column | Description |
|---|---|
| `target_total` | IMO total, 0–42 (main regression target) |
| `target_pct` | `target_total / 42` |
| `target_rank_pct` | percentile rank at this IMO |
| `target_z` | mean over the six problems of the score standardised by year and problem (Berg, 2021): removes differences in difficulty between years |
| `target_award` | none, hm, bronze, silver, gold (main classification target) |
| `target_award_code` | award code 0–4 |
| `target_p1` … `target_p6` | points on each problem |

### `meta_` — for error analysis, not features

| Column | Description |
|---|---|
| `meta_gender_proxy` | `gender_proxy` from `contestants.csv`. Uses the whole career (including later EGMOs), so it must not be a feature |
| `meta_continent` | continent of the country |

### `imo_` — the contestant's earlier IMOs

| Column | Description |
|---|---|
| `imo_attempt` | which IMO this is for the contestant (1 = first) |
| `imo_n_prior` | number of earlier IMOs |
| `imo_best_pct`, `imo_best_rank_pct`, `imo_best_award`, `imo_best_z` | best earlier IMO result (each maximum taken separately) |
| `imo_last_pct`, `imo_last_rank_pct`, `imo_last_award` | most recent earlier IMO |
| `imo_years_ago` | years since the most recent earlier IMO |

### `hist_` — all earlier international events (IMO and the other olympiads)

| Column | Description |
|---|---|
| `hist_n_events` | number of earlier events |
| `hist_n_other` | earlier events other than the IMO |
| `hist_n_competitions` | distinct competitions among them |
| `hist_n_same_year` | events in the same year as this IMO (before it) |
| `hist_n_medals` | earlier gold, silver or bronze medals |
| `hist_best_award` | best earlier award code |
| `hist_mean_pct`, `hist_mean_rank_pct` | mean earlier score fraction and percentile |
| `hist_best_rank_pct` | best earlier percentile |
| `hist_years_active` | years since the first international event; NaN without history |
| `hist_trend` | slope of the yearly mean percentile over the years (per year); needs events in two different years |

### `<c>_` — one block per other olympiad

`<c>` is one of `jbmo`, `bmo`, `egmo`, `rmm`, `apmo`, `memo`, `pamo`. Each block has the same
columns:

| Column | Description |
|---|---|
| `<c>_status` | `participated`; or, when absent: `not_participated` (all editions in the window are fully published), `no_data` (an edition in the window is missing or published in part, so absence is uncertain), `not_held` (the competition did not exist yet). The window is the 6 years before the IMO |
| `<c>_missing_editions` | editions in the window that are missing or partial |
| `<c>_n` | number of earlier participations |
| `<c>_best_pct`, `<c>_best_rank_pct`, `<c>_best_award` | best earlier result |
| `<c>_last_award` | award at the most recent participation |
| `<c>_years_ago` | years since the most recent participation |

### `team_` — the contestant's team at this IMO

| Column | Description |
|---|---|
| `team_size` | contestants of the country at this IMO |
| `team_n_with_history` | teammates (including the contestant) with any earlier international event |
| `team_rank_by_history` | rank within the team by `hist_best_rank_pct`, 1 = strongest; contestants without history share the last rank |
| `team_others_mean_best_rank_pct` | mean `hist_best_rank_pct` of the teammates who have history |

### `country_` — the country's earlier results

Computed from the previous IMOs only; `_3y` uses the three previous years, `_1y` the previous one.

| Column | Description |
|---|---|
| `country_imo_mean_pct_3y`, `country_imo_mean_pct_1y` | mean IMO score fraction |
| `country_medal_rate_3y`, `country_gold_rate_3y` | share of contestants with a medal / a gold medal |
| `country_modal_award_3y` | most frequent award code (the higher one on ties) |
| `country_n_imo_3y` | IMOs attended in the window |
| `country_n_regional_3y` | distinct other olympiads the country attended in the window |
| `country_access_<c>` | 1 if the country attended olympiad `<c>` in the window |

### `context_` — the IMO edition

| Column | Description |
|---|---|
| `context_is_host` | the country hosts this IMO |
| `context_online` | the IMO was held online (2020, 2021) |

---

## Compact table: `imo_contestants.csv`

The same rows with 29 columns: the identifiers, `target_total`, `target_rank_pct`, `target_z`,
`target_award`, both `meta_` columns, and a selection of features —
`imo_attempt`, `imo_best_pct`, `imo_last_award`, `hist_n_events`, `hist_n_other`,
`hist_best_award`, `hist_mean_rank_pct`, `hist_best_rank_pct`, `hist_trend`, the best percentile at
JBMO, BMO, EGMO, RMM and APMO, `team_rank_by_history`, `country_imo_mean_pct_3y`,
`country_medal_rate_3y`, `country_modal_award_3y`, `country_n_regional_3y`, `context_is_host`.
