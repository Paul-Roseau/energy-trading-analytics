"""Tests de l'étude du spread Brent-WTI : calibration OU, signal z-score, backtest et données"""
import numpy as np
import pandas as pd
import pytest

import brent_wti_spread as bws


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
