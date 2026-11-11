# Baseline results

Temporal split: train IMO 2008–2022 (n = 8,646), test IMO 2023–2026 (n = 2,523). Brackets: 95% bootstrap interval over test contestants (1000 resamples). Feature counts are after one-hot encoding of the status columns.

## IMO total score (0–42)

| model                                    | MAE                  | RMSE                   | R2                      |
|:-----------------------------------------|:---------------------|:-----------------------|:------------------------|
| Training mean                            | 8.365 [8.141, 8.593] | 10.199 [9.961, 10.434] | -0.038 [-0.053, -0.025] |
| Country history (3 IMOs)                 | 4.973 [4.814, 5.114] | 6.306 [6.121, 6.482]   | 0.603 [0.578, 0.628]    |
| Linear regression, compact (20 features) | 4.359 [4.227, 4.489] | 5.523 [5.337, 5.697]   | 0.696 [0.672, 0.719]    |
| Linear regression, full (108 features)   | 4.645 [4.514, 4.797] | 5.769 [5.606, 5.942]   | 0.668 [0.643, 0.691]    |

## IMO award (5 classes)

`within_1`: predicted award at most one step from the actual one (e.g. bronze for silver).

| model                                      | accuracy             | within_1             | balanced_acc         | macro_F1             |
|:-------------------------------------------|:---------------------|:---------------------|:---------------------|:---------------------|
| Majority class                             | 0.252 [0.235, 0.268] | 0.738 [0.721, 0.754] | 0.200 [0.200, 0.200] | 0.080 [0.076, 0.085] |
| Country modal award (3 IMOs)               | 0.467 [0.449, 0.486] | 0.906 [0.894, 0.918] | 0.449 [0.431, 0.469] | 0.463 [0.444, 0.483] |
| Logistic regression, compact (20 features) | 0.517 [0.498, 0.536] | 0.912 [0.902, 0.923] | 0.537 [0.518, 0.556] | 0.508 [0.489, 0.526] |
| Logistic regression, full (108 features)   | 0.521 [0.501, 0.540] | 0.940 [0.931, 0.949] | 0.519 [0.499, 0.540] | 0.515 [0.495, 0.535] |

## Confusion matrix: Logistic regression, full (108 features)

| actual \ predicted   |   none |   hm |   bronze |   silver |   gold |
|:---------------------|-------:|-----:|---------:|---------:|-------:|
| none                 |    336 |  226 |       12 |        4 |      0 |
| hm                   |     92 |  428 |       96 |       16 |      3 |
| bronze               |     14 |  197 |      256 |      147 |     35 |
| silver               |      3 |   38 |      128 |      157 |     96 |
| gold                 |      2 |    3 |       22 |       75 |    137 |

## Errors by prior international history (test set)

| prior history   |    n |   country MAE |   linear (compact) MAE |   logistic (compact) macro-F1 |
|:----------------|-----:|--------------:|-----------------------:|------------------------------:|
| no              |  842 |         4.656 |                  4.167 |                         0.511 |
| yes             | 1681 |         5.132 |                  4.456 |                         0.480 |

## Largest linear-regression coefficients, compact features (standardised)

|                                          |   coefficient |
|:-----------------------------------------|--------------:|
| country_imo_mean_pct_3y                  |          5.23 |
| imo_attempt                              |          1.33 |
| country_medal_rate_3y                    |          1.04 |
| hist_mean_rank_pct                       |          0.71 |
| missingindicator_country_modal_award_3y  |         -0.51 |
| missingindicator_country_medal_rate_3y   |         -0.51 |
| missingindicator_country_imo_mean_pct_3y |         -0.51 |
| team_rank_by_history                     |         -0.50 |
| country_modal_award_3y                   |          0.48 |
| hist_n_other                             |         -0.44 |
| missingindicator_egmo_best_rank_pct      |          0.37 |
| imo_last_award                           |          0.35 |
