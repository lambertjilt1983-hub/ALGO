# ai_model.py
# Simple AI/ML model for trading signal prediction (demo)

import numpy as np
from sklearn.linear_model import LogisticRegression

class SimpleAIModel:
    def __init__(self):
        # For demo: train a dummy model on fake data
        X = np.array([
            [0.1, 50, 1],   # uptrend
            [-0.2, 30, 0],  # downtrend
            [0.05, 60, 1],  # weak uptrend
            [-0.1, 40, 0],  # weak downtrend
        ])
        y = np.array([1, 0, 1, 0])  # 1=buy, 0=sell
        self.model = LogisticRegression().fit(X, y)

    def predict(self, features):
        # features: [change_percent, rsi, uptrend (1/0)]
        return self.model.predict([features])[0]

# Singleton for app use
ai_model = SimpleAIModel()
