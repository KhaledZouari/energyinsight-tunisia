# Architecture and output contracts

## Processing model

This is a local batch pipeline, not a hosted service. Python prepares features, loads MySQL, trains classifiers, verifies outputs, and publishes artifacts. Power BI consumes the published SQL analytics layer.

The raw invoice file is read in chunks of 200,000 rows. Each chunk is filtered to electricity and reduced into customer-level and monthly partial aggregates. These partial aggregates remain in memory until final consolidation; total memory use therefore still grows with the number of partial customer groups.

`src/project_config.py` centralizes paths and database connectivity. `ENERGYINSIGHT_OUTPUT_ROOT` directs output to an isolated staging directory, and `ENERGYINSIGHT_TABLE_PREFIX` creates provisional SQL tables. SQL identifiers are validated against a restricted pattern.

## Customer feature contract

`clients_clean` contains one row per customer. `client_consumption_features` contains one row per customer with usable electricity history. A left join validated with `one_to_one` preserves all customers in `client_ml_dataset`.

The model consumes three categorical and eleven numeric variables, defined in `src/ml_features.py`. Customer ID is a join key, not a predictor. Customers without electricity history retain missing values and are explicitly excluded from scoring.

## SQL tables

| Table | Grain | Purpose |
|---|---|---|
| `clients_clean` | Customer | Clean customer attributes and historical label |
| `client_consumption_features` | Customer with electricity history | Aggregated billing features |
| `client_ml_dataset` | Customer | Joined modeling and reporting dataset |
| `monthly_electricity_consumption` | Invoice month | Billing trend aggregates |
| `client_predictions` | Customer | Score, decision, partition and eligibility |
| `model_metrics` | Selected model / test evaluation | Independent performance metrics |

`sql/powerbi_views.sql` creates `vw_client_risk_analysis`, joining the customer dataset with predictions. Unknown dates are stored as SQL `NULL`; valid dates use `DATETIME`.

## Verification and publication

`run_all.py` backs up existing outputs and dumps MySQL before replacement. It runs all processing steps into staging, verifies file integrity and CSV/SQL consistency, and then publishes the new version.

The integrity manifest uses SHA-256 hashes for source preservation and artifact version consistency. Database tables are swapped with a grouped `RENAME TABLE`. Files are replaced individually; captured publication failures trigger restoration.

This is not a distributed transaction across the filesystem and MySQL. An abrupt crash during publication may require manual restoration from backup. A hash verifies unchanged bytes, not source authenticity before acquisition or business validity.

## Public repository boundary

Only source code, connection placeholders, aggregate result files, aggregate visuals and documentation are versioned. The dataset, individual exports, database backups, binary models and PBIX report remain private. The public copy is deliberately separate from the original working project.
