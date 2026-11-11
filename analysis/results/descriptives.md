# Dataset descriptives

- Raw participations: 36,564 rows, 21,105 contestants, 178 competition editions
- Final table: 11,169 IMO entries (IMO 2008–2026), 7,147 contestants, 133 countries, 97 features
- With any prior international result: 58.6%; with a prior non-IMO olympiad: 39.6%
- IMO total: mean 15.6, median 15, sd 9.8

## Raw participations by competition

| source   |   editions |   rows |   first |   last |
|:---------|-----------:|-------:|--------:|-------:|
| APMO     |         11 |   3815 |    2016 |   2026 |
| BMO      |         18 |   2005 |    2005 |   2026 |
| EGMO     |         15 |   2625 |    2012 |   2026 |
| EMO      |          1 |    124 |    2026 |   2026 |
| IMO      |         68 |  22745 |    1959 |   2026 |
| JBMO     |         15 |   1601 |    2010 |   2026 |
| MEMO     |         20 |   1194 |    2007 |   2026 |
| PAMO     |         13 |    964 |    2007 |   2026 |
| RMM      |         17 |   1491 |    2008 |   2026 |

## IMO award distribution

| target_award   |   share |
|:---------------|--------:|
| none           |   0.245 |
| hm             |   0.253 |
| bronze         |   0.245 |
| silver         |   0.171 |
| gold           |   0.086 |

## Prior-history coverage (share of IMO entries)

|      |   share |
|:-----|--------:|
| PAMO |   0.011 |
| EGMO |   0.033 |
| MEMO |   0.056 |
| JBMO |   0.078 |
| RMM  |   0.084 |
| BMO  |   0.132 |
| APMO |   0.149 |
| IMO  |   0.378 |

## Best prior percentile vs IMO percentile (Spearman)

| competition   |    n |   spearman |
|:--------------|-----:|-----------:|
| MEMO          |  624 |      0.45  |
| JBMO          |  703 |      0.513 |
| RMM           |  943 |      0.54  |
| BMO           | 1470 |      0.634 |
| PAMO          |  120 |      0.634 |
| IMO           | 4222 |      0.76  |
| APMO          | 1666 |      0.772 |
| EGMO          |  372 |      0.797 |

## IMO award by number of previous IMOs (row shares)

| imo_n_prior   |   none |    hm |   bronze |   silver |   gold |
|:--------------|-------:|------:|---------:|---------:|-------:|
| 0             |  0.316 | 0.265 |    0.215 |    0.140 |  0.064 |
| 1             |  0.152 | 0.250 |    0.291 |    0.200 |  0.106 |
| 2             |  0.086 | 0.216 |    0.309 |    0.261 |  0.129 |
| 3+            |  0.056 | 0.145 |    0.276 |    0.276 |  0.247 |
