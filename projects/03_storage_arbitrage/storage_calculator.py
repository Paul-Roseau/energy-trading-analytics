import os
import json
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


# ============================================================================
# PARAMÈTRES
# ============================================================================
# Un trader détient une cargaison de diesel, couverte par une vente du premier
# contrat ICE Gasoil (M1). La courbe est en contango : vendre tout de suite,
# ou stocker 1 ou 2 mois et vendre contre un contrat plus lointain ?

DOSSIER = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(DOSSIER, "figures")
CAS_PAR_DEFAUT = os.path.join(DOSSIER, "example_case.json")
JOURS_PAR_MOIS = 30

# Couleurs des graphiques
FOND = "#fcfcfb"
ENCRE = "#0b0b0b"
ENCRE_2 = "#52514e"
GRIS = "#898781"
GRIS_CLAIR = "#b9b8b2"
AXE = "#c3c2b7"
GRILLE = "#e1e0d9"
BLEU = "#2a78d6"
ROUGE = "#e34948"
DIVERGENT = LinearSegmentedColormap.from_list(
    "rouge_bleu", ["#b3302f", "#ec9190", "#f0efec", "#6da7ec", "#184f95"])

plt.rcParams.update({
    "figure.facecolor": FOND, "axes.facecolor": FOND, "savefig.facecolor": FOND,
    "font.size": 10, "text.color": ENCRE,
    "axes.edgecolor": AXE, "axes.linewidth": 0.8, "axes.labelcolor": ENCRE_2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlepad": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRILLE, "grid.linewidth": 0.6,
    "xtick.color": AXE, "ytick.color": AXE, "xtick.labelcolor": ENCRE_2,
    "ytick.labelcolor": ENCRE_2, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "savefig.dpi": 160,
})


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
# GRAPHIQUES
# ============================================================================

def graphique_cascade(cargaison, marche, vente, stock):
    """Passage du P&L 'vendre maintenant' au P&L 'stocker 1 mois'"""
    etapes = [("Sell now", vente["net_pnl"], True),
              ("Contango\ncaptured", (marche["curve"][1] - marche["curve"][0]) * cargaison["mass_mt"], False),
              ("Storage", -stock["storage_cost"], False),
              ("Financing", -stock["financing_cost"], False),
              ("Insurance", -stock["insurance_cost"], False),
              ("Futures\nroll", -stock["roll_cost"], False),
              ("Store\n1 month", stock["net_pnl"], True)]
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    niveau = 0.0
    niveaux = []
    for i, (nom, valeur, total) in enumerate(etapes):
        k = valeur / 1000
        if total:
            bas, hauteur, couleur = 0.0, k, GRIS_CLAIR
            niveau = k
        else:
            bas, hauteur = niveau, k
            couleur = BLEU if k >= 0 else ROUGE
            niveau += k
        niveaux.append(niveau)
        ax.bar(i, hauteur, bottom=bas, width=0.55, color=couleur, edgecolor=FOND, lw=2)
        if k >= 0:
            y, va, decalage = bas + hauteur, "bottom", 3
        else:
            y, va, decalage = bas + hauteur, "top", -3
        texte = f"{k:,.0f}" if total else f"{k:+,.0f}"
        ax.annotate(texte, (i, y), xytext=(0, decalage), textcoords="offset points",
                    ha="center", va=va, fontsize=9, color=ENCRE_2)
    ax.axhline(0, color=AXE, lw=0.8)
    ax.set_xticks(range(len(etapes)), [e[0] for e in etapes])
    ax.tick_params(axis="x", length=0)
    ax.set_title("Storing one month versus selling now, thousand USD")
    bas_axe = min(0.0, min(niveaux))
    haut_axe = max(0.0, max(niveaux))
    marge = 0.15 * (haut_axe - bas_axe)
    ax.set_ylim(bas_axe - marge, haut_axe + marge)
    ax.annotate("Example case: blue adds to P&L, red subtracts; grey bars are totals.",
                (0, 0), xycoords="axes fraction", xytext=(0, -30), textcoords="offset points",
                fontsize=8, color=GRIS, va="top")
    fig.savefig(os.path.join(FIG_DIR, "waterfall.png"), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def graphique_decision(cargaison, cuve, marche):
    """Gain à stocker 1 mois plutôt que vendre, selon le contango et le taux de financement"""
    contangos = np.linspace(0, 16, 161)
    taux = np.linspace(0, 0.08, 81)
    gains = np.empty((len(taux), len(contangos)))
    for i, t in enumerate(taux):
        for j, c in enumerate(contangos):
            courbe = [marche["curve"][0], marche["curve"][0] + c] + list(marche["curve"][2:])
            m = dict(marche, financing_rate=t, curve=courbe)
            gains[i, j] = (evaluer(cargaison, cuve, m, 1)["net_pnl"]
                           - evaluer(cargaison, cuve, m, 0)["net_pnl"]) / 1000
    limite = np.abs(gains).max()
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    carte = ax.pcolormesh(contangos, taux * 100, gains, cmap=DIVERGENT, vmin=-limite, vmax=limite,
                          shading="auto")
    ax.contour(contangos, taux * 100, gains, levels=[0], colors=[ENCRE], linewidths=1.2)
    ax.grid(False)
    contango_exemple = marche["curve"][1] - marche["curve"][0]
    ax.scatter([contango_exemple], [marche["financing_rate"] * 100], s=60, color=ENCRE,
               edgecolor=FOND, linewidth=2, zorder=3)
    ax.annotate("example case", (contango_exemple, marche["financing_rate"] * 100), xytext=(8, 6),
                textcoords="offset points", fontsize=9, color=ENCRE)
    ax.text(0.97, 0.08, "store", transform=ax.transAxes, ha="right", fontsize=11, color=ENCRE)
    ax.text(0.03, 0.90, "sell now", transform=ax.transAxes, ha="left", fontsize=11, color=ENCRE)
    ax.set_xlabel("M2 - M1 contango, USD/t")
    ax.set_ylabel("Financing rate, % a year")
    ax.set_title("Gain from storing one month instead of selling now, thousand USD "
                 "(black line: break-even)")
    barre = fig.colorbar(carte, ax=ax, pad=0.02)
    barre.outline.set_visible(False)
    barre.ax.tick_params(color=AXE, labelcolor=ENCRE_2, labelsize=9)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    fig.savefig(os.path.join(FIG_DIR, "decision_map.png"), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


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
    os.makedirs(FIG_DIR, exist_ok=True)
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

    graphique_cascade(cargaison, marche, resultats[0], resultats[1])
    graphique_decision(cargaison, cuve, marche)

    with open(os.path.join(DOSSIER, "results.md"), "w", encoding="utf-8") as fichier:
        fichier.write(res)
    print("Résultats écrits dans results.md, graphiques dans figures/")


if __name__ == "__main__":
    main()
