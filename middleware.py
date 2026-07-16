import logging
from typing import List
from datetime import datetime

import numpy as np
import pandas as pd
import torch
from fastapi import FastAPI, HTTPException

from api.schemas import PredictRequest, PredictResponse, HealthResponse
from api.middleware import LatencyLoggingMiddleware
from models.isolation_forest import IFModel
from models.prophet_model import ProphetModel
from models.lstm_autoencoder import LSTMAETrainer
from models.ensemble import EnsembleScorer
from features.engineer import FeatureEngineer
from features.store import FeatureStore

logger = logging.getLogger(__name__)

app = FastAPI(title="Anomaly Detection API")

# Add middleware
app.add_middleware(LatencyLoggingMiddleware)

# State variables (in-memory for simplicity per PRD Section 12)
models_loaded = []
if_model = None
pr_model = None
ls_model = None
ens_scorer = None
feature_engineer = None
feature_store = None

latest_timestamp = None
history = []
feature_history = []

@app.on_event("startup")
async def startup_event():
    global if_model, pr_model, ls_model, ens_scorer, feature_engineer, feature_store, models_loaded
    
    logger.info("Initializing models and feature store...")
    feature_store = FeatureStore()
    feature_engineer = FeatureEngineer()
    
    try:
        if_model = IFModel()
        if_model.load("isolation_forest.joblib")
        models_loaded.append("isolation_forest")
    except Exception as e:
        logger.error(f"Failed to load IFModel: {e}")
        
    try:
        pr_model = ProphetModel()
        pr_model.load("prophet_model.joblib")
        models_loaded.append("prophet")
    except Exception as e:
        logger.error(f"Failed to load ProphetModel: {e}")
        
    try:
        ls_model = LSTMAETrainer(n_features=7)
        ls_model.load("lstm_autoencoder.pt")
        models_loaded.append("lstm_ae")
    except Exception as e:
        logger.error(f"Failed to load LSTMAETrainer: {e}")
        
    ens_scorer = EnsembleScorer(if_weight=0.0, prophet_weight=1.0, lstm_weight=0.0)
    logger.info(f"Startup complete. Models loaded: {models_loaded}")


@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", models_loaded=models_loaded)


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    global latest_timestamp, history, feature_history
    
    if not (if_model and pr_model and ls_model):
        raise HTTPException(status_code=503, detail="Not all models are loaded.")
        
    # Check out-of-order timestamp (PRD Section 15 Edge Cases)
    is_out_of_order = False
    if latest_timestamp and request.timestamp < latest_timestamp:
        is_out_of_order = True
        logger.warning(f"Out of order timestamp received: {request.timestamp} < {latest_timestamp}. Processing statelessly.")
        
    # Feature Engineering (Avoid corrupting history if out of order)
    current_history = list(history)
    feats = feature_engineer.compute_features(current_history, request.value)
    
    if not is_out_of_order:
        latest_timestamp = request.timestamp
        history.append(request.value)
        # Prevent unbounded growth
        if len(history) > 1000:
            history = history[-1000:]
            
    if feats is None:
        # Warmup period (insufficient history)
        return PredictResponse(
            ensemble_score=0.0,
            is_anomaly=False,
            model_scores={"isolation_forest": 0.0, "prophet": 0.0, "lstm_ae": 0.0},
            threshold=0.0
        )
        
    feature_vector = [
        feats['rolling_mean'], feats['rolling_std'], feats['z_score'], 
        feats['lag_value'], feats['rate_of_change'], feats['iqr'], feats['fft_peak']
    ]
    
    # Update Feature Store
    feature_store.put("stream", request.timestamp.isoformat(), feats)
    
    # Manage feature history for LSTM sequence scoring
    temp_feature_history = list(feature_history)
    temp_feature_history.append(feature_vector)
    
    if not is_out_of_order:
        feature_history.append(feature_vector)
        if len(feature_history) > 60:
            feature_history = feature_history[-60:]
            
    # Score Isolation Forest
    if_score = if_model.score(np.array([feature_vector]))
    if isinstance(if_score, np.ndarray):
        if_score = float(if_score[0])
        
    # Score Prophet
    df_pr = pd.DataFrame([{"ds": request.timestamp.replace(tzinfo=None), "y": request.value}])
    pr_score = pr_model.score(df_pr)
    if isinstance(pr_score, np.ndarray):
        pr_score = float(pr_score[0])
        
    # Score LSTM
    # Inference strictly inside torch.no_grad() to guarantee p99 < 50ms
    X_ls = np.array(temp_feature_history)
    with torch.no_grad():
        ls_score = ls_model.score(X_ls)
        
    if ls_score is None:
        # Warmup period (insufficient history for LSTM)
        return PredictResponse(
            ensemble_score=0.0,
            is_anomaly=False,
            model_scores={"isolation_forest": 0.0, "prophet": 0.0, "lstm_ae": 0.0},
            threshold=0.0
        )
        
    if isinstance(ls_score, np.ndarray):
        ls_score = float(ls_score[-1])
        
    # Ensemble
    ens_score = ens_scorer.score(if_score, pr_score, ls_score)
    is_anomaly = bool(ens_scorer.is_anomaly(ens_score))
    threshold = float(ens_scorer.dynamic_threshold) if ens_scorer.dynamic_threshold is not None else 0.0
    
    return PredictResponse(
        ensemble_score=float(ens_score),
        is_anomaly=is_anomaly,
        model_scores={
            "isolation_forest": if_score,
            "prophet": pr_score,
            "lstm_ae": ls_score
        },
        threshold=threshold
    )
