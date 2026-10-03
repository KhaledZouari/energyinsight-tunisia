from pathlib import Path

import pandas as pd
from project_config import PROCESSED_DIR


# ============================================================
# 1. DÉFINITION DES CHEMINS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"

INPUT_FILE = RAW_DIR / "client_train.csv"
OUTPUT_FILE = PROCESSED_DIR / "clients_clean.csv"

# Créer le dossier processed s'il n'existe pas
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. VÉRIFICATION DU FICHIER
# ============================================================

print("=== VÉRIFICATION DU FICHIER ===")

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Fichier introuvable : {INPUT_FILE}"
    )

print("Fichier trouvé :", INPUT_FILE)


# ============================================================
# 3. CHARGEMENT DES DONNÉES
# ============================================================

print("\n=== CHARGEMENT DES CLIENTS ===")

clients = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print("Dimensions initiales :", clients.shape)
print("Colonnes initiales :", clients.columns.tolist())
print("Doublons complets :", clients.duplicated().sum())


# ============================================================
# 4. NETTOYAGE DES NOMS DE COLONNES
# ============================================================

clients.columns = (
    clients.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
)

# Le dataset original contient "disrict" au lieu de "district"
if "disrict" in clients.columns:
    clients = clients.rename(
        columns={"disrict": "district"}
    )

print("\nColonnes après correction :")
print(clients.columns.tolist())


# ============================================================
# 5. VÉRIFICATION DES COLONNES OBLIGATOIRES
# ============================================================

required_columns = {
    "district",
    "client_id",
    "client_catg",
    "region",
    "creation_date",
    "target"
}

missing_columns = required_columns - set(clients.columns)

if missing_columns:
    raise ValueError(
        f"Colonnes obligatoires manquantes : {missing_columns}"
    )

print("Identifiants clients dupliqués :", clients.duplicated(subset="client_id").sum())


# ============================================================
# 6. NETTOYAGE DES IDENTIFIANTS
# ============================================================

clients["client_id"] = (
    clients["client_id"]
    .astype("string")
    .str.strip()
)

# Remplacer les identifiants vides par des valeurs manquantes
clients["client_id"] = clients["client_id"].replace(
    "",
    pd.NA
)


# ============================================================
# 7. CONVERSION DE LA DATE
# ============================================================

clients["creation_date"] = pd.to_datetime(
    clients["creation_date"],
    format="%d/%m/%Y",
    errors="coerce"
)


# ============================================================
# 8. CONVERSION DES COLONNES NUMÉRIQUES
# ============================================================

numeric_columns = [
    "district",
    "client_catg",
    "region",
    "target"
]

for column in numeric_columns:
    clients[column] = pd.to_numeric(
        clients[column],
        errors="coerce"
    )


# ============================================================
# 9. TRAITEMENT DES VALEURS MANQUANTES
# ============================================================

print("\nValeurs manquantes avant traitement :")
print(clients.isna().sum())

# client_id et target sont indispensables
clients = clients.dropna(
    subset=["client_id", "target"]
)


# ============================================================
# 10. SUPPRESSION DES DOUBLONS
# ============================================================

clients = clients.drop_duplicates(
    subset="client_id",
    keep="first"
)


# ============================================================
# 11. CORRECTION DES TYPES
# ============================================================

clients["district"] = clients["district"].astype("Int64")
clients["client_catg"] = clients["client_catg"].astype("Int64")
clients["region"] = clients["region"].astype("Int64")
if not clients["target"].isin([0, 1]).all():
    raise ValueError("La cible doit contenir uniquement 0 et 1.")
clients["target"] = clients["target"].astype("int8")


# ============================================================
# 12. CRÉATION DE NOUVELLES COLONNES
# ============================================================

clients["creation_year"] = (
    clients["creation_date"]
    .dt.year
    .astype("Int64")
)

clients["creation_month"] = (
    clients["creation_date"]
    .dt.month
    .astype("Int64")
)


# ============================================================
# 13. TRI DES DONNÉES
# ============================================================

clients = clients.sort_values(
    by="client_id"
).reset_index(drop=True)


# ============================================================
# 14. AFFICHAGE DU RÉSULTAT
# ============================================================

print("\n=== RÉSULTAT DU NETTOYAGE ===")
print("Dimensions finales :", clients.shape)

print("\nValeurs manquantes après traitement :")
print(clients.isna().sum())

print("\nTypes des colonnes :")
print(clients.dtypes)

print("\nRépartition de target :")
print(clients["target"].value_counts())

print("\nCinq premières lignes :")
print(clients.head())


# ============================================================
# 15. ENREGISTREMENT
# ============================================================

clients.to_csv(
    OUTPUT_FILE,
    index=False,
    date_format="%Y-%m-%d"
)

print("\n=== ENREGISTREMENT TERMINÉ ===")
print("Fichier créé :", OUTPUT_FILE)
print("Nettoyage des clients terminé avec succès.")
