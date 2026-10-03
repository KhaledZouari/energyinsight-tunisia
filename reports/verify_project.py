"""Validation critique des fichiers, données, modèle, métriques et MySQL."""
from pathlib import Path
import ast
import hashlib
import json
import os
import platform
import subprocess
import sys
import warnings
import zipfile
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix)
from sklearn.model_selection import train_test_split
from sqlalchemy import text

PROJECT = Path(__file__).resolve().parents[1]
os.environ.setdefault('ENERGYINSIGHT_OUTPUT_ROOT', str(PROJECT))
sys.path.insert(0,str(PROJECT/'src'))
from project_config import OUTPUT_ROOT, get_engine, table_name, database_name
from database_io import TABLE_FILES, DATE_COLUMNS, prepare_dates
from ml_features import FEATURES, build_features


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    results = {'python':platform.python_version(),'scikit_learn':sklearn.__version__,'checks':{},'errors':[]}
    def check(name, condition, detail=None):
        results['checks'][name] = {'ok':bool(condition),'detail':detail}
        if not condition:
            results['errors'].append(name)
    try:
        pip = subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
        check('pip_check',pip.returncode==0,pip.stdout+pip.stderr)
        check('unique_active_venv',(PROJECT/'.venv/Scripts/python.exe').exists() and not (PROJECT.parent/'.venv').exists())
        for file in (PROJECT/'src').glob('*.py'):
            ast.parse(file.read_text(encoding='utf-8'))
        required = list(TABLE_FILES.values())+['models/fraud_detection_model.joblib','models/model_metadata.json',
            'reports/test_predictions.csv','reports/baseline_metrics.csv','reports/model_comparison.csv',
            'reports/validation_thresholds.csv','reports/confusion_matrix.png','reports/data_summary.json',
            'exports/client_predictions.csv','exports/model_metrics.csv','pipeline_manifest.json']
        for relative in required:
            check('file:'+relative,(OUTPUT_ROOT/relative).is_file())
        if results['errors']:
            raise ValueError('Fichiers ou environnement incomplets')
        metadata = json.loads((OUTPUT_ROOT/'models/model_metadata.json').read_text(encoding='utf-8'))
        summary = json.loads((OUTPUT_ROOT/'reports/data_summary.json').read_text(encoding='utf-8'))
        manifest = json.loads((OUTPUT_ROOT/'pipeline_manifest.json').read_text(encoding='utf-8'))
        for name,sha in manifest['sources'].items():
            check('raw_hash:'+name,digest(PROJECT/'data/raw'/name)==sha)
        for relative,sha in manifest['outputs'].items():
            check('output_hash:'+relative,(OUTPUT_ROOT/relative).exists() and digest(OUTPUT_ROOT/relative)==sha)
        frames = {name:pd.read_csv(OUTPUT_ROOT/relative,low_memory=False) for name,relative in TABLE_FILES.items()}
        clients = frames['clients_clean']
        monthly = frames['monthly_electricity_consumption']
        features = frames['client_consumption_features']
        dataset = frames['client_ml_dataset']
        predictions = frames['client_predictions']
        metrics = frames['model_metrics'].iloc[0]
        for name,frame in frames.items():
            if 'client_id' in frame:
                check('unique_clients:'+name,frame.client_id.notna().all() and frame.client_id.is_unique)
        check('client_count',len(clients)==summary['clients']==len(dataset)==len(predictions),len(clients))
        check('client_ids',set(clients.client_id)==set(dataset.client_id)==set(predictions.client_id))
        check('target_binary',clients.target.isin([0,1]).all() and dataset.target.isin([0,1]).all())
        check('target_join',dataset.set_index('client_id').target.equals(clients.set_index('client_id').target))
        check('predictions_target',predictions.set_index('client_id').actual_target.equals(dataset.set_index('client_id').target))
        check('anomaly_count',int(clients.target.sum())==summary['anomalies'],int(clients.target.sum()))
        check('months',monthly.month.is_unique and len(monthly)==summary['months'],len(monthly))
        check('monthly_dates',monthly.month.min()==summary['first_month'] and monthly.month.max()==summary['last_month'])
        raw_rows = electric_rows = valid_rows = 0
        first_date = last_date = None
        consumption_columns = [f'consommation_level_{i}' for i in range(1,5)]
        for chunk in pd.read_csv(PROJECT/'data/raw/invoice_train.csv',
                usecols=['client_id','invoice_date','counter_type']+consumption_columns,
                chunksize=200_000,low_memory=False):
            raw_rows += len(chunk)
            electric = chunk.loc[chunk.counter_type.astype('string').str.strip().str.upper().eq('ELEC')]
            electric_rows += len(electric)
            dates = pd.to_datetime(electric.invoice_date,format='%Y-%m-%d',errors='coerce')
            totals = electric[consumption_columns].apply(pd.to_numeric,errors='coerce').sum(axis=1,min_count=1)
            ids = electric.client_id.astype('string').str.strip().replace('',pd.NA)
            valid = dates.notna() & totals.notna() & ids.notna()
            valid_rows += int(valid.sum())
            if valid.any():
                minimum,maximum = dates[valid].min(),dates[valid].max()
                first_date = minimum if first_date is None else min(first_date,minimum)
                last_date = maximum if last_date is None else max(last_date,maximum)
        check('raw_invoice_count',raw_rows==summary['raw_invoice_rows'],raw_rows)
        check('raw_electric_count',electric_rows==summary['electric_invoice_rows'],electric_rows)
        check('raw_valid_count',valid_rows==summary['valid_electric_invoice_rows'],valid_rows)
        check('raw_date_range',str(first_date.date())==summary['first_invoice_date'] and
            str(last_date.date())==summary['last_invoice_date'],[str(first_date.date()),str(last_date.date())])
        check('invoice_count',int(monthly.invoice_count.sum())==int(features.invoice_count.sum())==summary['valid_electric_invoice_rows'])
        check('consumption_totals',np.isclose(monthly.total_consumption.sum(),features.consumption_sum.sum()))
        check('means',np.allclose(features.consumption_mean,features.consumption_sum/features.invoice_count))
        check('std_nonnegative',features.consumption_std.ge(0).all())
        eligible = dataset.a_facture_electrique.astype(bool)
        check('electricity_indicator',eligible.equals(dataset.invoice_count.notna()))
        unknown = dataset.loc[~eligible]
        check('excluded_count',len(unknown)==metadata['excluded_rows']==summary['clients_without_electricity'],len(unknown))
        check('unknown_is_null',unknown[['consumption_sum','consumption_mean','consumption_max','consumption_min',
            'consumption_std','invoice_count','billing_history_days','first_invoice_date','last_invoice_date']].isna().all().all())
        check('excluded_not_scored',predictions.loc[~predictions.a_facture_electrique.astype(bool),
            ['predicted_target','anomaly_probability']].isna().all().all())
        check('split_labels',set(predictions.jeu)=={'train','validation','test','exclu_sans_facture'})
        for label in ['train','validation','test']:
            check('split_count:'+label,int(predictions.jeu.eq(label).sum())==metadata[label+'_rows'])
        check('split_coverage',predictions.jeu.ne('exclu_sans_facture').equals(predictions.a_facture_electrique.astype(bool)))
        # Reconstruire le split à partir des identifiants triés, sans utiliser les scores test.
        sorted_dataset = dataset.sort_values('client_id').reset_index(drop=True)
        rows = sorted_dataset.index[sorted_dataset.a_facture_electrique.astype(bool)].to_numpy()
        train_val, test_rows = train_test_split(rows,test_size=.20,random_state=42,
            stratify=sorted_dataset.loc[rows,'target'])
        train_rows, validation_rows = train_test_split(train_val,test_size=.25,random_state=42,
            stratify=sorted_dataset.loc[train_val,'target'])
        for label,indices in [('train',train_rows),('validation',validation_rows),('test',test_rows)]:
            check('split_reproducible:'+label,set(sorted_dataset.loc[indices,'client_id'])==
                set(predictions.loc[predictions.jeu.eq(label),'client_id']))
        threshold = metadata['decision_threshold']
        check('threshold',0<threshold<1 and np.allclose(predictions.seuil,threshold) and np.isclose(metrics.threshold,threshold))
        scored = predictions[predictions.jeu.ne('exclu_sans_facture')]
        check('threshold_predictions',scored.predicted_target.eq(scored.anomaly_probability.ge(threshold).astype(int)).all())
        check('prediction_alias',predictions.prediction.equals(predictions.predicted_target) and predictions.probabilite_anomalie.equals(predictions.anomaly_probability))
        test = predictions.loc[predictions.jeu.eq('test')]
        check('test_only',metrics.evaluation_set=='test' and metadata['evaluation_set']=='test')
        cm = confusion_matrix(test.actual_target,test.predicted_target,labels=[0,1])
        check('confusion_matrix',np.array_equal(cm.ravel(),metrics[['tn','fp','fn','tp']].astype(int).to_numpy()),cm.tolist())
        calculated = {'accuracy':accuracy_score(test.actual_target,test.predicted_target),
            'precision':precision_score(test.actual_target,test.predicted_target,zero_division=0),
            'recall':recall_score(test.actual_target,test.predicted_target,zero_division=0),
            'f1_score':f1_score(test.actual_target,test.predicted_target,zero_division=0),
            'roc_auc':roc_auc_score(test.actual_target,test.anomaly_probability),
            'average_precision':average_precision_score(test.actual_target,test.anomaly_probability)}
        for name,value in calculated.items():
            check('metric:'+name,np.isclose(value,metrics[name],rtol=1e-9,atol=1e-10),value)
        saved_test = pd.read_csv(OUTPUT_ROOT/'reports/test_predictions.csv')
        pd.testing.assert_frame_equal(test.sort_values('client_id').reset_index(drop=True),
            saved_test.sort_values('client_id').reset_index(drop=True),check_dtype=False)
        check('model_version',metadata['scikit_learn_version']==sklearn.__version__)
        check('python_version',metadata['python_version']==platform.python_version())
        check('model_hash',digest(OUTPUT_ROOT/'models/fraud_detection_model.joblib')==metadata['model_sha256'])
        check('dataset_hash',digest(OUTPUT_ROOT/'data/processed/client_ml_dataset.csv')==metadata['dataset_sha256'])
        with warnings.catch_warnings():
            warnings.simplefilter('error',InconsistentVersionWarning)
            model = joblib.load(OUTPUT_ROOT/'models/fraud_detection_model.joblib')
        check('feature_names',list(model.feature_names_in_)==metadata['features']==FEATURES)
        indexed = dataset.set_index('client_id').loc[scored.client_id].reset_index()
        probabilities = model.predict_proba(build_features(indexed))[:,1]
        check('model_predictions',np.allclose(probabilities,scored.anomaly_probability,rtol=1e-9,atol=1e-10))
        comparison = pd.read_csv(OUTPUT_ROOT/'reports/model_comparison.csv')
        check('three_models',set(comparison.model)=={'LogisticRegression','RandomForest','HistGradientBoosting'})
        selected = comparison.sort_values(['validation_f1','validation_average_precision'],ascending=False).iloc[0]
        check('validation_selection',selected.model==metrics.model and np.isclose(selected.threshold,threshold))
        thresholds = pd.read_csv(OUTPUT_ROOT/'reports/validation_thresholds.csv')
        for _,row in comparison.iterrows():
            candidate = thresholds.loc[thresholds.model.eq(row.model)].sort_values('f1',ascending=False).iloc[0]
            check('validation_threshold_optimum:'+row.model,np.isclose(candidate.f1,row.validation_f1))
        validation = predictions.loc[predictions.jeu.eq('validation')]
        check('validation_f1',np.isclose(f1_score(validation.actual_target,validation.predicted_target),selected.validation_f1))
        baseline = pd.read_csv(OUTPUT_ROOT/'reports/baseline_metrics.csv').iloc[0]
        check('baseline',baseline.evaluation_set=='test' and baseline.f1_score==0 and np.isclose(baseline.accuracy,test.actual_target.eq(0).mean()))
        for relative in ['client_predictions.csv','monthly_electricity_consumption.csv','clients_clean.csv']:
            check('export:'+relative,digest(OUTPUT_ROOT/'exports'/relative)==digest(OUTPUT_ROOT/'data/processed'/relative))
        engine = get_engine()
        try:
            with engine.connect() as connection:
                results['mysql_version'] = connection.execute(text('SELECT VERSION()')).scalar_one()
                for name,frame in frames.items():
                    sql_name = table_name(name)
                    sql = pd.read_sql(text(f'SELECT * FROM `{sql_name}`'),connection)
                    check('sql_count:'+name,len(sql)==len(frame),len(sql))
                    expected = prepare_dates(frame.copy())
                    sql = prepare_dates(sql)
                    for boolean in ['a_facture_electrique']:
                        if boolean in expected:
                            expected[boolean] = expected[boolean].astype(bool)
                            sql[boolean] = sql[boolean].astype(bool)
                    keys = ['client_id'] if 'client_id' in expected else ['month'] if 'month' in expected else ['model']
                    pd.testing.assert_frame_equal(expected.sort_values(keys).reset_index(drop=True),
                        sql[expected.columns].sort_values(keys).reset_index(drop=True),check_dtype=False,check_exact=False,rtol=1e-8,atol=1e-8)
                    check('sql_values:'+name,True)
                    sql_types = connection.execute(text('SELECT COLUMN_NAME,DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS '
                        'WHERE TABLE_SCHEMA=:db AND TABLE_NAME=:table'),{'db':database_name(),'table':sql_name}).all()
                    for column,dtype in sql_types:
                        if column in DATE_COLUMNS:
                            check('sql_date:'+name+'.'+column,dtype in {'date','datetime','timestamp'},dtype)
        finally:
            engine.dispose()
        results['data_summary'] = summary
        results['test_metrics'] = calculated
        results['powerbi'] = {}
        for file in (PROJECT/'powerbi').glob('*.pbix'):
            with zipfile.ZipFile(file) as archive:
                check('pbix_archive:'+file.name,archive.testzip() is None)
                results['powerbi'][file.name] = 'Archive intacte ; actualisation visuelle manuelle requise'
    except Exception as error:
        results['errors'].append(type(error).__name__+': '+str(error))
    results['status'] = 'passed' if not results['errors'] else 'failed'
    destination = OUTPUT_ROOT/'reports/verification_results.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':results['status'],'checks':len(results['checks']),'errors':results['errors']},ensure_ascii=False))
    return 0 if not results['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
