"""Tests de l'étude du spread Brent-WTI : calibration OU, signal z-score, backtest, options et données"""
import warnings

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import brent_wti_spread as bws

T_MOIS = 21 / 252                                # un mois de bourse
TAUX = 0.04
GRILLE_SPREAD = np.linspace(0.0, 14.0, 2801)     # pas de 0,005 USD/bbl


def simuler_ou(kappa, theta, sigma, nb_pas, graine):
    """OU simulé avec la discrétisation exacte, pas d'un jour, départ à theta"""
    rng = np.random.default_rng(graine)
    b = np.exp(-kappa)
    ecart = sigma * np.sqrt((1 - b ** 2) / (2 * kappa))
    x = np.empty(nb_pas)
    x[0] = theta
    for t in range(1, nb_pas):
        x[t] = theta + (x[t - 1] - theta) * b + ecart * rng.standard_normal()
    return x


def spread_synthetique():
    """Spread qui oscille autour de 5 USD ; la chute de 4 USD du jour 122 retourne une position short en long"""
    rng = np.random.default_rng(3)
    nb_jours = 900
    niveau = 5 + np.sin(np.arange(nb_jours) / 15) + rng.normal(0, 0.1, nb_jours)
    niveau[122:] -= 4.0
    return pd.Series(niveau, index=pd.bdate_range("2020-01-01", periods=nb_jours))


# ============================================================================
# ORNSTEIN-UHLENBECK
# ============================================================================

def test_ou_calibration_recovers_known_parameters():
    x = simuler_ou(kappa=0.05, theta=5.0, sigma=0.3, nb_pas=20_000, graine=7)
    ou = bws.calibrer_ou(x)
    assert ou["kappa"] == pytest.approx(0.05, rel=0.10)
    assert ou["theta"] == pytest.approx(5.0, abs=0.2)
    assert ou["sigma"] == pytest.approx(0.3, rel=0.03)
    assert ou["half_life"] == pytest.approx(np.log(2) / ou["kappa"])


def test_ou_moments_at_zero_horizon():
    ou = {"kappa": 0.1, "theta": 4.0, "sigma": 0.5}
    moyenne, ecart = bws.moments_ou(ou, x0=7.0, horizon=0.0)
    assert moyenne == pytest.approx(7.0)
    assert ecart == pytest.approx(0.0)


def test_ou_gap_to_mean_halves_after_one_half_life():
    ou = {"kappa": 0.1, "theta": 4.0, "sigma": 0.5}
    moyenne, _ = bws.moments_ou(ou, x0=7.0, horizon=np.log(2) / 0.1)
    assert moyenne - 4.0 == pytest.approx((7.0 - 4.0) / 2)


def test_ou_moments_converge_to_stationary_distribution():
    ou = {"kappa": 0.1, "theta": 4.0, "sigma": 0.5}
    moyenne, ecart = bws.moments_ou(ou, x0=7.0, horizon=1_000.0)
    assert moyenne == pytest.approx(4.0)
    assert ecart == pytest.approx(0.5 / np.sqrt(2 * 0.1))


@pytest.mark.parametrize("serie", [1.02 ** np.arange(200), (-1.0) ** np.arange(200)],
                         ids=["explosive", "alternating"])
def test_ou_calibration_rejects_series_without_mean_reversion(serie):
    # pente AR(1) de 1,02 ou de -1 : aucune demi-vie n'a de sens
    with pytest.raises(ValueError, match="retour à la moyenne"):
        bws.calibrer_ou(serie)


# ============================================================================
# SIGNAL Z-SCORE
# ============================================================================

def test_target_positions_follow_entry_and_exit_rules():
    # short à 2,1, maintenu à 1,0, soldé quand z repasse par 0 ; long à -2,3, soldé à 0,2 ;
    # short à 2,4 puis retournement le même jour à -2,5
    z = pd.Series([np.nan, 0.5, 2.1, 1.0, -0.1, -2.3, -1.0, 0.2, 2.4, -2.5])
    positions = bws.positions_cibles(z, seuil_entree=2.0, seuil_sortie=0.0)
    assert positions.tolist() == [0, 0, -1, -1, 0, 1, 1, 0, -1, 1]
    assert positions.index.equals(z.index)


def test_missing_z_score_closes_the_position():
    z = pd.Series([2.5, 1.0, np.nan, 1.0])
    assert bws.positions_cibles(z, seuil_entree=2.0, seuil_sortie=0.0).tolist() == [-1, -1, 0, 0]


# ============================================================================
# BACKTEST
# ============================================================================

def test_trade_pnl_adds_up_to_daily_pnl():
    jours, trades, _ = bws.backtest(spread_synthetique(), fenetre=60)
    assert (jours["position"].diff().abs() == 2).any()     # le retournement est bien couvert
    assert sum(t["pnl"] for t in trades) == pytest.approx(jours["pnl"].sum())


