import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats
from scipy.stats import norm
from statsmodels.tsa.stattools import adfuller, coint


# ============================================================================
# PARAMÈTRES
# ============================================================================

DOSSIER = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DOSSIER, "..", "..", "data")
FIG_DIR = os.path.join(DOSSIER, "figures")

DEBUT = "2016-01-07"
FIN = "2026-02-11"
JOUR_EXCLU = "2020-04-20"      # WTI spot à -36.98 la veille de l'expiration du contrat de mai 2020
DATE_MIDLAND = "2023-06-01"    # le WTI Midland entre dans le panier Dated Brent

REGIMES = {
    "2016 - 2019": ("2016-01-07", "2019-12-31"),
    "2020 - May 2023": ("2020-01-01", "2023-05-31"),
    "Jun 2023 - Feb 2026": (DATE_MIDLAND, FIN),
}

# Stratégie z-score
FENETRE = 252          # fenêtre glissante du z-score (jours)
SEUIL_ENTREE = 2.0     # on entre quand |z| >= 2
SEUIL_SORTIE = 0.0     # on sort quand z repasse par 0
DECALAGE = 1           # 1 = exécution à la clôture suivante (pas de look-ahead)
COUT = 0.02            # coût en USD/bbl à chaque changement de position
TAILLE = 1000          # barils de spread (1 lot par jambe)
GRILLE_FENETRES = [20, 60, 126, 252]
GRILLE_SEUILS = [1.5, 2.0, 2.5]

# Options sur le spread
JOURS_OPTION = 21      # un mois de bourse
TAUX = 0.04            # taux d'actualisation (hypothèse)
FENETRE_VOL = 60       # jours pour les volatilités réalisées
BEAR_PUT = (6.50, 5.00)   # put long K haut, put court K bas
STRANGLE = (5.00, 8.50)   # put long, call long

