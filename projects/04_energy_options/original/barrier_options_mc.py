import numpy as np

def mc_barrier_call(S, K, B, T, r, sigma, steps=252, n=100_000, seed=42):
    # down-and-out : l'option meurt si le chemin touche B par le bas
    rng = np.random.default_rng(seed)
    dt = T/steps
    Z = rng.standard_normal((n, steps))
    incr = (r - 0.5*sigma**2)*dt + sigma*np.sqrt(dt)*Z
    paths = S*np.exp(np.cumsum(incr, axis=1))
    
    ST = paths[:, -1]
    # Vérification si l'un des points de la trajectoire est inférieur ou égal à la barrière B
    knocked = paths.min(axis=1) <= B
    
    # Si touché -> payoff = 0, sinon payoff classique du Call
    payoff = np.where(knocked, 0.0, np.maximum(ST-K, 0))
    return np.exp(-r*T)*payoff.mean()

# === Test de la fonction ===
if __name__ == "__main__":
    S_test = 100.0      # Spot
    K_test = 100.0      # Strike
    B_test = 85.0       # Barrière (Down-and-Out)
    T_test = 1.0        # 1 an
    r_test = 0.05       # 5%
    sigma_test = 0.20   # 20%
    
    prix_barriere = mc_barrier_call(S_test, K_test, B_test, T_test, r_test, sigma_test)
    
    print("--- RÉSULTATS OPTION À BARRIÈRE ---")
    print(f"Prix du Down-and-Out Call : {prix_barriere:.4f}")
    print("\nPour comparaison :")
    print("Un Call Européen classique sans barrière vaut environ 10.4506")
    print(f"La présence de la barrière à {B_test} a réduit le coût de l'option de {((10.4506-prix_barriere)/10.4506)*100:.1f}%.")