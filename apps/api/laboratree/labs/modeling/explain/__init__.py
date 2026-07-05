"""Model explainers — beginner-first "learn this model from zero" content, one per family.

For someone meeting a model name (XGBoost, logistic regression, k-NN…) for the first time, each
explainer gives: a plain one-liner + analogy, how it works step by step, every key formula with each
SYMBOL explained in plain words AND a worked example that plugs in real numbers, a tiny example table,
when to use it / what to watch out for, and reference articles to go deeper.

Curated (not LLM-generated) so it's accurate, consistent, and free. Families mirror the viz registry
(`labs/modeling/viz`) and the frontend `modelKind()` map, so every registered model resolves to one.
"""

from __future__ import annotations

from typing import Any


def _m(name: str, formula: str, plain: str, symbols: list[tuple[str, str]], worked: str) -> dict:
    return {
        "name": name, "formula": formula, "plain": plain,
        "symbols": [{"sym": s, "means": mng} for s, mng in symbols],
        "worked_example": worked,
    }


EXPLAINERS: dict[str, dict[str, Any]] = {
    "trees": {
        "title": "Decision trees & gradient boosting (XGBoost)",
        "one_liner": "A decision tree asks a chain of yes/no questions about the features to reach an "
        "answer. Boosting (XGBoost, LightGBM, CatBoost) stacks many small trees, each one fixing the "
        "mistakes the previous trees still make, and adds up their answers.",
        "analogy": "One tree is like a doctor's flowchart: 'Is blood pressure > 140? → yes → is age > "
        "50? → …'. Boosting is like a panel of specialists where each next specialist only focuses on "
        "the cases the others got wrong, and the final diagnosis is a weighted vote.",
        "how_it_works": [
            "A single tree repeatedly splits the data on the feature+threshold that best separates the "
            "outcomes (measured by how much it reduces 'impurity' — how mixed the two sides are).",
            "Boosting starts from a constant baseline guess, then fits a small tree to the RESIDUALS "
            "(what's still wrong), scales it by a learning rate, and adds it on.",
            "It repeats for N trees. Each tree is shallow (depth 2–6) so no single tree overfits; the "
            "ensemble gets its power from adding many weak corrections.",
            "To predict, a row walks down every tree to a leaf, and the leaf scores are summed (then "
            "passed through a sigmoid for a probability in classification).",
        ],
        "math": [
            _m("Ensemble prediction", "ŷ = base + η·(f₁(x) + f₂(x) + … + f_N(x))",
               "The prediction is the starting guess plus a shrunken sum of what each tree adds.",
               [("ŷ", "the model's output score for row x"), ("base", "the starting guess (e.g. the "
                "average log-odds)"), ("η", "learning rate — how much of each tree we trust (0–1)"),
                ("f_k(x)", "the score tree k gives to row x"), ("N", "number of boosting trees")],
               "base = 0.0, η = 1.0, and 3 trees score f₁ = −3.7, f₂ = −1.1, f₃ = −1.0 → "
               "ŷ = 0 + (−3.7 − 1.1 − 1.0) = −5.8"),
            _m("Turn the score into a probability", "p = 1 / (1 + e^(−ŷ))",
               "The sigmoid squeezes any score into a 0–1 probability. Big negative → near 0; big "
               "positive → near 1.",
               [("p", "probability of the positive class"), ("ŷ", "the summed score above"),
                ("e", "Euler's number ≈ 2.718")],
               "ŷ = −5.8 → p = 1/(1 + e^5.8) = 1/(1 + 330) ≈ 0.003, i.e. ~0.3% chance of the positive "
               "class → predict the negative class."),
            _m("How a split is chosen (information gain)", "gain = impurity(parent) − Σ (nᵢ/n)·impurity(childᵢ)",
               "A split is good if the two child groups are each 'purer' (more one-class) than the "
               "parent. Gain measures how much cleaner the split makes things.",
               [("impurity", "how mixed a group is — 0 means all one class"), ("n", "rows in the "
                "parent"), ("nᵢ", "rows going to child i")],
               "Parent impurity 0.50; a split sends 30 rows left (impurity 0.10) and 30 right "
               "(impurity 0.15): gain = 0.50 − (30/60·0.10 + 30/60·0.15) = 0.50 − 0.125 = 0.375."),
        ],
        "example_table": {
            "caption": "3 patients walking through a tiny kidney-disease tree",
            "columns": ["age", "blood_pressure", "→ leaf score", "→ p(disease)"],
            "rows": [["62", "150", "−5.8", "0.003 → no"], ["48", "95", "+2.1", "0.89 → yes"],
                     ["55", "130", "−0.4", "0.40 → no"]],
        },
        "when_to_use": "The go-to for tabular data (rows & columns) — handles mixed feature types, "
        "non-linear patterns, and interactions with little tuning. Usually the strongest baseline on "
        "structured data.",
        "watch_out_for": [
            "Can overfit if trees are too deep or there are too many — keep depth small and use a low "
            "learning rate with more trees.",
            "Not naturally interpretable as one rule; use feature importance / SHAP to explain it.",
        ],
        "references": [
            {"title": "XGBoost docs — 'Introduction to Boosted Trees'",
             "url": "https://xgboost.readthedocs.io/en/stable/tutorials/model.html"},
            {"title": "StatQuest: Gradient Boost, clearly explained (video)",
             "url": "https://www.youtube.com/watch?v=3CC4N4z3GJc"},
            {"title": "scikit-learn: Decision Trees",
             "url": "https://scikit-learn.org/stable/modules/tree.html"},
        ],
    },
    "linear": {
        "title": "Linear & logistic regression",
        "one_liner": "Give every feature a weight, multiply-and-add them into a single score. Linear "
        "regression uses that score directly as a number; logistic regression squeezes it through a "
        "sigmoid to get a 0–1 probability for a yes/no outcome.",
        "analogy": "Like a credit-score formula: +5 points per year of history, −20 for a missed "
        "payment… add them up to a total, then read off the decision.",
        "how_it_works": [
            "Training finds the weights that make the summed score best match the known answers "
            "(least-squares for linear; maximum-likelihood for logistic).",
            "A bigger absolute weight = that feature matters more; the sign says which way it pushes.",
            "For a new row, multiply each feature by its weight, add the intercept, and read the score "
            "(or sigmoid it into a probability).",
        ],
        "math": [
            _m("The score", "z = b + w₁x₁ + w₂x₂ + … + w_kx_k",
               "Each feature value times its learned weight, all added up, plus a baseline intercept.",
               [("z", "the raw score"), ("b", "intercept (the score when all features are 0)"),
                ("w_j", "weight learned for feature j"), ("x_j", "value of feature j for this row")],
               "b = −4.0, weights: age 0.05, bp 0.02; a row age=60, bp=150 → "
               "z = −4.0 + 0.05·60 + 0.02·150 = −4.0 + 3.0 + 3.0 = 2.0"),
            _m("Sigmoid → probability (logistic)", "p = 1 / (1 + e^(−z))",
               "Turns the score into a probability between 0 and 1.",
               [("p", "probability of the positive class"), ("z", "the score above")],
               "z = 2.0 → p = 1/(1 + e^−2) = 1/(1 + 0.135) ≈ 0.88 → 88% likely positive."),
            _m("Odds ratio (reading a logistic weight)", "OR = e^(w_j)",
               "Exponentiating a weight tells you how the odds multiply for a one-unit increase in "
               "that feature — the way epidemiology/econometrics papers report results.",
               [("OR", "odds ratio"), ("w_j", "the feature's weight")],
               "w = 0.05 for age → OR = e^0.05 ≈ 1.05: each extra year multiplies the odds by ~1.05 "
               "(a 5% increase)."),
        ],
        "example_table": {
            "caption": "Same weights applied to three rows",
            "columns": ["age", "bp", "z = −4 + .05·age + .02·bp", "p = σ(z)"],
            "rows": [["60", "150", "2.0", "0.88 → yes"], ["40", "90", "−0.2", "0.45 → no"],
                     ["30", "80", "−0.9", "0.29 → no"]],
        },
        "when_to_use": "When you want a simple, fast, INTERPRETABLE model and the relationship is "
        "roughly linear. The default in economics/medicine because each weight has a clear meaning.",
        "watch_out_for": [
            "Assumes a (mostly) linear relationship — misses complex interactions a tree would catch.",
            "Sensitive to feature scale; standardizing features makes weights comparable.",
        ],
        "references": [
            {"title": "scikit-learn: Logistic Regression",
             "url": "https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression"},
            {"title": "StatQuest: Logistic Regression, clearly explained (video)",
             "url": "https://www.youtube.com/watch?v=yIYKR4sgzI8"},
        ],
    },
    "nn": {
        "title": "Neural networks (MLP / deep learning)",
        "one_liner": "Stacked layers of simple units. Each unit takes a weighted mix of its inputs, "
        "passes it through a squashing function, and hands it on — letting the network learn curved, "
        "layered patterns a single formula can't.",
        "analogy": "Like an assembly line: the first station combines raw features into rough concepts "
        "('is this shape roundish?'), the next combines those into richer ones, until the last station "
        "reads off the answer.",
        "how_it_works": [
            "Each hidden unit computes weighted-sum → activation (tanh/ReLU), producing a new feature.",
            "Layers stack these, so later units build on the concepts earlier units found.",
            "Training runs the data forward, measures the error, and uses back-propagation + gradient "
            "descent to nudge every weight a little to reduce the error — repeated over many epochs.",
        ],
        "math": [
            _m("One hidden unit", "h = φ(b + Σⱼ wⱼxⱼ)",
               "Weighted sum of inputs, plus bias, passed through an activation function φ.",
               [("h", "the unit's output"), ("φ", "activation (tanh, ReLU, or sigmoid)"),
                ("wⱼ", "weight on input j"), ("xⱼ", "input j"), ("b", "bias")],
               "Inputs x = [1.0, −2.0], weights [0.5, 0.5], b = 0, tanh: "
               "z = 0.5·1.0 + 0.5·(−2.0) = −0.5 → h = tanh(−0.5) ≈ −0.46"),
            _m("Gradient-descent update", "w ← w − α·∂L/∂w",
               "Move each weight a small step DOWNHILL on the error surface. Do this repeatedly and "
               "the loss 'rolls downhill' to a good fit.",
               [("w", "a weight"), ("α", "learning rate (step size)"), ("∂L/∂w", "slope of the loss "
                "with respect to that weight")],
               "w = 0.50, α = 0.1, slope ∂L/∂w = +0.8 → w ← 0.50 − 0.1·0.8 = 0.42 (nudged down "
               "because increasing it would raise the error)."),
        ],
        "example_table": {
            "caption": "One demo row's output drifting toward the truth as training proceeds",
            "columns": ["epoch", "training loss", "output for demo row (truth = 1)"],
            "rows": [["1", "0.69", "0.52"], ["20", "0.31", "0.78"], ["150", "0.12", "0.94"]],
        },
        "when_to_use": "When patterns are complex/non-linear and there's enough data — especially "
        "images, text, and sequences. On small tabular data, boosted trees usually beat an MLP.",
        "watch_out_for": [
            "Data-hungry and easy to overfit; needs standardized inputs and often regularization.",
            "A 'black box' — harder to explain than a tree or a linear model.",
        ],
        "references": [
            {"title": "3Blue1Brown: But what is a neural network? (video)",
             "url": "https://www.youtube.com/watch?v=aircAruvnKk"},
            {"title": "scikit-learn: Neural network models (MLP)",
             "url": "https://scikit-learn.org/stable/modules/neural_networks_supervised.html"},
        ],
    },
    "knn": {
        "title": "k-Nearest Neighbours (k-NN)",
        "one_liner": "No training formula at all — it just remembers every example. To predict a new "
        "row it finds the k most similar remembered rows and lets them vote (or averages them).",
        "analogy": "Ask your k closest neighbours what they'd do and go with the majority — similarity "
        "IS the model.",
        "how_it_works": [
            "Standardize features so no single scale dominates the 'distance'.",
            "For a new row, compute its distance to every training row, pick the k smallest.",
            "Classification: majority class among the k wins. Regression: average their values.",
        ],
        "math": [
            _m("Euclidean distance", "d(a, b) = √(Σⱼ (aⱼ − bⱼ)²)",
               "How far apart two rows are — square the difference on each feature, add, square-root.",
               [("d", "distance between rows a and b"), ("aⱼ, bⱼ", "feature j of each row")],
               "a = (age 60, bp 150), b = (age 58, bp 145): "
               "d = √((60−58)² + (150−145)²) = √(4 + 25) = √29 ≈ 5.39"),
            _m("Majority vote", "ŷ = mode(labels of the k nearest)",
               "The predicted class is whichever label appears most among the k neighbours.",
               [("k", "how many neighbours vote"), ("mode", "most frequent value")],
               "k = 5 nearest labels = [yes, yes, no, yes, no] → 3 'yes' vs 2 'no' → predict 'yes'."),
        ],
        "example_table": {
            "caption": "5 nearest neighbours of a new patient",
            "columns": ["neighbour", "distance", "label"],
            "rows": [["#1", "0.8", "yes"], ["#2", "1.1", "yes"], ["#3", "1.4", "no"],
                     ["#4", "1.6", "yes"], ["#5", "1.9", "no"]],
        },
        "when_to_use": "A simple, strong baseline when similar rows tend to share an outcome and the "
        "dataset isn't huge. Great for intuition.",
        "watch_out_for": [
            "Slow at prediction time on big data (compares to every row).",
            "Sensitive to feature scaling and to irrelevant features; pick k by validation.",
        ],
        "references": [
            {"title": "scikit-learn: Nearest Neighbors",
             "url": "https://scikit-learn.org/stable/modules/neighbors.html"},
        ],
    },
    "timeseries": {
        "title": "Time-series models (ARIMA / autoregression)",
        "one_liner": "Predict the next value from the recent past of the same series: tomorrow ≈ a "
        "weighted blend of today, yesterday, and so on.",
        "analogy": "Like guessing tomorrow's temperature from the last few days — recent days matter "
        "most, and you learn how much to weight each.",
        "how_it_works": [
            "Line up each value against its own previous p values (lags).",
            "Fit weights (φ) so the blend of past values best predicts the next one.",
            "Forecast by sliding that equation forward one step at a time.",
        ],
        "math": [
            _m("AR(p) model", "yₜ = c + φ₁yₜ₋₁ + φ₂yₜ₋₂ + … + φₚyₜ₋ₚ + εₜ",
               "The value now is a constant plus weighted recent values, plus unpredictable noise.",
               [("yₜ", "value at time t"), ("c", "constant"), ("φᵢ", "weight on the value i steps "
                "back"), ("p", "how many past steps used"), ("εₜ", "random shock")],
               "c = 2, φ₁ = 0.6, φ₂ = 0.3; yesterday = 10, day-before = 8 → "
               "ŷₜ = 2 + 0.6·10 + 0.3·8 = 2 + 6 + 2.4 = 10.4"),
        ],
        "example_table": {
            "caption": "One-step-ahead forecasts from AR(2)",
            "columns": ["t−2", "t−1", "→ forecast tₜ", "actual"],
            "rows": [["8", "10", "10.4", "10.1"], ["10", "10.1", "10.5", "10.7"]],
        },
        "when_to_use": "When the data is ordered in time and the near past predicts the near future "
        "(sales, prices, demand). Add differencing (the 'I' in ARIMA) for trends.",
        "watch_out_for": [
            "Assumes the pattern is stable over time; structural breaks fool it.",
            "Needs enough history; watch for seasonality (use SARIMA).",
        ],
        "references": [
            {"title": "Hyndman & Athanasopoulos, 'Forecasting: Principles and Practice' (free book)",
             "url": "https://otexts.com/fpp3/"},
        ],
    },
    "clustering": {
        "title": "Clustering (k-means)",
        "one_liner": "There's no answer column — it discovers natural groups by putting down k centre "
        "points, assigning each row to its nearest centre, then moving the centres to the middle of "
        "their rows, and repeating until stable.",
        "analogy": "Drop k flags on a map, everyone joins the nearest flag, then each flag moves to "
        "the middle of its crowd — repeat until nobody switches.",
        "how_it_works": [
            "Pick k and place k centres.",
            "Assign every row to the nearest centre (Euclidean distance).",
            "Move each centre to the average of its assigned rows.",
            "Repeat assign→move until the centres stop moving (inertia stops falling).",
        ],
        "math": [
            _m("Objective (inertia)", "minimize Σ_points ‖xᵢ − μ_c(i)‖²",
               "Make every row as close as possible to its own cluster's centre — the total squared "
               "distance is what k-means drives down.",
               [("xᵢ", "a row"), ("μ_c(i)", "the centre of the cluster row i belongs to"),
                ("‖·‖²", "squared distance")],
               "A row at (2, 2) assigned to centre (3, 1): squared distance = (2−3)² + (2−1)² = "
               "1 + 1 = 2. Inertia sums this over all rows."),
        ],
        "example_table": {
            "caption": "A new row's distance to 3 centres → joins the nearest",
            "columns": ["cluster", "distance", "assigned?"],
            "rows": [["1", "2.0", "✓ nearest"], ["2", "3.5", ""], ["3", "5.1", ""]],
        },
        "when_to_use": "Exploration / segmentation when you have no labels and want to find structure "
        "(customer segments, groupings).",
        "watch_out_for": [
            "You must choose k; the 'elbow' of inertia vs k helps.",
            "Assumes roughly round, similar-size clusters; standardize features first.",
        ],
        "references": [
            {"title": "scikit-learn: Clustering (k-means)",
             "url": "https://scikit-learn.org/stable/modules/clustering.html#k-means"},
        ],
    },
    "anomaly": {
        "title": "Anomaly detection (Isolation Forest)",
        "one_liner": "Learns what 'usual' looks like and flags the unusual. Isolation Forest slices "
        "the data with random cuts — odd rows get isolated in very few cuts, typical rows need many.",
        "analogy": "A weird data point is like a house far from town — a few random fences already "
        "cut it off from everyone else.",
        "how_it_works": [
            "Build many trees of random split points.",
            "Measure how few cuts it takes to isolate each row.",
            "Few cuts → high anomaly score; rows above a threshold are flagged.",
        ],
        "math": [
            _m("Anomaly score", "s(x) = 2^(−E[h(x)] / c(n))",
               "Turns 'average number of cuts to isolate x' into a 0–1 score; closer to 1 = more "
               "anomalous.",
               [("E[h(x)]", "average path length (cuts) to isolate x across trees"), ("c(n)", "a "
                "normalizing constant for n rows"), ("s", "anomaly score")],
               "If a row is isolated in far fewer cuts than average, E[h(x)] is small, so the exponent "
               "is near 0 and s ≈ 1 → flagged as an anomaly."),
        ],
        "example_table": {
            "caption": "Scores for three rows (threshold ≈ 0.6)",
            "columns": ["row", "cuts to isolate", "score", "verdict"],
            "rows": [["A", "3", "0.72", "anomaly"], ["B", "9", "0.41", "normal"],
                     ["C", "11", "0.35", "normal"]],
        },
        "when_to_use": "Fraud, defect, and outlier detection — when anomalies are rare and you don't "
        "have labels for them.",
        "watch_out_for": [
            "You set 'contamination' (expected anomaly fraction) — too high flags normal rows.",
            "Very high-dimensional data can dilute the signal.",
        ],
        "references": [
            {"title": "scikit-learn: Isolation Forest",
             "url": "https://scikit-learn.org/stable/modules/outlier_detection.html#isolation-forest"},
        ],
    },
}


_FALLBACK = {
    "title": "This model",
    "one_liner": "A model learns a pattern from labelled examples (features → outcome), then applies "
    "that pattern to new rows to predict their outcome.",
    "analogy": "Like studying past exam papers to answer a new question you haven't seen.",
    "how_it_works": [
        "Split the data into train and test so we can check honestly.",
        "Fit the model on the training rows.",
        "Predict on held-out rows and score how close the predictions are to the truth.",
    ],
    "math": [],
    "example_table": None,
    "when_to_use": "See the staged animation below to watch this model learn and predict on the "
    "actual data.",
    "watch_out_for": ["Always compare against a simple baseline before trusting a complex model."],
    "references": [
        {"title": "scikit-learn: Supervised learning",
         "url": "https://scikit-learn.org/stable/supervised_learning.html"},
    ],
}


def explainer_for(family: str) -> dict[str, Any]:
    """Return the beginner explainer for a model family (falls back to a generic one)."""
    data = dict(EXPLAINERS.get(family, _FALLBACK))
    data["family"] = family
    return data


def families() -> list[str]:
    return sorted(EXPLAINERS)


__all__ = ["EXPLAINERS", "explainer_for", "families"]
