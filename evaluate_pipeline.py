import time
import numpy as np
import pandas as pd
import torch
from models.isolation_forest import IFModel
from models.prophet_model import ProphetModel
from models.lstm_autoencoder import LSTMAETrainer

def profile_models():
    # Load models
    if_model = IFModel()
    if_model.load("isolation_forest.joblib")
    
    pr_model = ProphetModel()
    pr_model.load("prophet_model.joblib")
    
    ls_model = LSTMAETrainer(n_features=7)
    ls_model.load("lstm_autoencoder.pt")
    
    # Dummy data
    feat_vector = [0.1] * 7
    df_pr = pd.DataFrame([{"ds": pd.Timestamp("2026-06-30T10:00:00"), "y": 12.5}])
    X_ls = np.random.randn(60, 7)
    
    # Warmup
    if_model.score(np.array([feat_vector]))
    pr_model.score(df_pr)
    with torch.no_grad():
        ls_model.score(X_ls)
        
    # Profile
    print("Profiling IF...")
    t0 = time.perf_counter()
    for _ in range(100):
        if_model.score(np.array([feat_vector]))
    print(f"IF: {(time.perf_counter()-t0)*10} ms per call")
    
    print("Profiling Prophet...")
    t0 = time.perf_counter()
    for _ in range(100):
        pr_model.score(df_pr)
    print(f"Prophet: {(time.perf_counter()-t0)*10} ms per call")
    
    print("Profiling LSTM...")
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(100):
            ls_model.score(X_ls)
    print(f"LSTM: {(time.perf_counter()-t0)*10} ms per call")

if __name__ == "__main__":
    profile_models()
