import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
from scipy.stats import norm, chi2
from scipy.special import xlogy
from statsmodels.tsa.stattools import adfuller


# ============================================================================
# PARAMÈTRES
# ============================================================================

DOSSIER = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DOSSIER, "..", "..", "data")
FIG_DIR = os.path.join(DOSSIER, "figures")

DEBUT = "2021-01-04"
FIN = "2025-12-31"
FIN_CALIBRATION = "2023-12-31"   # calibration sur 2021-2023, test sur 2024-2025

NB_TRAJECTOIRES = 5000
GRAINE = 2026
BANDE = (0.125, 0.875)           # bande centrale à 75%

LAMBDAS = [0.90, 0.94, 0.97]     # EWMA RiskMetrics
CONFIANCES = [0.95, 0.99]
FENETRE_HS = 250                 # simulation historique
LAMBDA_FHS = 0.94                # simulation historique filtrée

# Couleurs des graphiques
FOND = "#fcfcfb"
ENCRE = "#0b0b0b"
ENCRE_2 = "#52514e"
GRIS = "#898781"
GRIS_CLAIR = "#b9b8b2"
GRILLE = "#e1e0d9"
AXE = "#c3c2b7"
BLEU = "#2a78d6"
ORANGE = "#eb6834"

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
# MODÈLES DE PRIX : GBM ET ORNSTEIN-UHLENBECK
# ============================================================================

def calibrer_gbm(prix, dt=1 / 252):
    """GBM : dS = mu S dt + sigma S dW, estimé sur les rendements log"""
    r = np.diff(np.log(np.asarray(prix, dtype=float)))
    sigma = r.std(ddof=1) / np.sqrt(dt)
    mu = r.mean() / dt + 0.5 * sigma ** 2
    return mu, sigma


def simuler_gbm(mu, sigma, s0, nb_pas, nb_traj, graine, dt=1 / 252):
    """Simulation exacte du GBM, tableau (nb_pas + 1, nb_traj)"""
    rng = np.random.default_rng(graine)
    chocs = rng.standard_normal((nb_pas, nb_traj))
    increments = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * chocs
    log_trajectoires = np.vstack([np.zeros(nb_traj), np.cumsum(increments, axis=0)])
    return s0 * np.exp(log_trajectoires)


def calibrer_ou(x, dt=1 / 252):
    """OU par la discrétisation exacte AR(1) : x[t+1] = a + b x[t] + e"""
    x = np.asarray(x, dtype=float)
    b, a = np.polyfit(x[:-1], x[1:], 1)
    residus = x[1:] - (a + b * x[:-1])
    kappa = -np.log(b) / dt
    theta = a / (1 - b)
    sigma = residus.std(ddof=2) * np.sqrt(2 * kappa / (1 - b ** 2))
    return kappa, theta, sigma


def simuler_ou(kappa, theta, sigma, x0, nb_pas, nb_traj, graine, dt=1 / 252):
    """Simulation exacte de l'OU, tableau (nb_pas + 1, nb_traj)"""
    rng = np.random.default_rng(graine)
    b = np.exp(-kappa * dt)
    ecart = sigma * np.sqrt((1 - b ** 2) / (2 * kappa))
    trajectoires = np.empty((nb_pas + 1, nb_traj))
    trajectoires[0] = x0
    for t in range(nb_pas):
        trajectoires[t + 1] = theta + b * (trajectoires[t] - theta) + ecart * rng.standard_normal(nb_traj)
    return trajectoires


def evaluer_prevision(trajectoires, reel):
    """Compare les trajectoires simulées aux prix réalisés (RMSE, couverture de la bande)"""
    sims = trajectoires[1:len(reel) + 1]
    moyenne = sims.mean(axis=1)
    bas, haut = np.quantile(sims, BANDE, axis=1)
    r = reel.to_numpy()
    return {
        "moyenne": moyenne, "bas": bas, "haut": haut,
        "rmse": np.sqrt(np.mean((moyenne - r) ** 2)),
        "couverture": np.mean((r >= bas) & (r <= haut)),
        "moyenne_fin": sims[-1].mean(),
        "bas_fin": np.quantile(sims[-1], BANDE[0]),
        "haut_fin": np.quantile(sims[-1], BANDE[1]),
    }


