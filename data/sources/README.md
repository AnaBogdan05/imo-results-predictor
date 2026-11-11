# Additional result sources

Official result documents for competition editions that are missing on moresults.org.
The files list contestants by name, so they are kept locally and not committed; this table
says where each one comes from. `extraction/parse_jbmo_results.py` reads them; JBMO 2018 and the
2020 team lists are crawled from hms.gr by `extraction/crawl_jbmo_hms.py`.

| File | Edition | Content | Used | Source |
|---|---|---|---|---|
| `jbmo/jbmo2019-medals-member-countries.pdf` | JBMO 2019 | medallists of member countries: name, country, medal (no scores) | yes | https://cdn.b3web.xyz/web/cms/optimizedJBMO2019medals-Membercountries.pdf1561545621.pdf |
| `jbmo/jbmo2019-medals-guest-countries.pdf` | JBMO 2019 | medallists of guest countries: name, country, medal (no scores) | yes | https://cdn.b3web.xyz/web/cms/optimizedJBMO2019medals-Guestcountries.pdf1561545620.pdf |
| `jbmo/jbmo2022-medals.pdf` | JBMO 2022 | medallists and honourable mentions: rank, name, problem scores, total, medal | yes | https://jbmo2022.pmf.unsa.ba/ (downloaded manually: the site blocks automated requests) |
| `jbmo/jbmo2020-overall.pdf` | JBMO 2020 | every contestant by code (e.g. `ROM2`): problem scores, total | yes: codes mapped to the team pages of hms.gr | https://www.hms.gr/24jbmo2020/ |
| `jbmo/jbmo2020-medals.pdf` | JBMO 2020 | medallists by code | yes: medal cut-offs only (some rows wrap over several lines) | https://www.hms.gr/24jbmo2020/ |
| — (crawled) | JBMO 2018 | medallists by code (e.g. `ROMANIA2`): problem scores, total; held 19–24 June 2018 | yes: codes mapped to the team pages | http://hms.gr/22jbmo2018/ (`gold.htm`, `silver.htm`, `bronze.htm`) |
| — (crawled) | JBMO 2018, 2020 | team pages: contestants in code order | yes | `team*.htm` on the two sites above |

JBMO 2020 was held online on 9–13 September 2020, before the online IMO 2020 (from
19 September), so it still counts as an event before that IMO.

The JBMO 2019 PDFs are linked from the organiser's page,
https://www.cms.org.cy/pages/competitions/jbmo-2019/jbmo-2019 (Cyprus Mathematical Society).
That page also links one PDF per country with the team list, which maps contestant codes
(e.g. `ROU1`) to names.

## Terms of use (checked 2026-11-11)

| Site | robots.txt | Terms / licence |
|---|---|---|
| cms.org.cy | none | no terms of use found on the page |
| hms.gr | disallows only `/wp-admin/` | no terms of use found on the JBMO pages |
| jbmo2022.pmf.unsa.ba | not readable (web firewall blocks scripts) | not checked; the PDF was downloaded by hand in a browser |