def test_reversal_closes_one_trade_and_opens_the_other():
    # short le jour 1, retournement long le jour 3, sortie le jour 5
    dates = pd.bdate_range("2024-01-01", periods=6)
    spread = pd.Series([5.0, 5.2, 5.1, 4.8, 5.0, 5.3], index=dates)
    position = pd.Series([0.0, -1.0, -1.0, 1.0, 1.0, 0.0], index=dates)
    pnl_brut = position.shift(1).fillna(0.0) * spread.diff().fillna(0.0)
    trades = bws.liste_trades(spread, position, pnl_brut, cout=0.02, taille=1000)
    assert [(t["sens"], t["entree"], t["sortie"], t["jours"]) for t in trades] == [
        ("short", dates[1], dates[3], 2),
        ("long", dates[3], dates[5], 2),
    ]
    # short : +0,10 puis +0,30 USD/bbl ; long : +0,20 puis +0,30 ; 0,02 USD/bbl à chaque entrée et sortie
    assert trades[0]["pnl"] == pytest.approx(360.0)
    assert trades[1]["pnl"] == pytest.approx(460.0)


def test_costs_are_charged_per_lot_traded():
    spread = spread_synthetique()
    avec_couts, _, _ = bws.backtest(spread, fenetre=60, cout=0.02)
    sans_couts, _, _ = bws.backtest(spread, fenetre=60, cout=0.0)
    assert avec_couts["position"].equals(sans_couts["position"])
    position = avec_couts["position"]
    lots = (position - position.shift(1).fillna(0.0)).abs()
    ecart = sans_couts["pnl"] - avec_couts["pnl"]
    # rien sans changement de position, 20 USD à une entrée ou une sortie, 40 USD à un retournement
    for nb_lots, cout_usd in [(0, 0.0), (1, 20.0), (2, 40.0)]:
        assert (lots == nb_lots).any()
        assert ecart[lots == nb_lots].to_numpy() == pytest.approx(cout_usd)


@pytest.mark.parametrize("decalage, dernier_jour_inchange", [(1, 600), (0, 599)])
def test_positions_ignore_future_prices(decalage, dernier_jour_inchange):
    # spread modifié à partir du jour 600 : à la clôture suivante, la position de ce jour a été
    # décidée la veille ; à la même clôture, elle dépend déjà du prix du jour
    spread = spread_synthetique()
    modifie = spread.copy()
    modifie.iloc[600:] += 10.0
    reference, _, _ = bws.backtest(spread, fenetre=60, decalage=decalage)
    perturbe, _, _ = bws.backtest(modifie, fenetre=60, decalage=decalage)
    fin = dernier_jour_inchange + 1
    assert perturbe["position"].iloc[:fin].equals(reference["position"].iloc[:fin])
    assert not perturbe["position"].equals(reference["position"])


def test_max_drawdown_is_measured_from_the_running_peak():
    jours, _, resume = bws.backtest(spread_synthetique(), fenetre=60)
    sommet, pire = 0.0, 0.0                                  # capital de départ : 0 USD
    for valeur in jours["cumul"].dropna():
        sommet = max(sommet, valeur)
        pire = min(pire, valeur - sommet)
    assert pire < 0
    assert resume["max_drawdown_usd"] == pytest.approx(pire)


def test_sharpe_is_nan_without_trades():
    with warnings.catch_warnings():
        warnings.simplefilter("error")          # aucune division par zéro
        jours, trades, resume = bws.backtest(spread_synthetique(), fenetre=60, seuil_entree=50.0)
    assert trades == [] and (jours["position"] == 0).all()
    assert np.isnan(resume["sharpe"])
    assert resume["annual_pnl_usd"] == 0.0


# ============================================================================
# OPTIONS SUR LE SPREAD
# ============================================================================

@pytest.mark.parametrize("F, K", [(4.2, 5.0), (6.0, 5.0), (-1.0, 0.5)])
def test_bachelier_put_call_parity(F, K):
    call = bws.prix_bachelier(F, K, T_MOIS, 6.0, TAUX, "call")
    put = bws.prix_bachelier(F, K, T_MOIS, 6.0, TAUX, "put")
    assert call - put == pytest.approx(np.exp(-TAUX * T_MOIS) * (F - K))


def test_bachelier_at_the_money_closed_form():
    prix = bws.prix_bachelier(5.0, 5.0, T_MOIS, 6.0, TAUX, "call")
    assert prix == pytest.approx(np.exp(-TAUX * T_MOIS) * 6.0 * np.sqrt(T_MOIS / (2 * np.pi)))


def test_kirk_matches_margrabe_at_zero_strike():
    F1, F2, vol1, vol2, rho = 68.0, 64.0, 0.30, 0.32, 0.9
    vol = np.sqrt(vol1 ** 2 - 2 * rho * vol1 * vol2 + vol2 ** 2)
    d1 = (np.log(F1 / F2) + 0.5 * vol ** 2 * T_MOIS) / (vol * np.sqrt(T_MOIS))
    margrabe = np.exp(-TAUX * T_MOIS) * (F1 * norm.cdf(d1) - F2 * norm.cdf(d1 - vol * np.sqrt(T_MOIS)))
    assert bws.prix_kirk(F1, F2, 0.0, T_MOIS, vol1, vol2, rho, TAUX, "call") == pytest.approx(margrabe)


