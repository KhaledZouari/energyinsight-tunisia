import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from project_config import OUTPUT_ROOT, REPORTS_DIR

# Matrice de confusion
predictions = pd.read_csv(REPORTS_DIR / "test_predictions.csv")
if not predictions["jeu"].eq("test").all():
    raise ValueError("La matrice doit utiliser uniquement le test.")
cm = confusion_matrix(predictions["actual_target"], predictions["predicted_target"], labels=[0, 1])

fig, ax = plt.subplots(figsize=(7, 6))

# Affichage de la matrice
im = ax.imshow(cm, cmap="Blues")

# Barre de couleur
cbar = plt.colorbar(im)

# Titres et axes en français
ax.set_title("Matrice de confusion", fontsize=14)
ax.set_xlabel("Classe prédite", fontsize=12)
ax.set_ylabel("Classe réelle", fontsize=12)

# Libellés des classes
classes = ["Normal", "Anomalie"]
ax.set_xticks([0, 1])
ax.set_yticks([0, 1])
ax.set_xticklabels(classes)
ax.set_yticklabels(classes)

# Affichage des valeurs dans les cases
for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        ax.text(
            j, i, f"{cm[i, j]}",
            ha="center", va="center",
            color="white" if cm[i, j] > cm.max() / 2 else "#1f4e79",
            fontsize=11
        )

plt.tight_layout()

# Enregistrer l'image
for destination in [REPORTS_DIR / "confusion_matrix.png", OUTPUT_ROOT / "matrice_confusion_fr.png"]:
    plt.savefig(destination, dpi=300, bbox_inches="tight")
plt.close(fig)
