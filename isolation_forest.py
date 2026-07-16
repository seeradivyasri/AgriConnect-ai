import logging
import argparse
import numpy as np
import pandas as pd
from typing import Union, List, Tuple
from sklearn.metrics import f1_score

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class EnsembleScorer:
    """
    Consumes pre-computed .score() outputs from Isolation Forest, Prophet, and LSTM Autoencoder.
    Applies configurable, grid-searchable weights to produce a final ensemble anomaly score.
    Calculates a dynamic threshold based on recent historical scores.
    
    DISAGREEMENT BEHAVIOR (per PRD Section 15 Edge Cases):
    If one model strongly flags an anomaly (e.g., massive score) while the other two do not,
    the weighted sum effectively dampens the single extreme score. Unless that single score is 
    so extreme that a 1/3 weight still pushes it over the 99th percentile threshold of the 
    combined history, it will be suppressed. This acts as a majority-voting dampener against 
    single-model false positives, requiring either moderate agreement across multiple models 
    or overwhelming conviction from a single model to trigger an alert.
    """
    def __init__(self, 
                 if_weight: float = 0.333,
                 prophet_weight: float = 0.333,
                 lstm_weight: float = 0.334,
                 threshold_percentile: float = 99.0):
        self.weights = {
            'isolation_forest': if_weight,
            'prophet': prophet_weight,
            'lstm': lstm_weight
        }
        self.threshold_percentile = threshold_percentile
        self.dynamic_threshold = None
        self.historical_scores = []
        
        # We explicitly DO NOT instantiate or store models here.
        # This enforces the rule: EnsembleScorer must NEVER call internal fit/training logic.

    def score(self, 
              if_scores: Union[float, np.ndarray], 
              prophet_scores: Union[float, np.ndarray], 
              lstm_scores: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Takes raw anomaly scores from the three models, applies weights, and returns the final score.
        Updates internal history to calculate the adaptive threshold.
        """
        # Ensure inputs are numpy arrays for math
        is_scalar = isinstance(if_scores, (int, float))
        
        s_if = np.array(if_scores, dtype=float)
        s_pr = np.array(prophet_scores, dtype=float)
        s_ls = np.array(lstm_scores, dtype=float)
        
        final_scores = (s_if * self.weights['isolation_forest'] +
                        s_pr * self.weights['prophet'] +
                        s_ls * self.weights['lstm'])
                        
        # Maintain history for adaptive threshold (cap at 10,000 points)
        if final_scores.ndim == 0:  # scalar
            self.historical_scores.append(float(final_scores))
        else:
            self.historical_scores.extend(final_scores.tolist())
            
        if len(self.historical_scores) > 10000:
            self.historical_scores = self.historical_scores[-10000:]
            
        # Update adaptive threshold if we have enough warmup points
        if len(self.historical_scores) > 100:
            self.dynamic_threshold = np.percentile(self.historical_scores, self.threshold_percentile)
            
        return float(final_scores) if is_scalar else final_scores

    def is_anomaly(self, final_score: Union[float, np.ndarray]) -> Union[bool, np.ndarray]:
        """
        Produces a binary anomaly flag based on the dynamic threshold.
        """
        if self.dynamic_threshold is None:
            # Not enough history to declare anomalies reliably
            return False if isinstance(final_score, float) else np.zeros_like(final_score, dtype=bool)
            
        return final_score > self.dynamic_threshold


def tune_ensemble_weights(val_labels: np.ndarray, 
                          if_scores: np.ndarray, 
                          prophet_scores: np.ndarray, 
                          lstm_scores: np.ndarray) -> Tuple[float, float, float]:
    """
    Grid searches weights against validation-set F1.
    NEVER evaluate against test-set F1 here.
    """
    best_f1 = -1.0
    best_weights = (0.33, 0.33, 0.34)
    
    # Grid search: step by 0.1
    weights_grid = [x / 10.0 for x in range(11)]
    
    for w_if in weights_grid:
        for w_pr in weights_grid:
            w_ls = 1.0 - w_if - w_pr
            if w_ls < 0.0 or w_ls > 1.0:
                continue
                
            # Simulate ensemble
            final_scores = (if_scores * w_if + prophet_scores * w_pr + lstm_scores * w_ls)
            
            # Use 99th percentile of this specific combination as threshold
            threshold = np.percentile(final_scores, 99.0)
            preds = (final_scores > threshold).astype(int)
            
            # Note: We must handle cases where 99th percentile produces all 0s
            f1 = f1_score(val_labels, preds, zero_division=0)
            
            if f1 > best_f1:
                best_f1 = f1
                best_weights = (round(w_if, 2), round(w_pr, 2), round(w_ls, 2))
                
    logger.info(f"Best Validation F1: {best_f1:.4f} with weights (IF: {best_weights[0]}, Prophet: {best_weights[1]}, LSTM: {best_weights[2]})")
    return best_weights

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ensemble Scorer CLI")
    parser.add_argument("--tune", action="store_true", help="Grid search ensemble weights against validation F1.")
    args = parser.parse_args()
    
    if args.tune:
        # 1. Load data
        df = pd.read_csv("data/datasets/machine_temperature_system_failure.csv")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        n = len(df)
        train_end = int(n * 0.6)
        val_end = int(n * 0.8)
        
        # Inject anomalies into the validation set ONLY for tuning
        np.random.seed(42)
        y_val_full = np.zeros(n)
        val_indices = range(train_end, val_end)
        num_anomalies = int(len(val_indices) * 0.01)
        anomaly_indices = np.random.choice(val_indices, num_anomalies, replace=False)
        y_val_full[anomaly_indices] = 1
        
        # Inject into the signal
        df.loc[anomaly_indices, 'value'] += 1500.0
        
        from features.engineer import FeatureEngineer
        engineer = FeatureEngineer()
        history = []
        features_list = []
        for val in df['value'].values:
            feats = engineer.compute_features(history, val)
            if feats is not None:
                features_list.append([feats['rolling_mean'], feats['rolling_std'], feats['z_score'], 
                                      feats['lag_value'], feats['rate_of_change'], feats['iqr'], feats['fft_peak']])
            else:
                features_list.append([0]*7)
            history.append(val)
            
        X_all = np.array(features_list)
        
        X_val = X_all[train_end:val_end]
        df_val = df.iloc[train_end:val_end].rename(columns={'timestamp': 'ds', 'value': 'y'})
        y_val = y_val_full[train_end:val_end]
        
        # 2. Load Models
        from models.isolation_forest import IFModel
        from models.prophet_model import ProphetModel
        from models.lstm_autoencoder import LSTMAETrainer
        
        logger.info("Loading models...")
        if_model = IFModel()
        if_model.load("isolation_forest.joblib")
        
        pr_model = ProphetModel()
        pr_model.load("prophet_model.joblib")
        
        lstm_model = LSTMAETrainer(n_features=7)
        lstm_model.load("lstm_autoencoder.pt")
        
        # 3. Score validation set
        logger.info("Scoring validation set...")
        if_scores = if_model.score(X_val)
        pr_scores = pr_model.score(df_val)
        ls_scores = lstm_model.score(X_val)
        
        # LSTM drops the first (seq_len - 1) points during sequence creation.
        # We must truncate the other scores to match before ensembling.
        trunc = lstm_model.seq_len - 1
        if_scores_trunc = if_scores[trunc:]
        pr_scores_trunc = pr_scores[trunc:]
        y_val_trunc = y_val[trunc:]
        
        # 4. Tune
        logger.info("Tuning weights...")
        best_w = tune_ensemble_weights(y_val_trunc, if_scores_trunc, pr_scores_trunc, ls_scores)
        
        final_scores = (if_scores_trunc * best_w[0] + pr_scores_trunc * best_w[1] + ls_scores * best_w[2])
        threshold = np.percentile(final_scores, 99.0)
        preds = (final_scores > threshold).astype(int)
        
        from sklearn.metrics import precision_score, recall_score, f1_score
        final_f1 = f1_score(y_val_trunc, preds, zero_division=0)
        final_p = precision_score(y_val_trunc, preds, zero_division=0)
        final_r = recall_score(y_val_trunc, preds, zero_division=0)
        
        # 5. Log to MLflow
        from tracking.mlflow_utils import log_ensemble_tuning, start_experiment
        start_experiment("anomaly_detection_pipeline")
        log_ensemble_tuning(
            run_name=f"ensemble_tune_weights_{best_w[0]}_{best_w[1]}_{best_w[2]}",
            best_weights=best_w,
            best_f1=final_f1,
            precision=final_p,
            recall=final_r
        )
        print(f"Optimal weights: IF={best_w[0]}, Prophet={best_w[1]}, LSTM={best_w[2]}")
