import os
import json
import argparse
import numpy as np


# ============================================================================
# PARAMÈTRES
# ============================================================================
# Un trader détient une cargaison de diesel, couverte par une vente du premier
# contrat ICE Gasoil (M1). La courbe est en contango : vendre tout de suite,
# ou stocker 1 ou 2 mois et vendre contre un contrat plus lointain ?

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CAS_PAR_DEFAUT = os.path.join(DOSSIER, "example_case.json")
JOURS_PAR_MOIS = 30

# ============================================================================
# CALCULS
# ============================================================================

def charger_cas(chemin):
    """Charge le cas (cargaison, cuve, marché) depuis un fichier JSON"""
    with open(chemin, encoding="utf-8") as fichier:
        cas = json.load(fichier)
    return cas["cargo"], cas["tank"], cas["market"]


def volume_m3(cargaison):
    """Volume à 15°C : tonnes / densité (kg/l) = m3"""
    return cargaison["mass_mt"] / cargaison["density_kg_per_l"]


def evaluer(cargaison, cuve, marche, mois):
    """P&L (USD) si on stocke `mois` mois puis on vend contre le contrat M(1 + mois)"""
    masse = cargaison["mass_mt"]
    volume = volume_m3(cargaison)
    if mois > 0 and volume > cuve["capacity_m3"]:
        raise ValueError(f"La cargaison ({volume:,.0f} m3) ne rentre pas dans la cuve")
    valeur = masse * cargaison["purchase_price"]

    # La vente physique est fixée sur le contrat qui correspond à la livraison
    prix_vente = marche["curve"][mois] + marche["sale_differential"]
    pnl_physique = (prix_vente - cargaison["purchase_price"]) * masse
    # On rachète la vente M1 initiale au prix M1 du jour
    pnl_couverture = (cargaison["hedge_entry_price"] - marche["curve"][0]) * masse

    volume_facture = cuve["capacity_m3"] if cuve.get("charge_full_capacity") else volume
    stockage = volume_facture * cuve["rate_per_m3_month"] * mois
    financement = valeur * marche["financing_rate"] * mois * JOURS_PAR_MOIS / 360   # ACT/360
    assurance = valeur * marche["insurance_rate_month"] * mois
    roll = marche["hedge_cost_per_mt"] * masse if mois > 0 else 0.0

    net = pnl_physique + pnl_couverture - stockage - financement - assurance - roll
    return {
        "sale_price": prix_vente, "physical_pnl": pnl_physique, "hedge_pnl": pnl_couverture,
        "storage_cost": stockage, "financing_cost": financement, "insurance_cost": assurance,
        "roll_cost": roll, "net_pnl": net, "net_pnl_per_mt": net / masse,
    }


def cout_portage(cargaison, cuve, marche, mois):
    """Coût total pour porter la cargaison `mois` mois, en USD/t
    = contango minimum pour que stocker rapporte autant que vendre tout de suite"""
    r = evaluer(cargaison, cuve, marche, mois)
    return (r["storage_cost"] + r["financing_cost"] + r["insurance_cost"] + r["roll_cost"]) \
        / cargaison["mass_mt"]


def taux_financement_neutre(cargaison, cuve, marche, mois):
    """Taux de financement annuel pour lequel stocker = vendre tout de suite"""
    sans_financement = dict(marche, financing_rate=0.0)
    gain = evaluer(cargaison, cuve, sans_financement, mois)["net_pnl"] \
        - evaluer(cargaison, cuve, sans_financement, 0)["net_pnl"]
    base = cargaison["mass_mt"] * cargaison["purchase_price"] * mois * JOURS_PAR_MOIS / 360
    return gain / base


def spread_option_extension(cargaison, cuve, marche):
    """Spread M2-M3 (USD/t) qu'il faut pour payer un mois de plus + l'option d'extension"""
    valeur = cargaison["mass_mt"] * cargaison["purchase_price"]
    volume = volume_m3(cargaison)
    volume_facture = cuve["capacity_m3"] if cuve.get("charge_full_capacity") else volume
    un_mois = volume_facture * cuve["rate_per_m3_month"] \
        + valeur * marche["financing_rate"] * JOURS_PAR_MOIS / 360 \
        + valeur * marche["insurance_rate_month"]
    prime = volume * cuve["extension_premium_per_m3"]
    return (un_mois + prime) / cargaison["mass_mt"]


# ============================================================================
# EXPORT
# ============================================================================

