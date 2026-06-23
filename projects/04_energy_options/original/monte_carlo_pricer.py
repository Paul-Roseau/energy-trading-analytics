import numpy as np

def mc_european(S, K, T, r, sigma, kind="call", n=100_000, seed=42):
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal(n)
    ST = S*np.exp((r - 0.5*sigma**2)*T + sigma*np.sqrt(T)*Z)
    payoff = np.maximum(ST-K, 0) if kind=="call" else np.maximum(K-ST, 0)
    price = np.exp(-r*T)*payoff.mean()
    stderr = np.exp(-r*T)*payoff.std(ddof=1)/np.sqrt(n)
    return price, stderr

def mc_asian_call(S, K, T, r, sigma, steps=252, n=100_000, seed=42):
    rng = np.random.default_rng(seed)
    dt = T/steps
    # Création de n trajectoires, chacune avec 'steps' étapes
    Z = rng.standard_normal((n, steps))
    incr = (r - 0.5*sigma**2)*dt + sigma*np.sqrt(dt)*Z
    paths = S*np.exp(np.cumsum(incr, axis=1))     # chemins complets
    
    # Le payoff est basé sur la moyenne de la trajectoire
    payoff = np.maximum(paths.mean(axis=1) - K, 0)
    return np.exp(-r*T)*payoff.mean()

# === Test des fonctions ===
if __name__ == "__main__":
    # Définition des paramètres
    S_test = 100.0
    K_test = 100.0
    T_test = 1.0
    r_test = 0.05
    sigma_test = 0.20
    
    # Lancement des simulations
    prix_euro, err_euro = mc_european(S_test, K_test, T_test, r_test, sigma_test, kind="call")
    prix_asian = mc_asian_call(S_test, K_test, T_test, r_test, sigma_test)
    
    print("--- RÉSULTATS MONTE CARLO (100 000 simulations) ---")
    print(f"Prix Call Européen   : {prix_euro:.4f} (Erreur standard : +/- {err_euro:.4f})")
    print(f"Prix Call Asiatique  : {prix_asian:.4f}")
    print("\nNote : Le Call Asiatique est généralement moins cher que l'Européen")
    print("car la moyenne 'lisse' la volatilité extrême dont le Call Européen pourrait profiter.")