# ============================================================================
# VALUE AT RISK
# ============================================================================
# Chaque VaR est une prévision pour le jour t faite avec les rendements jusqu'à t-1.
# Position longue : perte si r < -VaR_long. Position courte : perte si r > VaR_short.

def vol_ewma(rendements, lam, fenetre_init=30):
    """Volatilité EWMA (RiskMetrics) : s2[t] = lam s2[t-1] + (1 - lam) r[t-1]^2"""
    r = rendements.to_numpy()
    s2 = np.full(len(r), np.nan)
    s2[fenetre_init] = np.var(r[:fenetre_init], ddof=1)   # initialisation
    for t in range(fenetre_init + 1, len(r)):
        s2[t] = lam * s2[t - 1] + (1 - lam) * r[t - 1] ** 2
    return pd.Series(np.sqrt(s2), index=rendements.index)


def var_ewma(rendements, lam, confiance):
    """VaR normale EWMA (moyenne nulle), identique en long et en short"""
    var = norm.ppf(confiance) * vol_ewma(rendements, lam)
    return var, var


def var_historique(rendements, confiance, fenetre=FENETRE_HS):
    """Simulation historique sur les `fenetre` derniers rendements"""
    passe = rendements.shift(1).rolling(fenetre)
    return -passe.quantile(1 - confiance), passe.quantile(confiance)


def var_historique_filtree(rendements, lam, confiance, fenetre=FENETRE_HS):
    """Simulation historique filtrée : rendements standardisés par l'EWMA,
    quantiles empiriques remis à l'échelle de la volatilité du jour"""
    vol = vol_ewma(rendements, lam)
    passe = (rendements / vol).shift(1).rolling(fenetre)
    return -passe.quantile(1 - confiance) * vol, passe.quantile(confiance) * vol


def test_kupiec(nb_obs, nb_depassements, p):
    """Test de Kupiec (1995) : le nombre de dépassements est-il cohérent avec p ?"""
    p_hat = nb_depassements / nb_obs
    log_l0 = xlogy(nb_obs - nb_depassements, 1 - p) + xlogy(nb_depassements, p)
    log_l1 = xlogy(nb_obs - nb_depassements, 1 - p_hat) + xlogy(nb_depassements, p_hat)
    lr = -2 * (log_l0 - log_l1)
    return chi2.sf(lr, 1)


def test_christoffersen(depassements):
    """Test de Christoffersen (1998) : les dépassements sont-ils indépendants ?"""
    h = np.asarray(depassements, dtype=int)
    avant, apres = h[:-1], h[1:]
    n00 = np.sum((avant == 0) & (apres == 0))
    n01 = np.sum((avant == 0) & (apres == 1))
    n10 = np.sum((avant == 1) & (apres == 0))
    n11 = np.sum((avant == 1) & (apres == 1))
    pi0 = n01 / (n00 + n01) if n00 + n01 > 0 else 0.0
    pi1 = n11 / (n10 + n11) if n10 + n11 > 0 else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    log_l0 = xlogy(n00 + n10, 1 - pi) + xlogy(n01 + n11, pi)
    log_l1 = xlogy(n00, 1 - pi0) + xlogy(n01, pi0) + xlogy(n10, 1 - pi1) + xlogy(n11, pi1)
    lr = -2 * (log_l0 - log_l1)
    return chi2.sf(lr, 1)


def backtest_var(rendements, var_long, var_short, confiance):
    """Taux de dépassement et tests, pour une position longue et une position courte"""
    p = 1 - confiance
    res = {}
    for cote, depassements in [("long", rendements < -var_long), ("short", rendements > var_short)]:
        res[f"taux_{cote}"] = depassements.mean()
        res[f"kupiec_{cote}"] = test_kupiec(len(rendements), depassements.sum(), p)
        res[f"indep_{cote}"] = test_christoffersen(depassements.to_numpy())
    return res


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