# Couleurs des graphiques
FOND = "#fcfcfb"
ENCRE = "#0b0b0b"
ENCRE_2 = "#52514e"
GRIS = "#898781"
GRILLE = "#e1e0d9"
AXE = "#c3c2b7"
BLEU = "#2a78d6"
ORANGE = "#eb6834"
BLEUS = LinearSegmentedColormap.from_list(
    "bleus", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281"])

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
# DONNÉES
# ============================================================================

def charger_prix(nom):
    """Charge un fichier de prix EIA (brent ou wti)"""
    df = pd.read_csv(os.path.join(DATA_DIR, f"{nom}_spot_daily.csv"), parse_dates=["Date"])
    return df.set_index("Date")["Price"].rename(nom).sort_index()


def charger_brent_wti():
    """Brent et WTI alignés sur les DATES (et pas ligne à ligne)"""
    # Les deux séries n'ont pas le même calendrier de jours fériés :
    # coller deux téléchargements côte à côte décale une série par rapport à l'autre
    prix = pd.concat([charger_prix("brent"), charger_prix("wti")], axis=1, join="inner").dropna()
    prix = prix.drop(index=pd.to_datetime([JOUR_EXCLU]), errors="ignore")
    return prix.loc[DEBUT:FIN]


# ============================================================================
# STATISTIQUES
# ============================================================================

def stats_descriptives(x):
    """Moments + test de Jarque-Bera (skew et kurtosis corrigés comme SKEW et KURT d'Excel)"""
    x = pd.Series(x).dropna()
    jb = stats.jarque_bera(x)
    return {
        "obs": len(x), "mean": x.mean(), "std": x.std(), "min": x.min(), "max": x.max(),
        "skew": stats.skew(x, bias=False), "excess_kurtosis": stats.kurtosis(x, bias=False),
        "jarque_bera": jb.statistic,
    }


def test_adf(x):
    """Test ADF avec choix des retards par AIC"""
    x = pd.Series(x).dropna()
    try:
        res = adfuller(x, regression="c", autolag="AIC", result_object=False)
    except TypeError:  # anciennes versions de statsmodels
        res = adfuller(x, regression="c", autolag="AIC")
    return {"stat": res[0], "pvalue": res[1], "lags": res[2], "crit_1pct": res[4]["1%"]}


# ============================================================================
# ORNSTEIN-UHLENBECK
# ============================================================================

def calibrer_ou(x, dt=1.0):
    """Calibration OU par la discrétisation exacte AR(1) : x[t+1] = a + b x[t] + e"""
    x = np.asarray(x, dtype=float)
    b, a = np.polyfit(x[:-1], x[1:], 1)
    if not 0 < b < 1:                       # sinon kappa négatif ou indéfini
        raise ValueError(f"pente AR(1) de {b:.4f} hors de ]0, 1[ : pas de retour à la moyenne")
    residus = x[1:] - (a + b * x[:-1])
    kappa = -np.log(b) / dt                 # et pas 1 - b (approximation)
    theta = a / (1 - b)
    sigma = residus.std(ddof=2) * np.sqrt(2 * kappa / (1 - b ** 2))
    return {"kappa": kappa, "theta": theta, "sigma": sigma, "half_life": np.log(2) / kappa}


def moments_ou(ou, x0, horizon):
    """Espérance et écart-type de X(horizon) sachant X(0) = x0"""
    decroissance = np.exp(-ou["kappa"] * horizon)
    moyenne = ou["theta"] + (x0 - ou["theta"]) * decroissance
    variance = ou["sigma"] ** 2 * (1 - decroissance ** 2) / (2 * ou["kappa"])
    return moyenne, np.sqrt(variance)


# ============================================================================
# BACKTEST Z-SCORE
# ============================================================================

def positions_cibles(z, seuil_entree, seuil_sortie):
    """Short le spread si z >= seuil, long si z <= -seuil, sortie quand z repasse par 0"""
    positions = []
    pos = 0.0
    for valeur in z:
        if np.isnan(valeur):
            pos = 0.0
        else:
            # sortie
            if pos < 0 and valeur <= seuil_sortie:
                pos = 0.0
            elif pos > 0 and valeur >= -seuil_sortie:
                pos = 0.0
            # entrée (on peut se retourner le même jour)
            if pos == 0.0:
                if valeur >= seuil_entree:
                    pos = -1.0
                elif valeur <= -seuil_entree:
                    pos = 1.0
        positions.append(pos)
    return pd.Series(positions, index=z.index)


def backtest(spread, fenetre=FENETRE, seuil_entree=SEUIL_ENTREE, seuil_sortie=SEUIL_SORTIE,
             decalage=DECALAGE, cout=COUT, taille=TAILLE):
    """Backtest de la stratégie z-score. P&L en USD pour `taille` barils de spread."""
    moyenne = spread.rolling(fenetre).mean()
    ecart_type = spread.rolling(fenetre).std()
    z = (spread - moyenne) / ecart_type

    cible = positions_cibles(z, seuil_entree, seuil_sortie)
    # position[t] = position tenue de la clôture t à la clôture t+1
    position = cible.shift(decalage).fillna(0.0) if decalage > 0 else cible.copy()
    position_veille = position.shift(1).fillna(0.0)

    pnl_brut = position_veille * spread.diff().fillna(0.0)          # en USD/bbl
    couts = (position - position_veille).abs() * cout
    pnl = (pnl_brut - couts) * taille

    debut = z.first_valid_index()
    cumul = pnl.loc[debut:].cumsum()
    drawdown = cumul - cumul.cummax().clip(lower=0.0)

    trades = liste_trades(spread, position, pnl_brut, cout, taille)
    fermes = [t for t in trades if t["sortie"] is not None]
    pnl_periode = pnl.loc[debut:]
    annees = len(pnl_periode) / 252

    vol_pnl = pnl_periode.std()             # nulle sans aucun trade
    resume = {
        "sharpe": pnl_periode.mean() / vol_pnl * np.sqrt(252) if vol_pnl > 0 else np.nan,
        "annual_pnl_usd": pnl_periode.sum() / annees,
        "max_drawdown_usd": drawdown.min(),
        "n_trades": len(trades),
        "hit_rate": np.mean([t["pnl"] > 0 for t in fermes]) if fermes else np.nan,
        "avg_holding_days": np.mean([t["jours"] for t in trades]) if trades else np.nan,
        "time_in_market": (position.loc[debut:] != 0).mean(),
    }
    jours = pd.DataFrame({"z": z, "position": position, "pnl": pnl, "cumul": cumul})
    return jours, trades, resume


def liste_trades(spread, position, pnl_brut, cout, taille):
    """Liste des trades : date d'entrée, de sortie, sens, durée et P&L (coûts inclus)"""
    trades = []
    trade = None
    pos_veille = 0.0
    for i, date in enumerate(spread.index):
        pos = position.iloc[i]
        # le P&L du jour appartient à la position tenue la veille
        if trade is not None:
            trade["pnl"] += pnl_brut.iloc[i] * taille
        if pos != pos_veille:
            if trade is not None:                      # sortie
                trade["pnl"] -= abs(pos_veille) * cout * taille
                trade["sortie"] = date
                trades.append(trade)
                trade = None
            if pos != 0:                               # entrée
                trade = {"entree": date, "sens": "long" if pos > 0 else "short",
                         "jours": 0, "pnl": -abs(pos) * cout * taille, "sortie": None}
        if trade is not None:
            trade["jours"] += 1
        pos_veille = pos
    if trade is not None:                              # trade encore ouvert à la fin
        trades.append(trade)
    return trades


# ============================================================================
# OPTIONS SUR LE SPREAD
# ============================================================================

def verifier_type_option(type_option):
    if type_option not in ("call", "put"):
        raise ValueError(f"type_option doit valoir 'call' ou 'put', pas {type_option!r}")


def valeur_intrinseque(ecart, type_option, actu):
    """Valeur actualisée à l'échéance, ecart = sous-jacent - strike"""
    return actu * np.maximum(ecart if type_option == "call" else -ecart, 0.0)


def prix_bachelier(F, K, T, vol, r, type_option):
    """Modèle normal (Bachelier) : le spread peut être négatif, vol en USD/bbl"""
    verifier_type_option(type_option)
    s = vol * np.sqrt(T)
    actu = np.exp(-r * T)
    if s == 0:                              # échéance atteinte ou vol nulle
        return valeur_intrinseque(F - K, type_option, actu)
    d = (F - K) / s
    if type_option == "call":
        return actu * ((F - K) * norm.cdf(d) + s * norm.pdf(d))
    return actu * ((K - F) * norm.cdf(-d) + s * norm.pdf(d))


def prix_kirk(F1, F2, K, T, vol1, vol2, rho, r, type_option):
    """Approximation de Kirk (1995) pour une option sur F1 - F2"""
    verifier_type_option(type_option)
    if F2 + K <= 0:
        raise ValueError("l'approximation de Kirk suppose F2 + K > 0")
    w = F2 / (F2 + K)
    vol = np.sqrt(vol1 ** 2 - 2 * rho * vol1 * vol2 * w + (vol2 * w) ** 2)
    actu = np.exp(-r * T)
    if vol * np.sqrt(T) == 0:               # échéance atteinte ou vol nulle
        return valeur_intrinseque(F1 - F2 - K, type_option, actu)
    d1 = (np.log(F1 / (F2 + K)) + 0.5 * vol ** 2 * T) / (vol * np.sqrt(T))
    d2 = d1 - vol * np.sqrt(T)
    call = actu * (F1 * norm.cdf(d1) - (F2 + K) * norm.cdf(d2))
    if type_option == "call":
        return call
    return call - actu * (F1 - F2 - K)    # parité call-put


def pnl_expiration(jambes, x):
    """P&L à l'échéance d'une stratégie. jambes = [(quantité, type, strike, prime), ...]"""
    total = np.zeros_like(x)
    for quantite, type_option, strike, prime in jambes:
        if type_option == "call":
            valeur = np.maximum(x - strike, 0.0)
        else:
            valeur = np.maximum(strike - x, 0.0)
        total += quantite * (valeur - prime)
    return total


def points_morts(jambes, x):
    """Niveaux du spread où le P&L à l'échéance passe par zéro"""
    y = pnl_expiration(jambes, x)
    points = []
    for i in range(len(x) - 1):
        if y[i] == 0:
            points.append(x[i])
        elif y[i] * y[i + 1] < 0:
            points.append(x[i] - y[i] * (x[i + 1] - x[i]) / (y[i + 1] - y[i]))
    return points


# ============================================================================
# GRAPHIQUES
# ============================================================================

def etiquette(ax, x, y, texte, dy=0):
    ax.annotate(texte, (x, y), xytext=(6, dy), textcoords="offset points",
                va="center", fontsize=9, color=ENCRE_2)


def source(ax, texte):
    ax.annotate(texte, (0, 0), xycoords="axes fraction", xytext=(0, -30),
                textcoords="offset points", fontsize=8, color=GRIS, va="top")


def axe_dates(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.margins(x=0.01)


def graphique_prix(prix, spread):
    fig, (haut, bas) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True,
                                    gridspec_kw={"height_ratios": [1.1, 1], "hspace": 0.3})
    haut.plot(prix.index, prix["brent"], color=BLEU, lw=1.3, label="Brent (Europe, FOB)")
    haut.plot(prix.index, prix["wti"], color=ORANGE, lw=1.3, label="WTI (Cushing)")
    haut.set_title("Brent and WTI spot prices, USD/bbl")
    haut.legend(loc="upper left", ncols=2)
    etiquette(haut, prix.index[-1], prix["brent"].iloc[-1], "Brent", dy=6)
    etiquette(haut, prix.index[-1], prix["wti"].iloc[-1], "WTI", dy=-6)

    moyenne_252 = spread.rolling(252).mean()
    bas.plot(spread.index, spread, color=BLEU, lw=1.0)
    bas.plot(moyenne_252.index, moyenne_252, color=ENCRE_2, lw=1.2)
    bas.axhline(0, color=AXE, lw=0.8)
    bas.axvline(pd.Timestamp(DATE_MIDLAND), color=GRIS, lw=0.8)
    bas.annotate("June 2023: WTI Midland joins\nthe Dated Brent basket",
                 (pd.Timestamp(DATE_MIDLAND), 14.0), xytext=(6, 0), textcoords="offset points",
                 ha="left", va="top", fontsize=8, color=ENCRE_2)
    bas.set_title("Brent minus WTI spread, USD/bbl (thin) and its 252-day mean")
    etiquette(bas, spread.index[-1], moyenne_252.iloc[-1], "252-day mean", dy=-8)
    axe_dates(bas)
    source(bas, "Source: U.S. EIA daily spot prices (public domain). 20 Apr 2020 excluded.")
    fig.savefig(os.path.join(FIG_DIR, "prices_and_spread.png"), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def graphique_backtest(jours, jours_meme_cloture, sharpe, sharpe_meme_cloture):
    d = jours.dropna(subset=["z"])
    fig, (haut, bas) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True,
                                    gridspec_kw={"height_ratios": [1, 1.1], "hspace": 0.3})
    haut.plot(d.index, d["z"], color=BLEU, lw=0.9)
    haut.axhline(2, color=ENCRE_2, lw=0.8)
    haut.axhline(-2, color=ENCRE_2, lw=0.8)
    haut.axhline(0, color=AXE, lw=0.8)
    haut.fill_between(d.index, -4.5, 4.5, where=d["position"] > 0, color=BLEU, alpha=0.10, lw=0)
    haut.fill_between(d.index, -4.5, 4.5, where=d["position"] < 0, color=ORANGE, alpha=0.12, lw=0)
    haut.set_ylim(-4.5, 4.5)
    haut.set_title("252-day z-score of the spread, entry bands at +/-2 "
                   "(shading: long spread blue, short spread orange)")

    for j, s, couleur, label in ((jours, sharpe, BLEU, "Next-close execution"),
                                 (jours_meme_cloture, sharpe_meme_cloture, ORANGE,
                                  "Same-close execution")):
        cumul = j["cumul"].dropna() / 1000
        bas.plot(cumul.index, cumul, color=couleur, lw=1.6, label=label)
        etiquette(bas, cumul.index[-1], cumul.iloc[-1], f"Sharpe {s:.2f}")
    bas.axhline(0, color=AXE, lw=0.8)
    bas.set_title("Cumulative P&L, thousand USD per 1,000 bbl of spread (costs included)")
    bas.legend(loc="upper left")
    axe_dates(bas)
    source(bas, "Enter at |z| >= 2, exit when z crosses 0, 0.02 USD/bbl per position change.")
    fig.savefig(os.path.join(FIG_DIR, "backtest.png"), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def graphique_sensibilite(grilles):
    vmax = max(g.to_numpy().max() for g in grilles.values())
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, decalage, titre in ((axes[0], 1, "next-close execution"),
                                (axes[1], 0, "same-close execution")):
        g = grilles[decalage]
        ax.imshow(g.to_numpy(), cmap=BLEUS, vmin=0, vmax=vmax, aspect="auto")
        ax.grid(False)
        for i in range(g.shape[0]):
            for j in range(g.shape[1]):
                v = g.iloc[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=10,
                        color="#ffffff" if v > 0.55 * vmax else ENCRE)
        ax.set_xticks(range(len(g.columns)), [f"|z| {c}" for c in g.columns])
        ax.set_yticks(range(len(g.index)), [f"{w} d" for w in g.index])
        ax.set_title(f"Sharpe ratio, {titre}")
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(length=0)
    axes[0].set_ylabel("z-score window")
    fig.savefig(os.path.join(FIG_DIR, "sensitivity.png"), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def graphique_options(s0, ecart_rw, moyenne_ou, ecart_ou, theta, strategies, x):
    fig, (gauche, droite) = plt.subplots(1, 2, figsize=(10.5, 4.2), gridspec_kw={"wspace": 0.25})
    grille = np.linspace(-6, 16, 600)
    gauche.plot(grille, norm.pdf(grille, s0, ecart_rw), color=BLEU, lw=1.6, label="Random walk")
    gauche.plot(grille, norm.pdf(grille, moyenne_ou, ecart_ou), color=ORANGE, lw=1.6,
                label="Mean reversion (OU)")
    gauche.axvline(s0, color=ENCRE_2, lw=0.8)
    gauche.annotate(f"today {s0:.2f}", (s0, gauche.get_ylim()[1] * 0.97), xytext=(4, 0),
                    textcoords="offset points", fontsize=8, color=ENCRE_2, va="top")
    gauche.axvline(theta, color=GRIS, lw=0.8)
    gauche.annotate(f"OU mean {theta:.2f}", (theta, gauche.get_ylim()[1] * 0.97), xytext=(-4, 0),
                    textcoords="offset points", fontsize=8, color=ENCRE_2, va="top", ha="right")
    gauche.set_title("Spread distribution in one month, USD/bbl")
    gauche.set_yticks([])
    gauche.legend(loc="upper right", bbox_to_anchor=(1.0, 0.86))

    for (nom, jambes), couleur in zip(strategies.items(), (BLEU, ORANGE)):
        droite.plot(x, pnl_expiration(jambes, x), color=couleur, lw=1.6, label=nom)
    droite.axhline(0, color=AXE, lw=0.8)
    droite.axvline(s0, color=ENCRE_2, lw=0.8)
    droite.annotate(f"today {s0:.2f}", (s0, 4.4), xytext=(4, 0), textcoords="offset points",
                    fontsize=8, color=ENCRE_2, va="top")
    droite.set_xlim(0, 14)
    droite.set_title("P&L at expiry, USD/bbl (random-walk premiums)")
    droite.set_xlabel("Spread at expiry, USD/bbl")
    droite.legend(loc="upper center", bbox_to_anchor=(0.42, 1.0))
    fig.savefig(os.path.join(FIG_DIR, "options.png"), bbox_inches="tight", pad_inches=0.2)
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
    prix = charger_brent_wti()
    spread = (prix["brent"] - prix["wti"]).rename("spread")
    print(f"{len(spread)} dates communes entre {DEBUT} et {FIN}")

    res = f"# Brent-WTI spread: results\n\nEIA daily spot prices, {DEBUT} to {FIN}, " \
          f"{len(spread):,} common dates (20 Apr 2020 removed: negative WTI spot print).\n\n"

    # 1. Statistiques descriptives
    niveau = stats_descriptives(spread)
    variation = stats_descriptives(spread.diff().dropna())
    res += "## Descriptive statistics (USD/bbl)\n\n"
    res += tableau(["", "Spread level", "Daily change"],
                   [[k, f(niveau[k], 3), f(variation[k], 3)] for k in
                    ["obs", "mean", "std", "min", "max", "skew", "excess_kurtosis", "jarque_bera"]])

    # 2. Stationnarité et cointégration
    tests = {"log Brent": test_adf(np.log(prix["brent"])), "log WTI": test_adf(np.log(prix["wti"])),
             "Spread": test_adf(spread)}
    eg_stat, eg_pvalue, _ = coint(np.log(prix["brent"]), np.log(prix["wti"]))
    res += "\n## Unit-root and cointegration tests\n\n"
    res += tableau(["Series", "ADF stat", "p-value", "lags (AIC)", "1% critical"],
                   [[k, f(v["stat"]), f(v["pvalue"], 4), v["lags"], f(v["crit_1pct"])]
                    for k, v in tests.items()])
    res += f"\nEngle-Granger (log Brent on log WTI): stat {f(eg_stat)}, p-value {f(eg_pvalue, 4)}.\n\n"

    # 3. Ornstein-Uhlenbeck, échantillon complet et par régime
    ou = calibrer_ou(spread)
    lignes = [["Full sample", len(spread), f(spread.mean()), f(spread.std()), f(ou["kappa"], 4),
               f(ou["half_life"], 1), f(ou["theta"]), f(ou["sigma"], 3)]]
    for nom, (a, b) in REGIMES.items():
        sous = spread.loc[a:b]
        ou_r = calibrer_ou(sous)
        lignes.append([nom, len(sous), f(sous.mean()), f(sous.std()), f(ou_r["kappa"], 4),
                       f(ou_r["half_life"], 1), f(ou_r["theta"]), f(ou_r["sigma"], 3)])
    res += "## Ornstein-Uhlenbeck calibration (daily steps)\n\n"
    res += tableau(["Period", "Obs", "Mean", "Std", "kappa /day", "Half-life (days)", "theta",
                    "sigma /sqrt(day)"], lignes)
    print(f"Demi-vie OU : {ou['half_life']:.1f} jours (échantillon complet)")

    # 4. Backtest : exécution à la clôture suivante vs à la clôture du signal
    jours, trades, resume = backtest(spread)
    jours_mc, trades_mc, resume_mc = backtest(spread, decalage=0)
    res += "\n## Z-score backtest (1,000 bbl of spread)\n\n"
    res += f"Rule: {FENETRE}-day z-score, enter at +/-{SEUIL_ENTREE}, exit at {SEUIL_SORTIE}, " \
           f"cost {COUT} USD/bbl per position change.\n\n"
    indicateurs = [("sharpe", "Sharpe ratio", 2), ("annual_pnl_usd", "P&L per year (USD)", 0),
                   ("max_drawdown_usd", "Max drawdown (USD)", 0), ("n_trades", "Trades", 0),
                   ("hit_rate", "Hit rate", 2), ("avg_holding_days", "Avg holding (days)", 1),
                   ("time_in_market", "Time in market", 2)]
    res += tableau(["Metric", "Next-close execution", "Same-close execution"],
                   [[nom, f(resume[k], nd), f(resume_mc[k], nd)] for k, nom, nd in indicateurs])
    print(f"Sharpe : {resume['sharpe']:.2f} (clôture suivante) / {resume_mc['sharpe']:.2f} (même clôture)")

    # Sensibilité du Sharpe à la fenêtre et au seuil d'entrée
    grilles = {}
    for decalage in [1, 0]:
        g = pd.DataFrame(index=GRILLE_FENETRES, columns=GRILLE_SEUILS, dtype=float)
        for w in GRILLE_FENETRES:
            for e in GRILLE_SEUILS:
                g.loc[w, e] = backtest(spread, fenetre=w, seuil_entree=e, decalage=decalage)[2]["sharpe"]
        grilles[decalage] = g
    res += "\n### Sharpe ratio sensitivity, next-close execution (rows: window, columns: entry z)\n\n"
    res += tableau(["Window"] + [str(e) for e in GRILLE_SEUILS],
                   [[w] + [f(grilles[1].loc[w, e]) for e in GRILLE_SEUILS] for w in GRILLE_FENETRES])
    res += "\n### Same grid, same-close execution\n\n"
    res += tableau(["Window"] + [str(e) for e in GRILLE_SEUILS],
                   [[w] + [f(grilles[0].loc[w, e]) for e in GRILLE_SEUILS] for w in GRILLE_FENETRES])

    # 5. Options sur le spread
    s0 = spread.iloc[-1]
    T = JOURS_OPTION / 252
    vol_normale = spread.diff().iloc[-FENETRE_VOL:].std() * np.sqrt(252)   # USD/bbl/racine(an)
    ou_actuel = calibrer_ou(spread.loc[DATE_MIDLAND:])                       # régime actuel
    moyenne_ou, ecart_ou = moments_ou(ou_actuel, s0, JOURS_OPTION)
    vol_ou = ecart_ou / np.sqrt(T)            # dispersion à 1 mois d'un spread qui revient à la moyenne
    rendements = np.log(prix).diff().iloc[-FENETRE_VOL:]
    vol_brent, vol_wti = rendements.std() * np.sqrt(252)
    rho = rendements.corr().iloc[0, 1]
    f_brent, f_wti = prix["brent"].iloc[-1], prix["wti"].iloc[-1]

    def prime_rw(type_option, k):
        return prix_bachelier(s0, k, T, vol_normale, TAUX, type_option)

    def prime_ou(type_option, k):
        return prix_bachelier(s0, k, T, vol_ou, TAUX, type_option)

    def prime_kirk(type_option, k):
        return prix_kirk(f_brent, f_wti, k, T, vol_brent, vol_wti, rho, TAUX, type_option)

    res += f"\n## Options on the spread, {JOURS_OPTION} trading days to expiry\n\n"
    res += f"Spread on {FIN}: {f(s0)} USD/bbl. Normal volatility ({FENETRE_VOL}-day realised): " \
           f"{f(vol_normale)} USD/bbl/sqrt(yr). Brent vol {f(vol_brent * 100, 1)}%, WTI vol " \
           f"{f(vol_wti * 100, 1)}%, correlation {f(rho, 3)}. OU since {DATE_MIDLAND}: half-life " \
           f"{f(ou_actuel['half_life'], 1)} days, theta {f(ou_actuel['theta'])}; expected spread at " \
           f"expiry {f(moyenne_ou)} (sd {f(ecart_ou)}) versus a random-walk sd of " \
           f"{f(vol_normale * np.sqrt(T))}, i.e. an OU-consistent normal vol of {f(vol_ou)} instead " \
           f"of {f(vol_normale)}. All prices use today's spread as the forward. Discount rate " \
           f"{TAUX:.0%} (assumed).\n\n"
    options = [("put", BEAR_PUT[0]), ("put", BEAR_PUT[1]), ("call", STRANGLE[1])]
    res += tableau(["Option", "Random-walk vol (Bachelier)", "Two legs (Kirk)",
                    "OU-consistent vol (Bachelier)"],
                   [[f"{t} {f(k)}", f(prime_rw(t, k), 3), f(prime_kirk(t, k), 3), f(prime_ou(t, k), 3)]
                    for t, k in options])

    # Stratégies, au prix "random walk"
    strategies = {
        "Bear put spread": [(1, "put", BEAR_PUT[0], prime_rw("put", BEAR_PUT[0])),
                            (-1, "put", BEAR_PUT[1], prime_rw("put", BEAR_PUT[1]))],
        "Long strangle": [(1, "put", STRANGLE[0], prime_rw("put", STRANGLE[0])),
                          (1, "call", STRANGLE[1], prime_rw("call", STRANGLE[1]))],
    }
    x = np.linspace(0, 14, 2801)
    lignes = []
    for nom, jambes in strategies.items():
        cout = sum(q * prime for q, _, _, prime in jambes)
        valeur_ou = sum(q * prime_ou(t, k) for q, t, k, _ in jambes)
        pnl = pnl_expiration(jambes, x)
        lignes.append([nom, f(cout, 3), f(valeur_ou, 3),
                       " / ".join(f(p) for p in points_morts(jambes, x)),
                       f(pnl.max(), 2) if nom.startswith("Bear") else "open-ended", f(pnl.min(), 3)])
    res += "\nStrategies priced with the random-walk vol (cost) and the OU-consistent vol:\n\n"
    res += tableau(["Strategy", "Cost (random-walk vol)", "Value (OU vol)", "Break-even(s)",
                    "Max profit", "Max loss"], lignes)

    # 6. Graphiques
    graphique_prix(prix, spread)
    graphique_backtest(jours, jours_mc, resume["sharpe"], resume_mc["sharpe"])
    graphique_sensibilite(grilles)
    graphique_options(s0, vol_normale * np.sqrt(T), moyenne_ou, ecart_ou, ou_actuel["theta"],
                      strategies, x)

    with open(os.path.join(DOSSIER, "results.md"), "w", encoding="utf-8") as fichier:
        fichier.write(res)
    print("Résultats écrits dans results.md, graphiques dans figures/")


if __name__ == "__main__":
    main()
