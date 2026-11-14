import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
from statsmodels.tsa.stattools import adfuller


# ============================================================================
# PARAMÈTRES
# ============================================================================

DOSSIER = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DOSSIER, "..", "..", "data")
FIG_DIR = os.path.join(DOSSIER, "figures")

DEBUT = "2021-01-04"
FIN = "2025-12-31"

# Couleurs des graphiques
FOND = "#fcfcfb"
ENCRE = "#0b0b0b"
ENCRE_2 = "#52514e"
GRIS = "#898781"
GRILLE = "#e1e0d9"
AXE = "#c3c2b7"
BLEU = "#2a78d6"

plt.rcParams.update({
    "figure.facecolor": FOND, "axes.facecolor": FOND, "savefig.facecolor": FOND,
    "font.size": 10, "text.color": ENCRE,
    "axes.edgecolor": AXE, "axes.linewidth": 0.8, "axes.labelcolor": ENCRE_2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlepad": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRILLE, "grid.linewidth": 0.6,
    "xtick.color": AXE, "ytick.color": AXE, "xtick.labelcolor": ENCRE_2,
    "ytick.labelcolor": ENCRE_2, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "legend.frameon": False, "legend.fontsize": 9, "legend.labelcolor": ENCRE_2,
    "savefig.dpi": 160,
})


# ============================================================================
# DONNÉES ET STATISTIQUES
# ============================================================================

def charger_brent():
    """Prix spot Brent EIA (USD/bbl)"""
    df = pd.read_csv(os.path.join(DATA_DIR, "brent_spot_daily.csv"), parse_dates=["Date"])
    return df.set_index("Date")["Price"].sort_index().loc[DEBUT:FIN]


def stats_descriptives(x):
    """Moments + Jarque-Bera (skew et kurtosis corrigés comme dans Excel)"""
    x = pd.Series(x).dropna()
    return {
        "obs": len(x), "mean": x.mean(), "std": x.std(),
        "skew": stats.skew(x, bias=False), "excess_kurtosis": stats.kurtosis(x, bias=False),
        "jarque_bera": stats.jarque_bera(x).statistic,
    }


def test_adf(x):
    """Test ADF (retards choisis par AIC) : statistique et p-value"""
    x = pd.Series(x).dropna()
    try:
        res = adfuller(x, regression="c", autolag="AIC", result_object=False)
    except TypeError:  # anciennes versions de statsmodels
        res = adfuller(x, regression="c", autolag="AIC")
    return res[0], res[1]


# ============================================================================
# GRAPHIQUES
# ============================================================================

def source(ax, texte):
    ax.annotate(texte, (0, 0), xycoords="axes fraction", xytext=(0, -30),
                textcoords="offset points", fontsize=8, color=GRIS, va="top")


def graphique_prix(brent, rendements):
    fig, (haut, bas) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={"hspace": 0.3})
    haut.plot(brent.index, brent, color=BLEU, lw=1.3)
    haut.set_title("Brent spot price, USD/bbl")
    bas.plot(rendements.index, rendements * 100, color=BLEU, lw=0.7)
    bas.axhline(0, color=AXE, lw=0.8)
    bas.set_title("Daily log return, %")
    bas.xaxis.set_major_locator(mdates.YearLocator(1))
    bas.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    bas.margins(x=0.01)
    source(bas, "Source: U.S. EIA, Europe Brent spot price FOB (public domain).")
    fig.savefig(os.path.join(FIG_DIR, "prices_and_returns.png"), bbox_inches="tight", pad_inches=0.2)
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


def f(x, nd=2):
    return f"{x:,.{nd}f}"


# ============================================================================
# MAIN
# ============================================================================

def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    brent = charger_brent()
    rendements = np.log(brent).diff().dropna()
    print(f"{len(brent)} prix Brent entre {DEBUT} et {FIN}")

    res = f"# Brent crude risk models: results\n\nEIA Brent spot (Europe, FOB), {DEBUT} to {FIN}, " \
          f"{len(brent):,} daily prices.\n\n"

    # 1. Statistiques descriptives
    sp, sr = stats_descriptives(brent), stats_descriptives(rendements)
    adf_prix, p_prix = test_adf(np.log(brent))
    adf_rend, p_rend = test_adf(rendements)
    res += "## Descriptive statistics\n\n"
    res += tableau(["", "Price (USD/bbl)", "Log return"], [
        ["Observations", sp["obs"], sr["obs"]],
        ["Mean", f(sp["mean"]), f"{sr['mean'] * 252:.2%} annualised"],
        ["Std deviation", f(sp["std"]), f"{sr['std'] * np.sqrt(252):.2%} annualised"],
        ["Skewness", f(sp["skew"]), f(sr["skew"])],
        ["Excess kurtosis", f(sp["excess_kurtosis"]), f(sr["excess_kurtosis"])],
        ["Jarque-Bera", f(sp["jarque_bera"], 1), f(sr["jarque_bera"], 1)],
        ["ADF statistic (p-value)", f"{adf_prix:.2f} ({p_prix:.3f}), log price",
         f"{adf_rend:.2f} ({p_rend:.3f})"],
    ])

    # 2. Graphiques
    graphique_prix(brent, rendements)

    with open(os.path.join(DOSSIER, "results.md"), "w", encoding="utf-8") as fichier:
        fichier.write(res)
    print("Résultats écrits dans results.md, graphiques dans figures/")


if __name__ == "__main__":
    main()
