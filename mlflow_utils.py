import mlflow
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Ensure mlruns directory is created locally per PRD Section 12 (local filesystem backend)
os.environ["MLFLOW_TRACKING_URI"] = "file:./mlruns"

def start_experiment(experiment_name: str):
    """Sets the MLflow experiment, creating it if it doesn't exist."""
    mlflow.set_experiment(experiment_name)

def log_model_metrics(run_name: str, model_type: str, params: Dict[str, Any], metrics: Dict[str, float]):
    """
    Logs hyperparameters and classification metrics (precision, recall, f1) for a model.
    The run_name is highly descriptive per CLAUDE.md Section 14.
    """
    with mlflow.start_run(run_name=run_name):
        mlflow.set_tag("model_type", model_type)
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)

def log_ensemble_tuning(run_name: str, best_weights: tuple, best_f1: float, precision: float = None, recall: float = None):
    """
    Logs the result of ensemble weight tuning.
    """
    if mlflow.active_run() is None:
        logger.warning("No active MLflow run. Call start_experiment() first.")
        return
        
    with mlflow.start_run(run_name=run_name, nested=True):
        mlflow.log_param("if_weight", best_weights[0])
        mlflow.log_param("prophet_weight", best_weights[1])
        mlflow.log_param("lstm_weight", best_weights[2])
        mlflow.log_metric("f1_score", best_f1)
        if precision is not None:
            mlflow.log_metric("precision", precision)
        if recall is not None:
            mlflow.log_metric("recall", recall)
        logger.info(f"Logged ensemble tuning results to MLflow: run_name={run_name}, f1={best_f1:.4f}")
