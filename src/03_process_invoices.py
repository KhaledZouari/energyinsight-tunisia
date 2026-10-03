from pathlib import Path

import numpy as np
import pandas as pd
import json
from project_config import PROCESSED_DIR, REPORTS_DIR


# ============================================================
# 1. DÉFINITION DES CHEMINS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

INVOICE_FILE = RAW_DIR / "invoice_train.csv"
CLIENT_FILE = PROCESSED_DIR / "clients_clean.csv"

MONTHLY_OUTPUT = (
    PROCESSED_DIR / "monthly_electricity_consumption.csv"
)

CLIENT_FEATURES_OUTPUT = (
    PROCESSED_DIR / "client_consumption_features.csv"
)

ML_DATASET_OUTPUT = (
    PROCESSED_DIR / "client_ml_dataset.csv"
)

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. PARAMÈTRES
# ============================================================

CHUNK_SIZE = 200_000

CONSUMPTION_COLUMNS = [
    "consommation_level_1",
    "consommation_level_2",
    "consommation_level_3",
    "consommation_level_4"
]

USE_COLUMNS = [
    "client_id",
    "invoice_date",
    "counter_type",
    "consommation_level_1",
    "consommation_level_2",
    "consommation_level_3",
    "consommation_level_4"
]


# ============================================================
# 3. VÉRIFICATION DES FICHIERS
# ============================================================

print("=== VÉRIFICATION DES FICHIERS ===")

if not INVOICE_FILE.exists():
    raise FileNotFoundError(
        f"Fichier introuvable : {INVOICE_FILE}"
    )

if not CLIENT_FILE.exists():
    raise FileNotFoundError(
        f"Fichier introuvable : {CLIENT_FILE}"
    )

print("Factures :", INVOICE_FILE)
print("Clients nettoyés :", CLIENT_FILE)


# ============================================================
# 4. LISTES POUR STOCKER LES AGRÉGATIONS
# ============================================================

monthly_parts = []
client_feature_parts = []

total_rows_read = 0
total_electricity_rows = 0
total_valid_rows = 0


# ============================================================
# 5. LECTURE DU FICHIER PAR BLOCS
# ============================================================

print("\n=== TRAITEMENT DES FACTURES ===")

reader = pd.read_csv(
    INVOICE_FILE,
    usecols=USE_COLUMNS,
    chunksize=CHUNK_SIZE,
    low_memory=False
)

