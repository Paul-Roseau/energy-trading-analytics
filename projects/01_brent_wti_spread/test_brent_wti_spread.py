"""Tests de l'étude du spread Brent-WTI : calibration OU, signal z-score et données"""
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
