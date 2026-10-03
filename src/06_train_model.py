"""Comparaison train/CV, choix sur validation et évaluation finale indépendante."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import platform
import shutil
import warnings
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import sklearn
from sqlalchemy import text
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, precision_recall_curve, confusion_matrix,
    ConfusionMatrixDisplay)
from sklearn.exceptions import InconsistentVersionWarning
from threadpoolctl import threadpool_limits
from project_config import (PROCESSED_DIR, REPORTS_DIR, MODELS_DIR, EXPORTS_DIR,
    get_engine, table_name)
from database_io import import_csv
from ml_features import CATEGORIES, NUMERIC, FEATURES, build_features


def hash_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def make_pipeline(name):
    numeric = Pipeline([('missing_values',SimpleImputer(strategy='median')),
                        ('scale',StandardScaler())])
    encoder = (OneHotEncoder(handle_unknown='ignore',sparse_output=False) if name != 'HistGradientBoosting'
               else OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=np.nan))
    categorical = Pipeline([('missing_values',SimpleImputer(strategy='most_frequent')),('encoding',encoder)])
    preprocessor = ColumnTransformer([('numeric',numeric,NUMERIC),('categorical',categorical,CATEGORIES)])
    models = {
        'LogisticRegression':LogisticRegression(class_weight='balanced',max_iter=1500,random_state=42),
        'RandomForest':RandomForestClassifier(n_estimators=150,max_depth=18,min_samples_leaf=2,
            class_weight='balanced_subsample',random_state=42,n_jobs=4),
        'HistGradientBoosting':HistGradientBoostingClassifier(class_weight='balanced',
            max_iter=150,max_leaf_nodes=31,learning_rate=.08,l2_regularization=1.,
            categorical_features=[False]*len(NUMERIC)+[True]*len(CATEGORIES),
            early_stopping=False,random_state=42),
    }
    return Pipeline([('preparation',preprocessor),('model',models[name])])


def metrics(y, predictions, probabilities):
    tn,fp,fn,tp = confusion_matrix(y,predictions,labels=[0,1]).ravel()
    return {'accuracy':accuracy_score(y,predictions),
            'precision':precision_score(y,predictions,zero_division=0),
            'recall':recall_score(y,predictions,zero_division=0),
            'f1_score':f1_score(y,predictions,zero_division=0),
            'roc_auc':roc_auc_score(y,probabilities),
            'average_precision':average_precision_score(y,probabilities),
            'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}


def main():
    for directory in [REPORTS_DIR,MODELS_DIR,EXPORTS_DIR]:
        directory.mkdir(parents=True,exist_ok=True)
    engine = get_engine()
    try:
        with engine.connect() as connection:
            dataset = pd.read_sql(text(f'SELECT * FROM `{table_name("client_ml_dataset")}` ORDER BY client_id'),connection)
        if not dataset.client_id.is_unique or not dataset.target.isin([0,1]).all():
            raise ValueError('Identifiants ou cibles invalides')
        eligible = dataset.a_facture_electrique.astype(bool)
        indices = dataset.index[eligible].to_numpy()
        train_val, test = train_test_split(indices,test_size=.20,random_state=42,stratify=dataset.loc[indices,'target'])
        train, validation = train_test_split(train_val,test_size=.25,random_state=42,stratify=dataset.loc[train_val,'target'])
        X = build_features(dataset.loc[eligible])
        y = dataset.target.astype(int)
        print(f'Train={len(train)}, validation={len(validation)}, test={len(test)}, exclus={int((~eligible).sum())}',flush=True)
        cv = StratifiedKFold(n_splits=3,shuffle=True,random_state=42)
        comparison = []
        fitted = {}
        validation_probabilities = {}
        thresholds = []
        for name in ['LogisticRegression','RandomForest','HistGradientBoosting']:
            print('Comparaison : '+name,flush=True)
            pipeline = make_pipeline(name)
            scores = cross_validate(pipeline,X.loc[train],y.loc[train],cv=cv,n_jobs=1,error_score='raise',
                scoring={'average_precision':'average_precision','roc_auc':'roc_auc','f1':'f1'})
            pipeline.fit(X.loc[train],y.loc[train])
            probabilities = pipeline.predict_proba(X.loc[validation])[:,1]
            precision,recall,cuts = precision_recall_curve(y.loc[validation],probabilities)
            f1 = np.divide(2*precision[:-1]*recall[:-1],precision[:-1]+recall[:-1],
                           out=np.zeros(len(cuts)),where=(precision[:-1]+recall[:-1])>0)
            best = int(np.argmax(f1))
            threshold = float(cuts[best])
            row = {'model':name,'threshold':threshold,'validation_f1':float(f1[best]),
                'validation_precision':float(precision[best]),'validation_recall':float(recall[best]),
                'validation_average_precision':average_precision_score(y.loc[validation],probabilities),
                'validation_f1_default':f1_score(y.loc[validation],probabilities>=.5,zero_division=0),
                'cv_ap_mean':float(scores['test_average_precision'].mean()),
                'cv_ap_std':float(scores['test_average_precision'].std()),
                'cv_roc_auc_mean':float(scores['test_roc_auc'].mean()),
                'cv_f1_default_mean':float(scores['test_f1'].mean())}
            comparison.append(row)
            fitted[name] = pipeline
            validation_probabilities[name] = probabilities
            thresholds.append(pd.DataFrame({'model':name,'threshold':cuts,'precision':precision[:-1],
                                            'recall':recall[:-1],'f1':f1}))
            print(json.dumps(row),flush=True)
        selected = max(comparison,key=lambda row:(row['validation_f1'],row['validation_average_precision']))
        name,threshold = selected['model'],selected['threshold']
        pipeline = fitted[name]  # Pas de réentraînement : seuil validé pour ce modèle précis.
        pd.DataFrame(comparison).to_csv(REPORTS_DIR/'model_comparison.csv',index=False)
        pd.concat(thresholds,ignore_index=True).to_csv(REPORTS_DIR/'validation_thresholds.csv',index=False)
        fig,ax = plt.subplots(figsize=(8,6))
        for model,probabilities in validation_probabilities.items():
            precision,recall,_ = precision_recall_curve(y.loc[validation],probabilities)
            ax.plot(recall,precision,label=model)
        ax.set(xlabel='Rappel',ylabel='Précision',title='Précision-rappel — validation uniquement')
        ax.legend(); fig.tight_layout(); fig.savefig(REPORTS_DIR/'validation_precision_recall.png',dpi=180); plt.close(fig)
        # Le modèle et le seuil sont maintenant figés. Une seule évaluation test.
        probabilities = pipeline.predict_proba(X.loc[test])[:,1]
        predictions = (probabilities>=threshold).astype(int)
        final_metrics = dict(model=name,evaluation_set='test',threshold=threshold,**metrics(y.loc[test],predictions,probabilities))
        pd.DataFrame([final_metrics]).to_csv(REPORTS_DIR/'model_metrics.csv',index=False)
        (REPORTS_DIR/'test_metrics.json').write_text(json.dumps(final_metrics,indent=2),encoding='utf-8')
        dummy = DummyClassifier(strategy='most_frequent').fit(X.loc[train],y.loc[train])
        baseline = dict(model='DummyClassifier_most_frequent',evaluation_set='test',
            **metrics(y.loc[test],dummy.predict(X.loc[test]),dummy.predict_proba(X.loc[test])[:,1]))
        pd.DataFrame([baseline]).to_csv(REPORTS_DIR/'baseline_metrics.csv',index=False)
        model_path = MODELS_DIR/'fraud_detection_model.joblib'
        joblib.dump(pipeline,model_path,compress=3)
        with warnings.catch_warnings():
            warnings.simplefilter('error',InconsistentVersionWarning)
            restored = joblib.load(model_path)
        if not np.allclose(restored.predict_proba(X.loc[test[:1000]])[:,1],probabilities[:1000]):
            raise ValueError('Modèle sauvegardé différent du modèle évalué')
        exported = pd.DataFrame({'client_id':dataset.client_id,'actual_target':y,
            'jeu':'exclu_sans_facture','anomaly_probability':np.nan,'predicted_target':pd.Series(pd.NA,index=dataset.index,dtype='Int64'),
            'seuil':threshold,'a_facture_electrique':eligible})
        for label,rows in [('train',train),('validation',validation),('test',test)]:
            # Pour le test, réutiliser exactement les probabilités de l'évaluation finale.
            values = probabilities if label=='test' else pipeline.predict_proba(X.loc[rows])[:,1]
            exported.loc[rows,'jeu'] = label
            exported.loc[rows,'anomaly_probability'] = values
            exported.loc[rows,'predicted_target'] = (values>=threshold).astype(int)
        exported['prediction'] = exported.predicted_target
        exported['probabilite_anomalie'] = exported.anomaly_probability
        exported['risk_level'] = pd.cut(exported.anomaly_probability,bins=[-.01,.30,.60,.80,1.],
            labels=['Faible','Modéré','Élevé','Critique']).astype('string').fillna('Non évalué')
        exported.to_csv(PROCESSED_DIR/'client_predictions.csv',index=False)
        exported[exported.jeu.eq('test')].to_csv(REPORTS_DIR/'test_predictions.csv',index=False)
        for file in ['client_predictions.csv','monthly_electricity_consumption.csv','clients_clean.csv']:
            shutil.copy2(PROCESSED_DIR/file,EXPORTS_DIR/file)
        shutil.copy2(REPORTS_DIR/'model_metrics.csv',EXPORTS_DIR/'model_metrics.csv')
        metadata = {'python_version':platform.python_version(),'scikit_learn_version':sklearn.__version__,
            'model_type':type(pipeline.named_steps['model']).__name__,'decision_threshold':threshold,
            'training_date':datetime.now(ZoneInfo('Europe/Paris')).isoformat(),
            'features':FEATURES,'target':'target','train_rows':len(train),'validation_rows':len(validation),
            'test_rows':len(test),'excluded_rows':int((~eligible).sum()),'random_state':42,
            'split':'stratified_unique_clients_60_20_20','cv':'StratifiedKFold_3_train_only',
            'selection':'maximum validation F1, then average precision',
            'evaluation_set':'test','dataset_sha256':hash_file(PROCESSED_DIR/'client_ml_dataset.csv'),
            'model_sha256':hash_file(model_path),'model_trained_on':'train_only',
            'scope':'retrospective classification; target diagnosis date unavailable',
            'removed_features':['client_id','creation_date','first_invoice_date','last_invoice_date','a_facture_electrique']}
        (MODELS_DIR/'model_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        import_csv(engine,'client_predictions',PROCESSED_DIR/'client_predictions.csv')
        import_csv(engine,'model_metrics',REPORTS_DIR/'model_metrics.csv')
        print('Résultats test : '+json.dumps(final_metrics),flush=True)
        print('Baseline test : '+json.dumps(baseline),flush=True)
    finally:
        engine.dispose()


if __name__ == '__main__':
    with threadpool_limits(limits=4):
        main()
