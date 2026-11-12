import os
import urllib.request

# Met à jour les prix spot EIA (Brent et WTI) depuis le package datahub.io "oil-prices"
# Utilisation : python scripts/update_data.py

SOURCE = "https://raw.githubusercontent.com/datasets/oil-prices/main/data/{}-daily.csv"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

for nom in ["brent", "wti"]:
    with urllib.request.urlopen(SOURCE.format(nom), timeout=60) as reponse:
        texte = reponse.read().decode("utf-8").replace("\r\n", "\n")
    with open(os.path.join(DATA_DIR, f"{nom}_spot_daily.csv"), "w", encoding="utf-8") as fichier:
        fichier.write(texte)
    lignes = texte.strip().splitlines()
    print(f"{nom}: {len(lignes) - 1} lignes, dernière : {lignes[-1]}")
