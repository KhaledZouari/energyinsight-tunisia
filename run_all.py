"""Pipeline sauvegardé, préparé et vérifié avant publication des fichiers et tables."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
import uuid

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0,str(PROJECT/'src'))
from project_config import get_engine, identifier
from database_io import TABLE_FILES, dump_database
from sqlalchemy import inspect, text


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def run(script, stage, environment):
    print('\n=== '+script+' ===',flush=True)
    logs = stage/'reports/logs'
    logs.mkdir(parents=True,exist_ok=True)
    with (logs/(Path(script).stem+'.log')).open('w',encoding='utf-8') as output:
        result = subprocess.run([sys.executable,str(PROJECT/script)],stdout=output,
                                stderr=subprocess.STDOUT,env=environment,cwd=PROJECT)
    if result.returncode:
        raise RuntimeError(f'{script} a échoué ({result.returncode}), voir {logs}')
    print('OK : '+script,flush=True)


def main():
    stamp = datetime.now(ZoneInfo('Europe/Paris')).strftime('%Y%m%d_%H%M%S')
    run_id = stamp+'_'+uuid.uuid4().hex[:6]
    backup = PROJECT.parent/('backup_'+stamp)
    backup.mkdir()
    saved = backup/PROJECT.name
    saved.mkdir()
    for name in ['data','models','outputs','exports','figures','reports','powerbi','src','sql']:
        if (PROJECT/name).exists():
            shutil.copytree(PROJECT/name,saved/name)
    for file in PROJECT.iterdir():
        if file.is_file() and file.name != '.env':
            shutil.copy2(file,saved/file.name)
    for file in PROJECT.parent.glob('*.pbix'):
        shutil.copy2(file,backup/file.name)
    stage = PROJECT/'.staging'/run_id
    stage.mkdir(parents=True)
    prefix = 'stage_'+uuid.uuid4().hex[:10]+'__'
    environment = dict(os.environ,ENERGYINSIGHT_OUTPUT_ROOT=str(stage),
        ENERGYINSIGHT_TABLE_PREFIX=prefix,ENERGYINSIGHT_RUN_ID=run_id,
        PYTHONIOENCODING='utf-8',MPLBACKEND='Agg')
    published = []
    renamed = []
    sql_published = False
    engine = get_engine()
    try:
        dump_database(engine,backup/'sql_before')
        for script in ['src/01_inspect_data.py','src/02_clean_clients.py','src/03_process_invoices.py',
                       'src/04_exploratory_analysis.py','src/05_load_to_mysql.py',
                       'src/06_train_model.py','src/matrice_confusion_fr.py']:
            run(script,stage,environment)
        comparisons = []
        import pandas as pd
        for file in (stage/'data/processed').glob('*.csv'):
            previous = PROJECT/'data/processed'/file.name
            new_frame = pd.read_csv(file,low_memory=False)
            old_frame = pd.read_csv(previous,low_memory=False) if previous.exists() else None
            comparisons.append({'file':file.name,'new_rows':len(new_frame),
                'previous_rows':None if old_frame is None else len(old_frame),
                'new_sha256':digest(file),'previous_sha256':digest(previous) if previous.exists() else None,
                'new_columns':new_frame.columns.tolist()})
        (stage/'reports/output_comparison.json').write_text(json.dumps(comparisons,indent=2),encoding='utf-8')
        manifest = {'run_id':run_id,'backup':str(backup),'sources':{},'outputs':{}}
        for file in (PROJECT/'data/raw').glob('*.csv'):
            manifest['sources'][file.name] = digest(file)
        for file in stage.rglob('*'):
            if file.is_file() and 'logs' not in file.parts:
                manifest['outputs'][file.relative_to(stage).as_posix()] = digest(file)
        (stage/'pipeline_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        run('reports/verify_project.py',stage,environment)
        # Une seule instruction RENAME pour toutes les tables, après dump.
        existing = set(inspect(engine).get_table_names())
        clauses = []
        for name in TABLE_FILES:
            old = identifier('old_'+uuid.uuid4().hex[:10]+'_'+name)
            if name in existing:
                clauses.append(f'`{name}` TO `{old}`')
            else:
                old = None
            clauses.append(f'`{prefix+name}` TO `{name}`')
            renamed.append((name,old))
        dump_database(engine,backup/'sql_before_publish')
        with engine.begin() as connection:
            connection.execute(text('RENAME TABLE '+', '.join(clauses)))
        sql_published = True
        for file in stage.rglob('*'):
            if file.is_file():
                relative = file.relative_to(stage)
                destination = PROJECT/relative
                destination.parent.mkdir(parents=True,exist_ok=True)
                temporary = destination.with_name(destination.name+'.new')
                shutil.copy2(file,temporary)
                published.append(relative)
                os.replace(temporary,destination)
        final_environment = dict(environment,ENERGYINSIGHT_OUTPUT_ROOT=str(PROJECT),ENERGYINSIGHT_TABLE_PREFIX='')
        run('reports/verify_project.py',PROJECT,final_environment)
        with engine.begin() as connection:
            for _,old in renamed:
                if old:
                    connection.execute(text(f'DROP TABLE `{old}`'))
        (PROJECT/'reports/pipeline_status.json').write_text(json.dumps({
            'status':'validated','run_id':run_id,'backup':str(backup),'stage':str(stage)},indent=2),encoding='utf-8')
        print('\nPIPELINE VALIDÉ. Sauvegarde : '+str(backup),flush=True)
    except Exception:
        error = traceback.format_exc()
        (stage/'reports').mkdir(parents=True,exist_ok=True)
        (stage/'reports/pipeline_error.log').write_text(error,encoding='utf-8')
        # Restaurer les fichiers publiés et l'ensemble des anciens noms de tables.
        for relative in reversed(published):
            destination = PROJECT/relative
            if (saved/relative).exists():
                shutil.copy2(saved/relative,destination)
            elif destination.exists():
                destination.unlink()
        if sql_published:
            with engine.begin() as connection:
                reverse = []
                for name,old in renamed:
                    reverse.append(f'`{name}` TO `{prefix+name}`')
                    if old:
                        reverse.append(f'`{old}` TO `{name}`')
                connection.execute(text('RENAME TABLE '+', '.join(reverse)))
        print(error,file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
