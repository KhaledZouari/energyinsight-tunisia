# Power BI reporting layer

The original report is an imported local Power BI Desktop model. Its three pages are documented below. The binary PBIX is omitted because it embeds restricted customer data. Public screenshots show aggregate results only; the existing report labels are French.

## Query sources

| Query | MySQL source |
|---|---|
| `Client_Risk_Analysis` | `vw_client_risk_analysis` |
| `Monthly_Consumption` | `monthly_electricity_consumption` |
| `Model_Metrics` | `model_metrics` |

The `.m` definitions in `queries/` are exported from the local report. They use local connection coordinates and contain no passwords. Adapt server/database names in Power Query and enter credentials through its authentication dialog.

## Suggested measure definitions

These English-named measures document the calculation contracts; they do not rename the original report's French measures.

```dax
Total Customers = DISTINCTCOUNT('Client_Risk_Analysis'[client_id])

Flagged Customers =
CALCULATE(
    DISTINCTCOUNT('Client_Risk_Analysis'[client_id]),
    'Client_Risk_Analysis'[predicted_target] = 1
)

Flagged Share = DIVIDE([Flagged Customers], [Total Customers])

Total Electricity Invoices = SUM('Monthly_Consumption'[invoice_count])

Total Billed Consumption = SUM('Monthly_Consumption'[total_consumption])

Mean Model Score = AVERAGE('Client_Risk_Analysis'[anomaly_probability])

Test Precision = MAX('Model_Metrics'[precision])
Test Recall = MAX('Model_Metrics'[recall])
Test F1 = MAX('Model_Metrics'[f1_score])
Test ROC AUC = MAX('Model_Metrics'[roc_auc])
Test Accuracy = MAX('Model_Metrics'[accuracy])
```

Unknown scores remain `BLANK`, so the mean score excludes the 678 unscored customers. The flagged-share denominator above includes the full customer population, including unscored customers; an eligible-only share would be a different measure.

## Page 1 — Billing overview

Six cards: total customers, flagged customers, flagged share, mean model score, invoice count, and total billed consumption. A line chart groups invoice totals by invoice issue month; a donut shows descriptive score bands including unscored customers.

The dataset spans 508 observed months, with 3,079,406 electricity invoices and 2,378,852,939 source consumption units. The screenshot abbreviates large values. These are sample billing aggregates, not certified national electricity statistics.

The page mixes train/validation/test scores for descriptive reporting. Its flagged share is a model-decision rate, not historical fraud prevalence. Its mean score is not a calibrated fraud rate.

## Page 2 — Risk segmentation

Category-wise score-band distribution, flagged counts by region, and local slicers for category, region and score band. A customer-level inspection queue is available in the private report. The public screenshot captures only the aggregate charts, excluding the queue and its granular values.

Counts by region are not regional fraud rates. Category and region values are source codes without a verified geographic/business mapping.

## Page 3 — Independent evaluation

Cards and confusion matrix use the published test metrics for 26,963 held-out customers. Keep the single-row `Model_Metrics` table separate from customer-filter interactions. If recalculating from predictions, filter strictly to `jeu = "test"`.

Matrix values: true negatives 22,249; false positives 3,202; false negatives 860; true positives 652. Precision is 16.92%, recall 43.12%, and F1 24.30%.

The local report embeds its confusion-matrix image and narrative statically. Update both after a new training run; data refresh alone does not change these static report resources.

## Screenshot provenance

`docs/results/screenshot_provenance.json` records how the published screenshots were obtained. They are direct captures of actual report views, with viewport selection used to exclude application chrome and granular customer rows. They are not mock dashboards or AI-generated images.
