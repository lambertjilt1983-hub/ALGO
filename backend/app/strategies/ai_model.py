# ai_model.py
# Simple AI/ML model for trading signal prediction (demo)

import numpy as np
from sklearn.linear_model import LogisticRegression

class SimpleAIModel:
    def __init__(self):
        # initialise with a small dummy model; will be retrained when history is available.
        self.model = LogisticRegression()
        # flag to know whether model has been fitted
        self.fitted = False

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train or re-train the internal model.
        X : feature matrix (n_samples, n_features)
        y : binary labels (1=profitable, 0=loss/SL)
        """
        if len(X) == 0:
            return
        self.model.fit(X, y)
        self.fitted = True

    def train_from_history(self, history: list[dict]) -> None:
        """Build feature vectors from stored trade history and train model.

        Expected keys in each record: 'entry_price','exit_price','status',
        optionally any pre-computed features such as 'rsi','trend_strength'.
        """
        features = []
        labels = []
        for t in history:
            entry = float(t.get('entry_price') or t.get('price') or 0)
            exitp = float(t.get('exit_price') or entry)
            if entry <= 0:
                continue
            pnl = exitp - entry
            # label profitable trades as 1, others as 0
            labels.append(1 if pnl > 0 else 0)

            # example features: percent change, quality score, trend flags
            change_pct = (exitp - entry) / entry
            rsi = float(t.get('rsi') or 50)
            uptrend = 1 if t.get('trend_strength', 0) > 0.5 else 0
            features.append([change_pct, rsi, uptrend])
        if features:
            X = np.array(features)
            y = np.array(labels)
            self.train(X, y)

    def predict(self, features, probability: bool = False):
        """Return prediction for the given feature vector.

        If probability=True returns probability of label=1 (profitable).
        Otherwise returns 0/1.
        """
        if not self.fitted:
            # fallback to dummy behaviour: buy if change_pct > 0
            if probability:
                return 0.5
            return 1 if features[0] > 0 else 0
        if probability:
            return float(self.model.predict_proba([features])[0][1])
        return int(self.model.predict([features])[0])

# Singleton for app use
ai_model = SimpleAIModel()
