"""Features explicites, indépendantes de la cible et des ensembles du split."""
import numpy as np
import pandas as pd

CATEGORIES = ['district','region','client_catg']
NUMERIC = ['creation_year','creation_month','consumption_sum','invoice_count',
           'consumption_max','consumption_min','zero_consumption_count',
           'negative_consumption_count','consumption_mean','consumption_std','billing_history_days']
FEATURES = CATEGORIES + NUMERIC


def build_features(dataset):
    # Dates absolues de facturation exclues : périodes variables, absence de date du diagnostic.
    # creation_year/month existent déjà ; pas de duplication des mêmes variables.
    frame = dataset[FEATURES].copy()
    for column in CATEGORIES:
        values = pd.to_numeric(frame[column],errors='coerce').astype('Int64')
        frame[column] = values.astype('string').fillna('Inconnu').astype(object)
    for column in NUMERIC:
        frame[column] = pd.to_numeric(frame[column],errors='coerce').astype(float)
    frame[NUMERIC] = frame[NUMERIC].replace([np.inf,-np.inf],np.nan)
    return frame
