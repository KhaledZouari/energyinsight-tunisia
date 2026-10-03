"""Import des quatre datasets validés, en tables provisoires puis renommage."""
from sqlalchemy import text
from project_config import OUTPUT_ROOT, REPORTS_DIR, get_engine
from database_io import TABLE_FILES, import_csv
import json


def main():
    engine = get_engine()
    try:
        with engine.connect() as connection:
            version = connection.execute(text('SELECT VERSION()')).scalar_one()
        print('MySQL :', version, flush=True)
        results = {'server_version':version, 'tables':{}}
        for name, relative in list(TABLE_FILES.items())[:4]:
            results['tables'][name] = import_csv(engine, name, OUTPUT_ROOT / relative)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / 'sql_import_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
