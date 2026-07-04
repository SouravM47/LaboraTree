"""BBO-style wrapper feature selection — staged search for the animation.

Not a model family: this powers the dedicated feature-selection pipeline step. Each candidate
feature-subset is a "habitat" scored by a quick model fit; strong habitats share features with weak
ones (migration) and random mutations explore — the population converges on a compact subset.
"""

from __future__ import annotations

import io

from .common import prep_xy
from .schema import FeatureSelectionTrace

POP, GENS, SEARCH_TOP = 8, 5, 12


def feature_selection_trace(data: bytes, target: str) -> FeatureSelectionTrace:
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.metrics import accuracy_score, r2_score
    from sklearn.model_selection import train_test_split

    df = pd.read_csv(io.BytesIO(data), nrows=1500)
    if target not in df.columns:
        target = df.columns[-1]
    X, y, feats, task, _labels = prep_xy(df, target)
    if len(feats) < 2:
        raise ValueError("need at least 2 numeric features for selection")

    strat = y if (task == "classification" and y.nunique() > 1) else None
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=0, stratify=strat)

    def fitness(mask) -> float:
        cols = [feats[i] for i in range(len(feats)) if mask[i]]
        if not cols:
            return 0.0
        try:
            if task == "classification":
                m = LogisticRegression(max_iter=300).fit(Xtr[cols], ytr)
                acc = accuracy_score(yte, m.predict(Xte[cols]))
            else:
                m = LinearRegression().fit(Xtr[cols], ytr)
                acc = max(0.0, r2_score(yte, m.predict(Xte[cols])))
        except Exception:
            return 0.0
        return float(acc - 0.02 * (sum(mask) / len(feats)))  # small compactness penalty

    # one-feature relevance → keep the top ~12 as the search space (readable animation)
    rel = []
    for i in range(len(feats)):
        m = [False] * len(feats)
        m[i] = True
        rel.append((feats[i], round(fitness(m), 3)))
    rel.sort(key=lambda t: -t[1])
    search = [f for f, _ in rel[:SEARCH_TOP]]
    feats = search
    X, Xtr, Xte = X[search], Xtr[search], Xte[search]
    importances = [{"feature": f, "importance": s} for f, s in rel[:SEARCH_TOP]]

    rng = np.random.default_rng(7)
    k = len(feats)
    pop = []
    for _ in range(POP):
        m = rng.random(k) < 0.5
        if not m.any():
            m[rng.integers(k)] = True
        pop.append(m)

    generations = []
    for g in range(GENS):
        fits = np.array([fitness(list(m)) for m in pop])
        order = np.argsort(-fits)
        pop = [pop[i] for i in order]
        fits = fits[order]
        generations.append({
            "habitats": [
                {"selected": [feats[i] for i in range(k) if pop[h][i]],
                 "fitness": round(float(fits[h]), 3)}
                for h in range(POP)
            ],
            "best_fitness": round(float(fits[0]), 3),
        })
        if g == GENS - 1:
            break
        rng_span = (fits.max() - fits.min()) or 1.0
        lam = 1 - (fits - fits.min()) / rng_span  # immigration (weak habitats absorb more)
        mu = (fits - fits.min()) / rng_span  # emigration (strong habitats share more)
        newpop = [pop[0].copy(), pop[1].copy()]  # elitism: keep best 2
        for h in range(2, POP):
            child = pop[h].copy()
            for bit in range(k):
                if rng.random() < lam[h]:
                    probs = mu / (mu.sum() or 1)
                    child[bit] = pop[int(rng.choice(POP, p=probs))][bit]
                if rng.random() < 0.06:
                    child[bit] = not child[bit]
            if not child.any():
                child[rng.integers(k)] = True
            newpop.append(child)
        pop = newpop

    best = pop[0]
    selected = [feats[i] for i in range(k) if best[i]]
    return FeatureSelectionTrace(
        target=target, task=task, features=feats, importances=importances,
        generations=generations, selected=selected,
        best_fitness=generations[-1]["best_fitness"],
        note="BBO treats each candidate feature-subset as a 'habitat', scored by how well a model does "
        "with just those features (its fitness). Strong habitats share features with weak ones "
        "(migration); random mutations try new subsets. Over generations it settles on a small, "
        "strong set — fewer features, similar accuracy.",
    )
