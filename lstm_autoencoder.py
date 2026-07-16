import argparse
import logging
import joblib
import numpy as np
from typing import Union
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class IFModel:
    """
    Isolation Forest model for structural outlier detection.
    
    Exposes a consistent interface (.fit, .score) allowing the ensemble to treat
    all models interchangeably.
    """

    def __init__(self, contamination: float = 0.02, random_state: int = 42):
        """
        Initializes the Isolation Forest model.
        
        Args:
            contamination: The expected proportion of anomalies in the dataset.
            random_state: Random seed for reproducibility.
        """
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            contamination=self.contamination, 
            random_state=self.random_state,
            n_jobs=-1
        )
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray = None) -> None:
        """
        Trains the model unsupervised on engineered features.
        
        Args:
            X: A 2D numpy array of shape (n_samples, n_features) containing engineered features.
            y: A 1D numpy array of labels. If provided, anomalies (y==1) are filtered out.
        """
        if y is not None:
            if len(X) != len(y):
                raise ValueError("X and y must have the same length.")
            X = X[y == 0]
            
        logger.info(f"Fitting Isolation Forest on {X.shape[0]} samples with {X.shape[1]} features.")
        self.model.fit(X)
        self.is_fitted = True
        logger.info("Isolation Forest model successfully fitted.")

    def score(self, X: np.ndarray) -> Union[float, np.ndarray]:
        """
        Scores the input points.
        
        In sklearn's Isolation Forest, lower decision_function scores indicate anomalies.
        We invert this so that higher scores = more anomalous, maintaining consistency
        with the ensemble scorer where higher score implies an anomaly.
        
        Args:
            X: A 2D numpy array of shape (n_samples, n_features) containing engineered features.
            
        Returns:
            A float if a single sample is provided, or a 1D numpy array of scores.
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before scoring.")
            
        # Ensure 2D for single sample if passed a 1D array by mistake, though the 
        # API layer should handle shaping.
        if X.ndim == 1:
            X = X.reshape(1, -1)
            
        # decision_function returns positive for normal, negative for anomaly.
        # We invert it so higher = more anomalous.
        raw_scores = self.model.decision_function(X)
        anomaly_scores = -raw_scores
        
        if anomaly_scores.shape[0] == 1:
            return float(anomaly_scores[0])
        return anomaly_scores

    def save(self, path: str) -> None:
        """Saves the fitted model to disk."""
        if not self.is_fitted:
            raise ValueError("Cannot save an unfitted model.")
        joblib.dump(self.model, path)
        logger.info(f"Model saved to {path}")

    def load(self, path: str) -> None:
        """Loads a fitted model from disk."""
        self.model = joblib.load(path)
        self.is_fitted = True
        logger.info(f"Model loaded from {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Isolation Forest Anomaly Detection")
    parser.add_argument("--train", action="store_true", help="Train the Isolation Forest model")
    args = parser.parse_args()

    if args.train:
        # Import data and feature engineering components for a standalone training run
        from data.stream_sim import generate_synthetic_stream
        from features.engineer import FeatureEngineer
        
        logger.info("Starting standalone training run for Isolation Forest...")
        logger.info("Generating synthetic data stream (1000 points)...")
        stream = generate_synthetic_stream(num_points=1000, seed=42)
        engineer = FeatureEngineer()
        
        features_list = []
        history = []
        
        for point in stream:
            val = point['value']
            feats = engineer.compute_features(history, val)
            if feats is not None:
                # Convert dictionary to ordered feature vector
                feature_vector = [
                    feats['rolling_mean'],
                    feats['rolling_std'],
                    feats['z_score'],
                    feats['lag_value'],
                    feats['rate_of_change'],
                    feats['iqr'],
                    feats['fft_peak']
                ]
                features_list.append(feature_vector)
            history.append(val)
            
        X_train = np.array(features_list)
        logger.info(f"Extracted feature matrix shape: {X_train.shape}")
        
        # Inject synthetic anomalies to calculate metrics
        np.random.seed(42)
        y_test = np.zeros(len(X_train))
        y_test[np.random.choice(len(X_train), int(0.02 * len(X_train)), replace=False)] = 1
        X_train[y_test == 1] += 5.0
        
        model = IFModel(contamination=0.02)
        model.fit(X_train, y_test)
        
        # Evaluate to get metrics
        scores = model.score(X_train)
        preds = (scores > np.percentile(scores, 98)).astype(int)
        
        from sklearn.metrics import precision_score, recall_score, f1_score
        from tracking.mlflow_utils import log_model_metrics, start_experiment
        
        p = precision_score(y_test, preds, zero_division=0)
        r = recall_score(y_test, preds, zero_division=0)
        f = f1_score(y_test, preds, zero_division=0)
        
        start_experiment("anomaly_detection_pipeline")
        log_model_metrics(
            run_name="isolation_forest_standalone_train",
            model_type="isolation_forest",
            params={"contamination": 0.02, "n_estimators": 100},
            metrics={"precision": p, "recall": r, "f1_score": f}
        )
        
        # Save model to disk
        model_path = "isolation_forest.joblib"
        model.save(model_path)
        logger.info(f"Training complete. Artifact saved to {model_path}.")