for chunk_number, chunk in enumerate(reader, start=1):

    rows_in_chunk = len(chunk)
    total_rows_read += rows_in_chunk

    print(
        f"\nBloc {chunk_number} : "
        f"{rows_in_chunk:,} lignes lues"
    )

    # Uniformiser les noms de colonnes
    chunk.columns = (
        chunk.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # Nettoyer les identifiants
    chunk["client_id"] = (
        chunk["client_id"]
        .astype("string")
        .str.strip()
    )
    chunk["client_id"] = chunk["client_id"].replace("", pd.NA)

    # Nettoyer le type du compteur
    chunk["counter_type"] = (
        chunk["counter_type"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    # Garder uniquement les factures d'électricité
    chunk = chunk[
        chunk["counter_type"] == "ELEC"
    ].copy()

    electricity_rows = len(chunk)
    total_electricity_rows += electricity_rows

    print(
        f"  Factures électriques : "
        f"{electricity_rows:,}"
    )

    if chunk.empty:
        continue

    # Convertir la date de facturation
    chunk["invoice_date"] = pd.to_datetime(
        chunk["invoice_date"],
        format="%Y-%m-%d",
        errors="coerce"
    )

    # Convertir les colonnes de consommation
    for column in CONSUMPTION_COLUMNS:
        chunk[column] = pd.to_numeric(
            chunk[column],
            errors="coerce"
        )

    # Calculer la consommation totale des quatre niveaux
    chunk["total_consumption"] = (
        chunk[CONSUMPTION_COLUMNS]
        .sum(axis=1, min_count=1)
    )

    # Supprimer uniquement les lignes inutilisables
    chunk = chunk.dropna(
        subset=[
            "client_id",
            "invoice_date",
            "total_consumption"
        ]
    )

    valid_rows = len(chunk)
    total_valid_rows += valid_rows

    print(
        f"  Factures valides : "
        f"{valid_rows:,}"
    )

    if chunk.empty:
        continue

    # Indicateurs utiles pour détecter les anomalies
    chunk["is_zero_consumption"] = (
        chunk["total_consumption"] == 0
    ).astype("int8")

    chunk["is_negative_consumption"] = (
        chunk["total_consumption"] < 0
    ).astype("int8")

    # Carré utilisé pour calculer l'écart-type par client
    chunk["consumption_squared"] = (
        chunk["total_consumption"].astype("float64") ** 2
    )

    # Créer le mois de facturation
    chunk["month"] = (
        chunk["invoice_date"]
        .dt.to_period("M")
        .astype("string")
    )

    # --------------------------------------------------------
    # 5.1 Agrégation mensuelle
    # --------------------------------------------------------

    monthly_chunk = (
        chunk
        .groupby("month", as_index=False)
        .agg(
            total_consumption=(
                "total_consumption",
                "sum"
            ),
            invoice_count=(
                "client_id",
                "size"
            )
        )
    )

    monthly_parts.append(monthly_chunk)

    # --------------------------------------------------------
    # 5.2 Agrégation par client
    # --------------------------------------------------------

    client_chunk = (
        chunk
        .groupby("client_id", as_index=False)
        .agg(
            consumption_sum=(
                "total_consumption",
                "sum"
            ),
            consumption_count=(
                "total_consumption",
                "count"
            ),
            consumption_max=(
                "total_consumption",
                "max"
            ),
            consumption_min=(
                "total_consumption",
                "min"
            ),
            consumption_squared_sum=(
                "consumption_squared",
                "sum"
            ),
            zero_consumption_count=(
                "is_zero_consumption",
                "sum"
            ),
            negative_consumption_count=(
                "is_negative_consumption",
                "sum"
            ),
            first_invoice_date=(
                "invoice_date",
                "min"
            ),
            last_invoice_date=(
                "invoice_date",
                "max"
            )
        )
    )

    client_feature_parts.append(client_chunk)


# ============================================================
# 6. REGROUPEMENT DES STATISTIQUES MENSUELLES
# ============================================================

if not monthly_parts:
    raise ValueError(
        "Aucune facture électrique valide n'a été trouvée."
    )

monthly_data = pd.concat(
    monthly_parts,
    ignore_index=True
)

monthly_data = (
    monthly_data
    .groupby("month", as_index=False)
    .agg(
        total_consumption=(
            "total_consumption",
            "sum"
        ),
        invoice_count=(
            "invoice_count",
            "sum"
        )
    )
)

monthly_data["average_consumption_per_invoice"] = (
    monthly_data["total_consumption"]
    / monthly_data["invoice_count"]
)

monthly_data["month"] = pd.to_datetime(
    monthly_data["month"] + "-01",
    errors="coerce"
)

monthly_data = (
    monthly_data
    .sort_values("month")
    .reset_index(drop=True)
)


# ============================================================
# 7. REGROUPEMENT DES STATISTIQUES PAR CLIENT
# ============================================================

client_features = pd.concat(
    client_feature_parts,
    ignore_index=True
)

client_features = (
    client_features
    .groupby("client_id", as_index=False)
    .agg(
        consumption_sum=(
            "consumption_sum",
            "sum"
        ),
        invoice_count=(
            "consumption_count",
            "sum"
        ),
        consumption_max=(
            "consumption_max",
            "max"
        ),
        consumption_min=(
            "consumption_min",
            "min"
        ),
        consumption_squared_sum=(
            "consumption_squared_sum",
            "sum"
        ),
        zero_consumption_count=(
            "zero_consumption_count",
            "sum"
        ),
        negative_consumption_count=(
            "negative_consumption_count",
            "sum"
        ),
        first_invoice_date=(
            "first_invoice_date",
            "min"
        ),
        last_invoice_date=(
            "last_invoice_date",
            "max"
        )
    )
)

# Moyenne de consommation par facture
client_features["consumption_mean"] = (
    client_features["consumption_sum"]
    / client_features["invoice_count"]
)

# Variance = moyenne des carrés - carré de la moyenne
client_features["consumption_variance"] = (
    client_features["consumption_squared_sum"]
    / client_features["invoice_count"]
) - (
    client_features["consumption_mean"] ** 2
)

# Éviter les petites valeurs négatives causées par les arrondis
client_features["consumption_variance"] = (
    client_features["consumption_variance"]
    .clip(lower=0)
)

# Calculer l'écart-type
client_features["consumption_std"] = np.sqrt(
    client_features["consumption_variance"]
)

# Durée entre la première et la dernière facture
client_features["billing_history_days"] = (
    client_features["last_invoice_date"]
    - client_features["first_invoice_date"]
).dt.days

# La somme des carrés n'est plus nécessaire
client_features = client_features.drop(
    columns=[
        "consumption_squared_sum",
        "consumption_variance"
    ]
)


# ============================================================
# 8. FUSION AVEC LES CLIENTS
# ============================================================

clients = pd.read_csv(
    CLIENT_FILE,
    parse_dates=["creation_date"]
)

clients["client_id"] = (
    clients["client_id"]
    .astype("string")
    .str.strip()
)

client_features["client_id"] = (
    client_features["client_id"]
    .astype("string")
    .str.strip()
)

ml_dataset = clients.merge(
    client_features,
    on="client_id",
    how="left",
    validate="one_to_one"
)

feature_columns = [
    "consumption_sum",
    "invoice_count",
    "consumption_max",
    "consumption_min",
    "zero_consumption_count",
    "negative_consumption_count",
    "consumption_mean",
    "consumption_std",
    "billing_history_days"
]

ml_dataset["a_facture_electrique"] = ml_dataset["invoice_count"].notna()
# Absence de facture != consommation nulle : statistiques et dates restent nulles.


# ============================================================
# 9. ENREGISTREMENT DES RÉSULTATS
# ============================================================

monthly_data.to_csv(
    MONTHLY_OUTPUT,
    index=False,
    date_format="%Y-%m-%d"
)

client_features.to_csv(
    CLIENT_FEATURES_OUTPUT,
    index=False,
    date_format="%Y-%m-%d"
)

ml_dataset.to_csv(
    ML_DATASET_OUTPUT,
    index=False,
    date_format="%Y-%m-%d"
)


# ============================================================
# 10. RÉSUMÉ FINAL
# ============================================================

print("\n=== TRAITEMENT TERMINÉ ===")

print(
    "Nombre total de lignes lues :",
    f"{total_rows_read:,}"
)

print(
    "Factures électriques trouvées :",
    f"{total_electricity_rows:,}"
)

print(
    "Factures électriques valides :",
    f"{total_valid_rows:,}"
)

print(
    "Nombre de mois :",
    len(monthly_data)
)

print(
    "Nombre de clients avec statistiques :",
    len(client_features)
)

print(
    "Dimensions du dataset ML :",
    ml_dataset.shape
)

print("\nFichiers créés :")
print("-", MONTHLY_OUTPUT)
print("-", CLIENT_FEATURES_OUTPUT)
print("-", ML_DATASET_OUTPUT)

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
(REPORTS_DIR / "data_summary.json").write_text(json.dumps({
    "raw_invoice_rows": total_rows_read,
    "electric_invoice_rows": total_electricity_rows,
    "valid_electric_invoice_rows": total_valid_rows,
    "clients": len(clients), "months": len(monthly_data),
    "first_month": str(monthly_data["month"].min().date()),
    "last_month": str(monthly_data["month"].max().date()),
    "first_invoice_date": str(client_features["first_invoice_date"].min().date()),
    "last_invoice_date": str(client_features["last_invoice_date"].max().date()),
    "anomalies": int(clients["target"].sum()),
    "clients_without_electricity": int((~ml_dataset["a_facture_electrique"]).sum())
}, indent=2), encoding="utf-8")
