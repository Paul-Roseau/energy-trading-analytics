import numpy as np
from scipy.stats import norm

def black_scholes(S, K, T, r, sigma, option_type="call", q=0.0):
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "call":
        return S * np.exp(-q*T) * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
    else:
        return K * np.exp(-r*T) * norm.cdf(-d2) - S * np.exp(-q*T) * norm.cdf(-d1)

def implied_vol(mkt, S, K, T, r, kind="call", q=0.0, tol=1e-8, it=100):
    sigma = 0.2
    for _ in range(it):                            # Newton-Raphson
        price = black_scholes(S, K, T, r, sigma, kind, q)
        d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        vega = S*np.exp(-q*T)*norm.pdf(d1)*np.sqrt(T)
        diff = price - mkt
        
        if abs(diff) < tol:
            return sigma
        if vega < 1e-12 or sigma <= 0:
            break                                  # instable -> bisection
        sigma -= diff/vega
        
    lo, hi = 1e-6, 5.0                             # repli robuste
    for _ in range(it):
        mid = 0.5*(lo+hi)
        if black_scholes(S, K, T, r, mid, kind, q) > mkt: 
            hi = mid
        else: 
            lo = mid
    return 0.5*(lo+hi)

# === Test de la fonction ===
if __name__ == "__main__":
    S_test = 100.0
    K_test = 100.0
    T_test = 1.0
    r_test = 0.05
    
    # On utilise le prix exact calculé par notre premier script (pour une vol de 20%)
    mkt_price = 10.4506 
    
    iv = implied_vol(mkt_price, S_test, K_test, T_test, r_test, kind="call")
    print("--- RÉSULTAT IMPLIED VOLATILITY ---")
    print(f"Prix de marché observé : {mkt_price}")
    print(f"Volatilité Implicite retrouvée par l'algorithme : {iv:.4%} ({iv:.4f})")