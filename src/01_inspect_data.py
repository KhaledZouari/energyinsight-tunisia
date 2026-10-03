from pathlib import Path
import pandas as pd

# Afficher toutes les colonnes dans le terminal
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

# Construire les chemins automatiquement
PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_DIR / "data" / "raw"

CLIENT_FILE = RAW_DATA_DIR / "client_train.csv"
INVOICE_FILE = RAW_DATA_DIR / "invoice_train.csv"

# Vérifier que les fichiers existent
print("=== VÉRIFICATION DES FICHIERS ===")
print("client_train.csv :", CLIENT_FILE.exists())
print("invoice_train.csv :", INVOICE_FILE.exists())

if not CLIENT_FILE.exists() or not INVOICE_FILE.exists():
    raise FileNotFoundError(
        "Les fichiers CSV doivent être placés dans le dossier data/raw."
    )

# Le fichier clients peut être chargé entièrement
clients = pd.read_csv(CLIENT_FILE)

# Le fichier des factures est très volumineux :
# on charge seulement les 10 000 premières lignes
invoices_sample = pd.read_csv(
    INVOICE_FILE,
    nrows=10_000,
    low_memory=False
)

print("\n=== DIMENSIONS ===")
print("Clients :", clients.shape)
print("Échantillon des factures :", invoices_sample.shape)

print("\n=== COLONNES CLIENTS ===")
print(clients.columns.tolist())

print("\n=== COLONNES FACTURES ===")
print(invoices_sample.columns.tolist())

print("\n=== 5 PREMIERS CLIENTS ===")
print(clients.head())

print("\n=== 5 PREMIÈRES FACTURES ===")
print(invoices_sample.head())

print("\n=== TYPES DES COLONNES CLIENTS ===")
print(clients.dtypes)

print("\n=== TYPES DES COLONNES FACTURES ===")
print(invoices_sample.dtypes)

print("\n=== VALEURS MANQUANTES — CLIENTS ===")
print(clients.isna().sum())

print("\n=== VALEURS MANQUANTES — FACTURES ===")
print(invoices_sample.isna().sum())

print("\nInspection terminée avec succès.")