@pytest.mark.parametrize("K", [3.0, 5.0])
@pytest.mark.parametrize("type_option", ["call", "put"])
def test_kirk_agrees_with_monte_carlo(K, type_option):
    # deux futures lognormaux corrélés, 500 000 tirages antithétiques
    F1, F2, vol1, vol2, rho = 68.0, 64.0, 0.30, 0.32, 0.9
    rng = np.random.default_rng(11)
    z1 = rng.standard_normal(500_000)
    z2 = rho * z1 + np.sqrt(1 - rho ** 2) * rng.standard_normal(500_000)
    gains = []
    for signe in (1, -1):
        f1 = F1 * np.exp(-0.5 * vol1 ** 2 * T_MOIS + vol1 * np.sqrt(T_MOIS) * signe * z1)
        f2 = F2 * np.exp(-0.5 * vol2 ** 2 * T_MOIS + vol2 * np.sqrt(T_MOIS) * signe * z2)
        ecart = f1 - f2 - K if type_option == "call" else K - (f1 - f2)
        gains.append(np.maximum(ecart, 0.0))
    valeurs = np.exp(-TAUX * T_MOIS) * (gains[0] + gains[1]) / 2
    erreur_type = valeurs.std(ddof=1) / np.sqrt(len(valeurs))
    kirk = bws.prix_kirk(F1, F2, K, T_MOIS, vol1, vol2, rho, TAUX, type_option)
    assert abs(kirk - valeurs.mean()) < 4 * erreur_type


def test_bear_put_spread_payoff_and_break_even():
    # put 6,50 acheté 1,00 et put 5,00 vendu 0,40 : coût net 0,60
    jambes = [(1, "put", 6.50, 1.00), (-1, "put", 5.00, 0.40)]
    assert bws.points_morts(jambes, GRILLE_SPREAD) == pytest.approx([5.90])
    # gain maximal sous 5,00, perte maximale au-dessus de 6,50
    assert bws.pnl_expiration(jambes, np.array([4.0, 5.90, 7.0])) == pytest.approx([0.90, 0.0, -0.60])


def test_long_strangle_break_evens():
    # put 5,00 à 0,30 et call 8,50 à 0,25 : coût 0,55, perdu entre les deux strikes
    jambes = [(1, "put", 5.00, 0.30), (1, "call", 8.50, 0.25)]
    assert bws.points_morts(jambes, GRILLE_SPREAD) == pytest.approx([4.45, 9.05])
    assert bws.pnl_expiration(jambes, np.array([6.0, 8.0])) == pytest.approx([-0.55, -0.55])


@pytest.mark.parametrize("T, vol", [(0.0, 6.0), (T_MOIS, 0.0)], ids=["expiry", "zero-vol"])
def test_bachelier_returns_intrinsic_value_without_time_or_volatility(T, vol):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert bws.prix_bachelier(6.0, 5.0, T, vol, TAUX, "call") == pytest.approx(np.exp(-TAUX * T))
        assert bws.prix_bachelier(6.0, 5.0, T, vol, TAUX, "put") == 0.0
        assert bws.prix_bachelier(5.0, 5.0, T, vol, TAUX, "call") == 0.0     # à la monnaie


def test_kirk_returns_intrinsic_value_at_expiry():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert bws.prix_kirk(68.0, 64.0, 3.0, 0.0, 0.30, 0.32, 0.9, TAUX, "call") == pytest.approx(1.0)
        assert bws.prix_kirk(68.0, 64.0, 3.0, 0.0, 0.30, 0.32, 0.9, TAUX, "put") == 0.0
        assert bws.prix_kirk(68.0, 64.0, 4.0, 0.0, 0.30, 0.32, 0.9, TAUX, "call") == 0.0


def test_kirk_requires_positive_f2_plus_k():
    with pytest.raises(ValueError, match=r"F2 \+ K > 0"):
        bws.prix_kirk(68.0, 64.0, -64.0, T_MOIS, 0.30, 0.32, 0.9, TAUX, "call")


@pytest.mark.parametrize("pricer, arguments", [
    (bws.prix_bachelier, (5.0, 4.0, T_MOIS, 6.0, TAUX)),
    (bws.prix_kirk, (68.0, 64.0, 3.0, T_MOIS, 0.30, 0.32, 0.9, TAUX)),
], ids=["bachelier", "kirk"])
def test_unknown_option_type_is_rejected(pricer, arguments):
    # une faute de frappe (« Call ») ne doit pas donner silencieusement le prix du put
    with pytest.raises(ValueError, match="'call' ou 'put'"):
        pricer(*arguments, "Call")


# ============================================================================
# DONNÉES
# ============================================================================

def test_prices_are_joined_on_common_dates():
    prix = bws.charger_brent_wti()
    assert list(prix.columns) == ["brent", "wti"]
    assert len(prix) == 2_493
    assert prix.index[0] == pd.Timestamp("2016-01-07")
    assert prix.index[-1] == pd.Timestamp("2026-02-11")
    assert prix.index.is_monotonic_increasing and prix.index.is_unique
    assert pd.Timestamp(bws.JOUR_EXCLU) not in prix.index
    assert prix.notna().all().all()