def graphique_monte_carlo(calibration, test, prev_gbm, prev_ou):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True, gridspec_kw={"wspace": 0.12})
    historique = calibration.iloc[-130:]
    for ax, prev, couleur, titre in ((axes[0], prev_gbm, BLEU, "Geometric Brownian motion"),
                                     (axes[1], prev_ou, ORANGE, "Ornstein-Uhlenbeck (log price)")):
        ax.plot(historique.index, historique, color=ENCRE_2, lw=1.0)
        ax.fill_between(test.index, prev["bas"], prev["haut"], color=couleur, alpha=0.12, lw=0,
                        label="75% band")
        ax.plot(test.index, prev["moyenne"], color=couleur, lw=1.8, label="Mean of 5,000 paths")
        ax.plot(test.index, test, color=ENCRE, lw=1.0, label="Actual")
        ax.axvline(test.index[0], color=AXE, lw=0.8)
        ax.set_title(f"{titre}\nRMSE {prev['rmse']:.1f} USD/bbl, "
                     f"{prev['couverture']:.0%} of days inside the band", linespacing=1.5)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1,)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        ax.margins(x=0.01)
        ax.legend(loc="upper left")
    axes[0].set_ylabel("USD/bbl")
    axes[0].set_ylim(30, 190)
    source(axes[0], "Calibrated on 2021-2023, simulated from the last 2023 price; "
                    "grey line: end of the training window.")
    fig.savefig(os.path.join(FIG_DIR, "monte_carlo.png"), bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def graphique_var(rendements, var_ewma_99, var_fhs_99):
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(rendements.index, rendements * 100, color=GRIS_CLAIR, lw=0.7)
    for var, couleur, nom in ((var_ewma_99, BLEU, "EWMA normal 99%"),
                              (var_fhs_99, ORANGE, "Filtered historical simulation 99%")):
        var = var * 100
        depassements = rendements * 100 < -var
        ax.plot(var.index, -var, color=couleur, lw=1.4,
                label=f"{nom}: {depassements.sum()} breaches ({depassements.mean():.1%}, expected 1.0%)")
        ax.scatter(rendements.index[depassements], (rendements * 100)[depassements], s=22,
                   color=couleur, edgecolor=FOND, linewidth=1.0, zorder=3)
    ax.axhline(0, color=AXE, lw=0.8)
    ax.set_title("One-day 99% VaR of a long Brent position versus realised returns, %")
    ax.legend(loc="lower right")
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.margins(x=0.01)
    source(ax, "Dots: days when the loss exceeded the VaR forecast made the day before.")
    fig.savefig(os.path.join(FIG_DIR, "var_backtest.png"), bbox_inches="tight", pad_inches=0.2)
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

    # 2. Calibration sur 2021-2023
    calibration = brent.loc[:FIN_CALIBRATION]
    mu, sigma_gbm = calibrer_gbm(calibration)
    kappa, theta, sigma_ou = calibrer_ou(np.log(calibration))
    # Correction du biais de petit échantillon sur kappa (Kendall, 1954)
    n = len(calibration) - 1
    b = np.exp(-kappa / 252)
    b_corrige = min(b + (1 + 3 * b) / n, 0.99999)
    kappa_corrige = -np.log(b_corrige) * 252
    res += f"\n## Calibration, training window {DEBUT} to {FIN_CALIBRATION} ({len(calibration)} prices)\n\n"
    res += tableau(["Parameter", "GBM", "OU on log price"], [
        ["Drift mu", f"{mu:.2%}", "-"],
        ["Volatility sigma", f"{sigma_gbm:.2%}", f"{sigma_ou:.2%}"],
        ["Mean reversion kappa (per year)", "-", f(kappa)],
        ["Half-life", "-", f"{np.log(2) / kappa * 252:.0f} trading days"],
        ["Long-run level exp(theta)", "-", f"{np.exp(theta):.2f} USD/bbl"],
        ["kappa after Kendall bias correction", "-",
         f"{kappa_corrige:.2f} (half-life {np.log(2) / kappa_corrige * 252:.0f} days)"],
    ])

    # 3. Prévisions Monte Carlo hors échantillon
    s0 = calibration.iloc[-1]
    test = brent[brent.index > calibration.index[-1]]
    traj_gbm = simuler_gbm(mu, sigma_gbm, s0, len(test), NB_TRAJECTOIRES, GRAINE)
    traj_ou = np.exp(simuler_ou(kappa, theta, sigma_ou, np.log(s0), len(test), NB_TRAJECTOIRES, GRAINE + 1))
    lignes = []
    previsions = {}
    for horizon, reel in [("2024", test.loc[:"2024-12-31"]), ("2024-2025", test)]:
        for modele, traj in [("GBM", traj_gbm), ("OU", traj_ou)]:
            prev = evaluer_prevision(traj, reel)
            previsions[(horizon, modele)] = prev
            lignes.append([horizon, modele, f(prev["moyenne_fin"]),
                           f"{f(prev['bas_fin'])} - {f(prev['haut_fin'])}", f(reel.iloc[-1]),
                           f(prev["rmse"]), f"{prev['couverture']:.0%}"])
    res += f"\n## Monte Carlo forecasts from {calibration.index[-1].date()} " \
           f"(S0 = {f(s0)}, {NB_TRAJECTOIRES:,} paths)\n\n"
    res += tableau(["Horizon", "Model", "Terminal mean", "75% band at horizon", "Actual at horizon",
                    "RMSE of mean path", "Days inside 75% band"], lignes)
    print(f"RMSE 2024 : GBM {previsions[('2024', 'GBM')]['rmse']:.2f}, OU {previsions[('2024', 'OU')]['rmse']:.2f}")

    # 4. Backtest des VaR, sur la même fenêtre pour tous les modèles
    modeles = {}
    for c in CONFIANCES:
        for lam in LAMBDAS:
            modeles[(f"EWMA normal, lambda {lam}", c)] = var_ewma(rendements, lam, c)
        modeles[(f"Historical simulation, {FENETRE_HS} d", c)] = var_historique(rendements, c)
        modeles[(f"Filtered HS, lambda {LAMBDA_FHS}", c)] = var_historique_filtree(rendements, LAMBDA_FHS, c)
    valide = pd.concat([v[0] for v in modeles.values()], axis=1).notna().all(axis=1)
    fenetre = rendements.index[valide]
    r = rendements.loc[fenetre]

    res += f"\n## One-day VaR backtest, {fenetre[0].date()} to {fenetre[-1].date()} " \
           f"({len(fenetre):,} days, same window for every model)\n\n"
    res += "Exceedance rates for a long and a short position; Kupiec tests coverage, " \
           "Christoffersen tests independence (p < 0.05 rejects the model).\n\n"
    lignes = []
    for (nom, c), (var_l, var_s) in modeles.items():
        bt = backtest_var(r, var_l.loc[fenetre], var_s.loc[fenetre], c)
        lignes.append([nom, f"{c:.0%}", f"{bt['taux_long']:.2%}", f(bt["kupiec_long"], 3),
                       f(bt["indep_long"], 3), f"{bt['taux_short']:.2%}", f(bt["kupiec_short"], 3),
                       f(bt["indep_short"], 3)])
    res += tableau(["Model", "Conf.", "Long: breaches", "Kupiec p", "Indep. p", "Short: breaches",
                    "Kupiec p", "Indep. p"], lignes)

    # 5. Graphiques
    graphique_prix(brent, rendements)
    graphique_monte_carlo(calibration, test, previsions[("2024-2025", "GBM")],
                          previsions[("2024-2025", "OU")])
    graphique_var(r, modeles[("EWMA normal, lambda 0.94", 0.99)][0].loc[fenetre],
                  modeles[(f"Filtered HS, lambda {LAMBDA_FHS}", 0.99)][0].loc[fenetre])

    with open(os.path.join(DOSSIER, "results.md"), "w", encoding="utf-8") as fichier:
        fichier.write(res)
    print("Résultats écrits dans results.md, graphiques dans figures/")


if __name__ == "__main__":
    main()
