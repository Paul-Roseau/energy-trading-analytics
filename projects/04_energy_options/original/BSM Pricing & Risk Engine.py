import numpy as np
from scipy.stats import norm

def black_scholes(S, K, T, r, sigma, option_type="call", q=0.0):
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == "call":
        return S * np.exp(-q*T) * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
    else:
        return K * np.exp(-r*T) * norm.cdf(-d2) - S * np.exp(-q*T) * norm.cdf(-d1)

def bs_greeks(S, K, T, r, sigma, option_type="call", q=0.0):
    d1 = (np.log(S / K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    phi = norm.pdf(d1)
    
    gamma = np.exp(-q*T) * phi / (S * sigma * np.sqrt(T))
    vega  = S * np.exp(-q*T) * phi * np.sqrt(T)          
    
    if option_type == "call":
        delta = np.exp(-q*T) * norm.cdf(d1)
        theta = (-S * np.exp(-q*T) * phi * sigma / (2 * np.sqrt(T))
                 - r * K * np.exp(-r*T) * norm.cdf(d2) + q * S * np.exp(-q*T) * norm.cdf(d1))
        rho   = K * T * np.exp(-r*T) * norm.cdf(d2)
    else:
        delta = -np.exp(-q*T) * norm.cdf(-d1)
        theta = (-S * np.exp(-q*T) * phi * sigma / (2 * np.sqrt(T))
                 + r * K * np.exp(-r*T) * norm.cdf(-d2) - q * S * np.exp(-q*T) * norm.cdf(-d1))
        rho   = -K * T * np.exp(-r*T) * norm.cdf(-d2)
        
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}

# === Test des fonctions ===
if __name__ == "__main__":
    # Définition des paramètres du marché
    S_test = 100.0      # Prix actuel du sous-jacent (Spot)
    K_test = 100.0      # Prix d'exercice (Strike)
    T_test = 1.0        # Temps jusqu'à l'échéance en années (1 an)
    r_test = 0.05       # Taux d'intérêt sans risque (5%)
    sigma_test = 0.20   # Volatilité implicite (20%)
    
    # Calcul et affichage du prix du Call
    prix_call = black_scholes(S_test, K_test, T_test, r_test, sigma_test, option_type="call")
    print("--- RÉSULTATS BLACK-SCHOLES ---")
    print(f"Prix du Call : {prix_call:.4f}")
    
    # Calcul et affichage des Grecques
    grecques_call = bs_greeks(S_test, K_test, T_test, r_test, sigma_test, option_type="call")
    print("\n--- GRECQUES ---")
    for nom, valeur in grecques_call.items():
        print(f"{nom.capitalize():<6} : {valeur:.4f}")