"""Configuration partagée ; les sorties sont préparées avant publication."""
from pathlib import Path
import os
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

PROJECT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DIR / '.env', override=False)
OUTPUT_ROOT = Path(os.getenv('ENERGYINSIGHT_OUTPUT_ROOT', str(PROJECT_DIR / '.staging/manual'))).resolve()
PROCESSED_DIR = OUTPUT_ROOT / 'data/processed'
REPORTS_DIR = OUTPUT_ROOT / 'reports'
MODELS_DIR = OUTPUT_ROOT / 'models'
EXPORTS_DIR = OUTPUT_ROOT / 'exports'


def identifier(value):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', value):
        raise ValueError('Identifiant SQL invalide')
    return value


def table_name(name):
    return identifier(os.getenv('ENERGYINSIGHT_TABLE_PREFIX', '') + name)


def database_name():
    return identifier(os.environ['MYSQL_DATABASE'])


def get_engine(database=True):
    return create_engine(URL.create(
        'mysql+pymysql', username=os.environ['MYSQL_USER'],
        password=os.environ['MYSQL_PASSWORD'], host=os.environ['MYSQL_HOST'],
        port=int(os.environ['MYSQL_PORT']), database=database_name() if database else None,
        query={'charset': 'utf8mb4'}), pool_pre_ping=True,
        connect_args={'connect_timeout': 10})
