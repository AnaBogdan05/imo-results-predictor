"""Phase 1 baselines on a temporal split (train on earlier IMOs, test on the latest).

1. Country history: predict the country's mean IMO score over the previous 3 IMOs
   (and its modal award). Countries without recent IMOs fall back to the training mean.
2. Linear regression (score) and multinomial logistic regression (award), each on two
   feature sets: the compact table and the full table. NaN -> median + missing
   indicator; <competition>_status -> one-hot.

Features are all columns except id_, target_ and meta_ ones.
Metrics: MAE, RMSE, R^2 for target_total; accuracy, accuracy within one award,
balanced accuracy and macro-F1 for target_award; 95% bootstrap intervals over test
contestants.

Input:  data/final/imo_contestants.csv, data/final/imo_contestants_full.csv
Output: analysis/results/baselines.md, analysis/results/baseline_predictions.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score, mean_absolute_error,
                             mean_squared_error, r2_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "data" / "final"
RESULTS = ROOT / "analysis" / "results"

TEST_YEARS = range(2023, 2027)
AWARDS = ["none", "hm", "bronze", "silver", "gold"]
NOT_FEATURES = ("id_", "target_", "meta_")
N_BOOTSTRAP = 1000


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    x = df[[c for c in df.columns if not c.startswith(NOT_FEATURES)]]
    categorical = [c for c in x.columns if x[c].dtype == object]
    return pd.get_dummies(x, columns=categorical, dtype=float)


def regression_metrics(y, p):
    return {"MAE": mean_absolute_error(y, p), "RMSE": mean_squared_error(y, p) ** 0.5, "R2": r2_score(y, p)}


def classification_metrics(y, p):
    code = {a: i for i, a in enumerate(AWARDS)}
    off_by = np.abs(pd.Series(p).map(code).values - pd.Series(y).map(code).values)
    return {"accuracy": accuracy_score(y, p), "within_1": (off_by <= 1).mean(),
            "balanced_acc": balanced_accuracy_score(y, p),
            "macro_F1": f1_score(y, p, average="macro", labels=AWARDS, zero_division=0)}


def bootstrap(metric_fn, y, p, seed=0):
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    point = metric_fn(y, p)
    samples = [metric_fn(y[idx], p[idx]) for idx in
               (rng.integers(0, len(y), len(y)) for _ in range(N_BOOTSTRAP))]
    return {k: (v, np.percentile([s[k] for s in samples], 2.5), np.percentile([s[k] for s in samples], 97.5))
            for k, v in point.items()}


def pipeline(model):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                         StandardScaler(), model)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    tables = {"compact": pd.read_csv(FINAL / "imo_contestants.csv"),
              "full": pd.read_csv(FINAL / "imo_contestants_full.csv", low_memory=False)}
    df = tables["full"]
    is_test = df.id_year.isin(TEST_YEARS)
    train, test = df[~is_test], df[is_test]

    preds = test[["id_contestant", "id_year", "id_country", "target_total", "target_award", "hist_n_events"]].copy()

    # 1. Country history
    preds["country_total"] = (test.country_imo_mean_pct_3y * 42).fillna(train.target_total.mean())
    modal = train.target_award.mode()[0]
    preds["country_award"] = test.country_modal_award_3y.map(dict(enumerate(AWARDS))).fillna(modal)

    # 2. Linear / logistic regression on each feature set
    n_features = {}
    for name, table in tables.items():
        x = feature_matrix(table)
        n_features[name] = x.shape[1]
        lin = pipeline(LinearRegression()).fit(x[~is_test], train.target_total)
        preds[f"linear_{name}_total"] = np.clip(lin.predict(x[is_test]), 0, 42)
        log = pipeline(LogisticRegression(max_iter=3000, class_weight="balanced"))
        log.fit(x[~is_test], train.target_award)
        preds[f"logistic_{name}_award"] = log.predict(x[is_test])
        if name == "compact":
            coef = pd.Series(lin[-1].coef_, index=lin[:-1].get_feature_names_out(x.columns))

    preds["mean_total"] = train.target_total.mean()
    preds["majority_award"] = modal

    reg_models = [("Training mean", "mean_total"), ("Country history (3 IMOs)", "country_total"),
                  (f"Linear regression, compact ({n_features['compact']} features)", "linear_compact_total"),
                  (f"Linear regression, full ({n_features['full']} features)", "linear_full_total")]
    cls_models = [("Majority class", "majority_award"), ("Country modal award (3 IMOs)", "country_award"),
                  (f"Logistic regression, compact ({n_features['compact']} features)", "logistic_compact_award"),
                  (f"Logistic regression, full ({n_features['full']} features)", "logistic_full_award")]
    reg = pd.DataFrame([{"model": n, **bootstrap(regression_metrics, preds.target_total, preds[c])}
                        for n, c in reg_models]).set_index("model")
    cls = pd.DataFrame([{"model": n, **bootstrap(classification_metrics, preds.target_award, preds[c])}
                        for n, c in cls_models]).set_index("model")

    def fmt(table):
        return table.map(lambda t: f"{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]")

    best_cls = cls.macro_F1.map(lambda t: t[0]).idxmax()
    best_col = dict(cls_models)[best_cls]
    confusion = pd.crosstab(preds.target_award, preds[best_col]).reindex(index=AWARDS, columns=AWARDS, fill_value=0)
    confusion.index.name, confusion.columns.name = "actual \\ predicted", None

    split = []
    for has, g in preds.groupby(preds.hist_n_events > 0):
        split.append({"prior history": "yes" if has else "no", "n": len(g),
                      "country MAE": mean_absolute_error(g.target_total, g.country_total),
                      "linear (compact) MAE": mean_absolute_error(g.target_total, g.linear_compact_total),
                      "logistic (compact) macro-F1": f1_score(g.target_award, g.logistic_compact_award,
                                                             average="macro", labels=AWARDS, zero_division=0)})

    lines = [
        "# Baseline results",
        "",
        f"Temporal split: train IMO {train.id_year.min()}–{train.id_year.max()} (n = {len(train):,}), "
        f"test IMO {min(TEST_YEARS)}–{max(TEST_YEARS)} (n = {len(test):,}). "
        f"Brackets: 95% bootstrap interval over test contestants ({N_BOOTSTRAP} resamples). "
        "Feature counts are after one-hot encoding of the status columns.",
        "",
        "## IMO total score (0–42)",
        "",
        fmt(reg).to_markdown(),
        "",
        "## IMO award (5 classes)",
        "",
        "`within_1`: predicted award at most one step from the actual one (e.g. bronze for silver).",
        "",
        fmt(cls).to_markdown(),
        "",
        f"## Confusion matrix: {best_cls}",
        "",
        confusion.to_markdown(),
        "",
        "## Errors by prior international history (test set)",
        "",
        pd.DataFrame(split).to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Largest linear-regression coefficients, compact features (standardised)",
        "",
        coef.sort_values(key=abs, ascending=False).head(12).rename("coefficient").to_frame()
        .to_markdown(floatfmt=".2f"),
        "",
    ]
    (RESULTS / "baselines.md").write_text("\n".join(lines))
    preds.to_csv(RESULTS / "baseline_predictions.csv", index=False)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
