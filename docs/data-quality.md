# Data provenance and quality findings

## Provenance confidence

Zindi's [data page](https://zindi.world/competitions/fraud-detection-in-electricity-and-gas-consumption-challenge/data) attributes the files to STEG and describes customer and invoice CSVs. Local filenames, column layout and `train_Client_*` identifiers match that description. The source code performs local ingestion, not website scraping.

An original download receipt or comparison against a newly downloaded official archive is not available. The project records local hashes for integrity, but these do not establish the files' full acquisition history. Future acquisition records should include the source URL, download date, archive checksum and extracted-file checksums.

## Observed quality

The independent scan of all invoice rows and all customer rows reports:

| Check | Observed result |
|---|---:|
| Customer ID duplicates | 0 |
| Missing customer cells | 0 |
| Invalid electricity invoice dates under strict ISO parsing | 0 |
| Missing electricity consumption components | 0 |
| Electricity invoices with zero total consumption | 229,197 |
| Electricity invoices with negative total consumption | 0 |
| Electricity invoices before 2005 | 19,909 |
| Electricity total, in source units | 2,378,852,939 |

Exact aggregate checks are in `docs/results/data_quality_checks.json`. No individual source rows are published.

## Date discrepancy

Zindi documents a 2005–2019 history. Local electricity dates span 9 June 1977 to 7 December 2019. Correct parsing does not make these older dates business-valid; the discrepancy must be resolved with authoritative source information or a documented sensitivity analysis.

An earlier mixed/day-first parser swapped 1,242,886 electricity dates whose day and month were ambiguous. Explicit ISO parsing changed monthly placement from the earlier 505 observed months to 508, without removing or adding electricity invoices for that purpose.

## Cleaning behavior

Customer processing strips identifiers, standardizes headers, corrects `disrict`, parses dates explicitly, enforces a binary target and removes unusable IDs/targets and duplicate IDs. In this dataset, the customer count remains unchanged. On conflicting future duplicates, retaining the first row would require a stronger reconciliation policy.

Invoice processing filters to `ELEC`, converts consumption components, and excludes unusable IDs/dates/totals. All 3,079,406 electricity records pass the current criteria. Negative totals are retained and counted by design, although no such totals are observed here. Invoice duplicates and extreme values are not removed by the current implementation.

Summation uses `min_count=1`: entirely missing consumption stays missing, but a partially missing record is summed from available components. There are no missing electricity components in the current scan; future incomplete data would require an explicit completeness rule.

## Coverage and interpretation

The 678 customers without electricity history stay in the customer dataset and receive neither a score nor a decision. They must not be converted into zero-consumption customers.

Monthly totals group invoices by issue date. They do not allocate consumption across billing periods or insert unobserved months as zeros. The implementation does not use `months_number` to normalize consumption. Source units, category meanings, geographic mappings and national representativeness must be confirmed before broader claims.
