# Local setup and reproduction

## Requirements

- Python 3.13; the recorded local environment is Python 3.13.6.
- Dependencies pinned in `requirements.txt`; the recorded model environment uses scikit-learn 1.9.0.
- A running MySQL server, database, application account, and `mysqldump` executable.
- Private access to the dataset under its publisher's terms.
- Windows for the supplied local server helper scripts and the current full verifier's environment check.
- Power BI Desktop for report authoring; the validated local report used Desktop 2.158.1177.0 and Oracle Connector/NET 26.7.0.

The repository intentionally does not contain data, trained binaries, a bundled MySQL server or a PBIX. Cloning alone does not reproduce the dashboard. The query definitions and measure documentation support local reconstruction after authorized data acquisition.

## 1. Install Python dependencies

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip check
```

Use the same dependency versions when loading saved scikit-learn models. The full verifier currently requires `.venv/Scripts/python.exe`; it is not a platform-neutral certification tool.

## 2. Acquire the data privately

Visit the [official data page](https://zindi.world/competitions/fraud-detection-in-electricity-and-gas-consumption-challenge/data), read the terms, obtain `train.zip` through the platform, and place its files here:

```text
data/raw/client_train.csv
data/raw/invoice_train.csv
```

Preserve the original files. Record the acquisition URL, date and checksums locally. Do not upload them, processed copies or individual predictions to GitHub.

## 3. Configure MySQL

Create an empty dedicated database and user through an administrator account. Use your own password, and give the application account the privileges needed to create, read, populate, rename and drop tables, plus the privileges required by your server's backup configuration.

```sql
CREATE DATABASE energyinsight_db CHARACTER SET utf8mb4;
CREATE USER 'energy_user'@'127.0.0.1' IDENTIFIED BY 'CHOOSE_A_PRIVATE_PASSWORD';
GRANT ALL PRIVILEGES ON energyinsight_db.* TO 'energy_user'@'127.0.0.1';
```

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your connection details. Set `MYSQL_BIN` to the directory containing `mysqldump`. Never commit `.env` or MySQL option files. Confirm backup access before running the pipeline against any existing database.

`start_mysql.ps1` and `stop_mysql.ps1` are helpers for the original machine's optional portable server. They do not install MySQL, and the excluded `.tools/` and `.mysql/` directories are not supplied. Use your own running MySQL installation on a fresh checkout.

## 4. Run the pipeline

```powershell
.venv\Scripts\python.exe run_all.py
.venv\Scripts\python.exe reports\verify_project.py
```

The orchestrator backs up existing files and SQL, processes data in staging, loads temporary tables, trains/evaluates models, checks consistency, and publishes the version. A failed stage stops the run and keeps logs in staging.

Individual processing scripts default to `.staging/manual/`. Use `run_all.py` to publish a coherent version; running one script alone does not publish all dependent outputs.

## 5. Tests

Data-independent regressions:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_regressions.py -v
```

After a successful full local run:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The verifier-failure integration tests depend on the last run's staging artifacts and a reachable MySQL server. They intentionally introduce a temporary inconsistency, assert rejection, and restore the staging files. A clean public checkout skips these tests because private outputs are absent.

## 6. Reconstruct the Power BI report

Create the view in `sql/powerbi_views.sql` after the tables have been published. Configure the three Power Query definitions under `powerbi/queries/` to your server and database, with credentials entered through Power BI's credential dialog.

Use the specifications in `powerbi/README.md` to build the overview, segmentation and test-performance pages. Keep `Model_Metrics` independent of customer overview filters. Do not publish a data-bearing PBIX or granular extracts without resolving the dataset's access conditions.
