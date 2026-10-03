from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from project_config import PROCESSED_DIR, REPORTS_DIR


# ============================================================
# 1. CHEMINS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

MONTHLY_FILE = (
    PROCESSED_DIR / "monthly_electricity_consumption.csv"
)

ML_FILE = (
    PROCESSED_DIR / "client_ml_dataset.csv"
)

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. VÉRIFICATION
# ============================================================

if not MONTHLY_FILE.exists():
    raise FileNotFoundError(
        f"Fichier introuvable : {MONTHLY_FILE}"
    )

if not ML_FILE.exists():
    raise FileNotFoundError(
        f"Fichier introuvable : {ML_FILE}"
    )


# ============================================================
# 3. CHARGEMENT
# ============================================================

monthly = pd.read_csv(
    MONTHLY_FILE,
    parse_dates=["month"]
)

clients = pd.read_csv(
    ML_FILE,
    low_memory=False
)

print("=== DIMENSIONS ===")
print("Données mensuelles :", monthly.shape)
print("Dataset clients ML :", clients.shape)


# ============================================================
# 4. VÉRIFICATIONS GÉNÉRALES
# ============================================================

print("\n=== VALEURS MANQUANTES ===")
print(clients.isna().sum())

print("\n=== DOUBLONS CLIENTS ===")
print(
    clients.duplicated(
        subset="client_id"
    ).sum()
)

print("\n=== RÉPARTITION DE TARGET ===")
target_counts = (
    clients["target"]
    .value_counts()
    .sort_index()
)

print(target_counts)

fraud_rate = clients["target"].mean() * 100

print(
    f"\nPourcentage de clients anormaux : "
    f"{fraud_rate:.2f} %"
)

print("\n=== PÉRIODE DES DONNÉES ===")
print("Premier mois :", monthly["month"].min())
print("Dernier mois :", monthly["month"].max())

print("\n=== STATISTIQUES DE CONSOMMATION ===")
print(
    clients[
        [
            "consumption_sum",
            "invoice_count",
            "consumption_mean",
            "consumption_max",
            "consumption_std"
        ]
    ].describe()
)


# ============================================================
# 5. STYLE DES GRAPHIQUES
# ============================================================

sns.set_theme(style="whitegrid")


# ============================================================
# 6. ÉVOLUTION MENSUELLE
# ============================================================

monthly = monthly.sort_values("month")

fig, ax = plt.subplots(figsize=(12, 6))

sns.lineplot(
    data=monthly,
    x="month",
    y="total_consumption",
    color="#0078D4",
    linewidth=2,
    ax=ax
)

ax.set_title(
    "Évolution mensuelle de la consommation électrique"
)

ax.set_xlabel("Mois")
ax.set_ylabel("Consommation totale")
ax.tick_params(axis="x", rotation=45)

fig.tight_layout()

fig.savefig(
    REPORTS_DIR / "monthly_consumption_trend.png",
    dpi=300
)

plt.close(fig)


# ============================================================
# 7. RÉPARTITION NORMAL / ANORMAL
# ============================================================

normal_count = target_counts.get(0, 0)
anomaly_count = target_counts.get(1, 0)

fig, ax = plt.subplots(figsize=(8, 5))

ax.bar(
    ["Normal", "Anormal"],
    [normal_count, anomaly_count],
    color=["#2E86DE", "#E74C3C"]
)

ax.set_title(
    "Répartition des clients normaux et anormaux"
)

ax.set_xlabel("Catégorie")
ax.set_ylabel("Nombre de clients")

fig.tight_layout()

fig.savefig(
    REPORTS_DIR / "target_distribution.png",
    dpi=300
)

plt.close(fig)


# ============================================================
# 8. TOP 10 DES RÉGIONS
# ============================================================

region_counts = (
    clients["region"]
    .value_counts()
    .head(10)
    .sort_values()
)

fig, ax = plt.subplots(figsize=(10, 6))

ax.barh(
    region_counts.index.astype(str),
    region_counts.values,
    color="#16A085"
)

ax.set_title(
    "Les 10 régions contenant le plus de clients"
)

ax.set_xlabel("Nombre de clients")
ax.set_ylabel("Code de la région")

fig.tight_layout()

fig.savefig(
    REPORTS_DIR / "top_regions.png",
    dpi=300
)

plt.close(fig)


# ============================================================
# 9. RÉSUMÉ
# ============================================================

summary = f"""
RAPPORT D'ANALYSE EXPLORATOIRE

Nombre de clients : {len(clients):,}
Nombre de mois analysés : {len(monthly)}
Premier mois : {monthly["month"].min()}
Dernier mois : {monthly["month"].max()}
Clients normaux : {normal_count:,}
Clients anormaux : {anomaly_count:,}
Pourcentage de clients anormaux : {fraud_rate:.2f} %
"""

report_file = REPORTS_DIR / "exploratory_summary.txt"

report_file.write_text(
    summary.strip(),
    encoding="utf-8"
)

print(summary)

print("=== FICHIERS CRÉÉS ===")
print(REPORTS_DIR / "monthly_consumption_trend.png")
print(REPORTS_DIR / "target_distribution.png")
print(REPORTS_DIR / "top_regions.png")
print(report_file)

print("\nAnalyse exploratoire terminée avec succès.")