def tableau(entetes, lignes):
    """Tableau markdown"""
    texte = "| " + " | ".join(entetes) + " |\n|" + "---|" * len(entetes) + "\n"
    for ligne in lignes:
        texte += "| " + " | ".join(str(c) for c in ligne) + " |\n"
    return texte


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Sell now or store a hedged cargo?")
    parser.add_argument("--config", default=CAS_PAR_DEFAUT, help="fichier JSON du cas")
    args = parser.parse_args()
    cargaison, cuve, marche = charger_cas(args.config)

    horizons = range(len(marche["curve"]))
    resultats = [evaluer(cargaison, cuve, marche, n) for n in horizons]
    noms = ["Sell now"] + [f"Store {n} month{'s' if n > 1 else ''}" for n in horizons if n > 0]

    courbe = ", ".join(f"M{i + 1} {p:,.2f}" for i, p in enumerate(marche["curve"]))
    res = "# Storage arbitrage: results\n\n"
    res += f"Cargo {cargaison['mass_mt']:,.0f} t at {cargaison['density_kg_per_l']} kg/l = " \
           f"{volume_m3(cargaison):,.0f} m3 (tank {cuve['capacity_m3']:,.0f} m3). Curve {courbe} USD/t. " \
           f"Financing {marche['financing_rate']:.1%} a year, storage " \
           f"{cuve['rate_per_m3_month']:.2f} USD/m3/month.\n\n"

    # P&L de chaque option
    lignes = []
    for cle, nom in [("sale_price", "Sale price (USD/t)"), ("physical_pnl", "Physical P&L"),
                     ("hedge_pnl", "Hedge P&L (buy back M1)"), ("storage_cost", "Storage"),
                     ("financing_cost", "Financing"), ("insurance_cost", "Insurance"),
                     ("roll_cost", "Futures roll"), ("net_pnl", "**Net P&L (USD)**"),
                     ("net_pnl_per_mt", "Net P&L per tonne")]:
        nd = 2 if cle in ("sale_price", "net_pnl_per_mt") else 0
        lignes.append([nom] + [f"{r[cle]:,.{nd}f}" for r in resultats])
    res += tableau([""] + noms, lignes)
    meilleur = int(np.argmax([r["net_pnl"] for r in resultats]))
    res += f"\nBest option: **{noms[meilleur]}** ({resultats[meilleur]['net_pnl']:,.0f} USD).\n\n"
    print(f"Meilleure option : {noms[meilleur]} ({resultats[meilleur]['net_pnl']:,.0f} USD)")

    # Points morts
    res += "## Break-evens\n\n"
    lignes = []
    for n in horizons:
        if n == 0:
            continue
        lignes.append([noms[n], f"{marche['curve'][n] - marche['curve'][0]:.2f}",
                       f"{cout_portage(cargaison, cuve, marche, n):.2f}",
                       f"{taux_financement_neutre(cargaison, cuve, marche, n):.2%}"])
    res += tableau(["Option", "Contango available (USD/t)", "Contango needed (USD/t)",
                    "Financing rate at break-even"], lignes)
    if len(marche["curve"]) > 2 and cuve.get("extension_premium_per_m3", 0) > 0:
        res += f"\nOption to extend storage by one month ({cuve['extension_premium_per_m3']:.2f} " \
               f"USD/m3): needs an M2-M3 spread of {spread_option_extension(cargaison, cuve, marche):.2f} " \
               f"USD/t; the curve offers {marche['curve'][2] - marche['curve'][1]:.2f}.\n\n"

    # Scénarios
    res += "## Sensitivity of the storage decision\n\n"
    scenarios = {
        "Base case": (cuve, marche),
        "No financing cost": (cuve, dict(marche, financing_rate=0.0)),
        "Whole tank charged": (dict(cuve, charge_full_capacity=True), marche),
    }
    lignes = []
    for nom, (c, m) in scenarios.items():
        nets = [evaluer(cargaison, c, m, n)["net_pnl"] for n in horizons]
        lignes.append([nom] + [f"{v:,.0f}" for v in nets] + [noms[int(np.argmax(nets))]])
    res += tableau(["Scenario"] + noms + ["Best"], lignes)

    with open(os.path.join(DOSSIER, "results.md"), "w", encoding="utf-8") as fichier:
        fichier.write(res)
    print("Résultats écrits dans results.md")


if __name__ == "__main__":
    main()
