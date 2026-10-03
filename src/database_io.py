"""Imports SQL en tables provisoires, contrôles puis renommage atomique."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import subprocess
import uuid
import pandas as pd
from sqlalchemy import DateTime, BigInteger, Boolean, Float, String, inspect, text
from project_config import PROJECT_DIR, database_name, identifier, table_name

DATE_COLUMNS = {'creation_date','month','invoice_date','invoice_month','first_invoice_date','last_invoice_date'}
TABLE_FILES = {
    'clients_clean': 'data/processed/clients_clean.csv',
    'monthly_electricity_consumption': 'data/processed/monthly_electricity_consumption.csv',
    'client_consumption_features': 'data/processed/client_consumption_features.csv',
    'client_ml_dataset': 'data/processed/client_ml_dataset.csv',
    'client_predictions': 'data/processed/client_predictions.csv',
    'model_metrics': 'reports/model_metrics.csv',
}


def prepare_dates(frame):
    for column in DATE_COLUMNS.intersection(frame.columns):
        frame[column] = pd.to_datetime(frame[column], format='ISO8601', errors='coerce')
    return frame


def sql_types(frame):
    types = {c: DateTime() for c in DATE_COLUMNS.intersection(frame.columns)}
    for column in frame.columns:
        if column in types:
            continue
        if column in {'client_id','risk_level','jeu','model','evaluation_set'}:
            types[column] = String(128)
        elif column in {'predicted_target','prediction','actual_target','target','tn','fp','fn','tp'}:
            types[column] = BigInteger()
        elif pd.api.types.is_bool_dtype(frame[column]) or column == 'a_facture_electrique':
            types[column] = Boolean()
        elif pd.api.types.is_integer_dtype(frame[column]):
            types[column] = BigInteger()
        elif pd.api.types.is_numeric_dtype(frame[column]):
            types[column] = Float(precision=53)
    return types


def dump_database(engine, backup):
    """Refuse tout remplacement sans dump exploitable."""
    backup = Path(backup)
    backup.mkdir(parents=True, exist_ok=True)
    executable = Path(os.environ['MYSQL_BIN']) / ('mysqldump.exe' if os.name=='nt' else 'mysqldump')
    config = backup / '.dump.cnf'
    password = os.environ['MYSQL_PASSWORD'].replace('\\','\\\\').replace('"','\\"')
    config.write_text('[client]\nuser='+os.environ['MYSQL_USER']+'\npassword="'+password+'"\nhost='+os.environ['MYSQL_HOST']+'\nport='+os.environ['MYSQL_PORT']+'\n',encoding='utf-8')
    output = backup / 'energyinsight_db.sql'
    try:
        with output.open('wb') as stream:
            result = subprocess.run([str(executable), '--defaults-extra-file='+str(config),
                '--single-transaction','--skip-lock-tables','--no-tablespaces',
                '--set-gtid-purged=OFF', database_name()], stdout=stream, stderr=subprocess.PIPE)
        if result.returncode or output.stat().st_size==0:
            raise RuntimeError('Dump MySQL échoué : '+result.stderr.decode('utf-8',errors='replace'))
    finally:
        config.unlink(missing_ok=True)
    return output


def import_csv(engine, logical_name, csv_path):
    target = table_name(logical_name)
    temporary = identifier('import_'+uuid.uuid4().hex[:12])
    if inspect(engine).has_table(target):
        backup = PROJECT_DIR.parent / ('backup_'+datetime.now(ZoneInfo('Europe/Paris')).strftime('%Y%m%d_%H%M%S'))
        dump_database(engine, backup / 'sql')
    count = 0
    try:
        for frame in pd.read_csv(csv_path, chunksize=50_000, low_memory=False):
            frame = prepare_dates(frame)
            frame.to_sql(temporary, engine, if_exists='fail' if count==0 else 'append', index=False,
                         chunksize=1000, method='multi', dtype=sql_types(frame))
            count += len(frame)
        if count==0:
            raise ValueError('CSV vide : '+str(csv_path))
        with engine.connect() as connection:
            actual = connection.execute(text(f'SELECT COUNT(*) FROM `{temporary}`')).scalar_one()
            if actual != count:
                raise ValueError('Comptage SQL différent du CSV')
            if 'client_id' in frame.columns:
                unique = connection.execute(text(f'SELECT COUNT(DISTINCT client_id) FROM `{temporary}`')).scalar_one()
                if unique != count:
                    raise ValueError('Clients SQL non uniques')
            date_types = connection.execute(text('SELECT COLUMN_NAME,DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS '
                'WHERE TABLE_SCHEMA=:db AND TABLE_NAME=:table'), {'db':database_name(),'table':temporary}).all()
            for name, dtype in date_types:
                if name in DATE_COLUMNS and dtype not in {'date','datetime','timestamp'}:
                    raise ValueError('Type SQL incorrect : '+name)
        old = identifier('previous_'+uuid.uuid4().hex[:12])
        with engine.begin() as connection:
            if inspect(engine).has_table(target):
                connection.execute(text(f'RENAME TABLE `{target}` TO `{old}`, `{temporary}` TO `{target}`'))
                connection.execute(text(f'DROP TABLE `{old}`'))
            else:
                connection.execute(text(f'RENAME TABLE `{temporary}` TO `{target}`'))
        print(f'{logical_name} : CSV={count}, SQL={actual}', flush=True)
        return count
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS `{temporary}`'))
