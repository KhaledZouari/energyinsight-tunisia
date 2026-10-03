# Modeling methodology

## What is being predicted?

The target is the customer-level binary label supplied in the dataset: 1 for fraud and 0 otherwise, according to Zindi. The implementation uses electricity-only billing features. It does not establish an electricity-specific diagnosis, identify the cause of fraud, or estimate fraud onset.

Because the label has no diagnosis date, evaluation is retrospective. Aggregating the available history is defensible for this task, but cannot demonstrate that an alert would have preceded an actual fraud event. A prospective evaluation needs dated labels and features constructed before the prediction cutoff.

## Features

Categorical: district, region, customer category.

Numeric: creation year/month, consumption sum, invoice count, maximum/minimum consumption, counts of zero/negative total consumption, mean consumption, population standard deviation, and billing-history duration in days.

Per-invoice consumption is the sum of four consumption levels. Final customer means are calculated from consolidated sums and counts, not an unweighted average of chunk means. Population variance is `sum(x²)/n - mean(x)²`; small negative numerical artifacts are clipped before the square root.

Absolute invoice dates, customer IDs, target and eligibility/split flags are excluded from predictors. Creation year/month and history duration remain, so time/cohort effects are not entirely eliminated.

## Partitioning and preprocessing

- 134,815 customers with electricity history are eligible.
- Training: 80,889; validation: 26,963; test: 26,963.
- Stratified random split, seed 42, with disjoint customers.
- Three-fold stratified cross-validation on training only.
- Numeric median imputation and scaling fitted inside each training fold.
- One-hot categorical encoding for logistic regression/random forest; ordinal encoding with categorical feature flags for HistGradientBoosting.
- Class weighting addresses imbalance; synthetic oversampling is not used.

Customer aggregation is independent of target and other customers. The pipeline keeps learned imputation/encoding/scaling inside training. This controls common technical leakage paths, while the absence of dated outcomes remains a substantive limitation.

## Selection and evaluation

Each candidate uses fixed hyperparameters. Validation precision-recall curves supply the threshold maximizing validation F1. Candidate selection uses validation F1, then validation Average Precision on ties. The selected model is not retrained after threshold selection.

HistGradientBoosting is selected at threshold `0.6484454588571432`. Only then is the held-out test evaluated. Its exact metrics are in `docs/results/test_metrics.json`. The test is an internal partition of the labeled training CSV; it is not Zindi's hidden competition test.

ROC-AUC measures ranking discrimination. Average Precision summarizes precision across recall increments and is not a trapezoidal PR-curve area. Precision/recall/F1 describe behavior at the selected decision threshold. Accuracy must be compared with the always-negative baseline because prevalence is low.

The model finds 652 positive-labeled customers among 3,854 test alerts. Test prevalence is 1,512 / 26,963 = 5.61%; alert precision is 16.92%, roughly three times prevalence. This enrichment does not quantify inspection value or recovered revenue.

## Interpreting the score

Class weighting changes the optimization objective. Predicted scores have not been calibrated against independent outcomes and should not be presented as literal real-world probabilities.

The existing report uses score bands at 0.30, 0.60 and 0.80. These descriptive bands are distinct from the binary decision threshold at 0.6484. A customer in the high band may still have a negative binary decision.

Metrics on all scored customers mix in-sample and independent predictions. Use `jeu = "test"` for evaluation and treat overview population summaries as descriptive.
