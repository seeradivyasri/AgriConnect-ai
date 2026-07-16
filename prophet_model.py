import argparse
import logging
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from typing import Union

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class LSTMAutoencoder(nn.Module):
    """
    PyTorch implementation of an LSTM-based Autoencoder.
    Learns to reconstruct sequences of normal data.
    """
    def __init__(self, n_features: int, hidden_dim: int = 16):
        super(LSTMAutoencoder, self).__init__()
        self.hidden_dim = hidden_dim
        # batch_first=True means inputs are (batch, seq_len, features)
        self.encoder = nn.LSTM(n_features, hidden_dim, batch_first=True)
        self.decoder = nn.LSTM(hidden_dim, n_features, batch_first=True)
        
    def forward(self, x):
        # x shape: (batch, seq_len, n_features)
        _, (hidden, _) = self.encoder(x)
        # hidden is (1, batch, hidden_dim) since it's a 1-layer unidirectional LSTM
        
        # Repeat the final hidden state to form the sequence for the decoder
        hidden = hidden[-1].unsqueeze(1).repeat(1, x.size(1), 1)
        # hidden shape: (batch, seq_len, hidden_dim)
        
        out, _ = self.decoder(hidden)
        # out shape: (batch, seq_len, n_features)
        return out


class LSTMAETrainer:
    """
    Trainer wrapper exposing the consistent (.fit, .score) interface.
    Trains on sliding windows and scores based on reconstruction error.
    """
    def __init__(self, n_features: int, seq_len: int = 60, epochs: int = 20, hidden_dim: int = 16, batch_size: int = 32):
        self.seq_len = seq_len
        self.epochs = epochs
        self.batch_size = batch_size
        self.n_features = n_features
        self.model = LSTMAutoencoder(n_features=n_features, hidden_dim=hidden_dim)
        self.criterion = nn.MSELoss(reduction='none')
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)
        self.is_fitted = False
        self.threshold = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    def _create_windows(self, X: np.ndarray) -> np.ndarray:
        """
        Converts a 2D array (N, features) to a 3D array of sliding windows (N - seq_len + 1, seq_len, features).
        Handles Edge Case (Section 15): If length < seq_len, pads the sequence with zeros.
        """
        if len(X) < self.seq_len:
            pad_len = self.seq_len - len(X)
            X = np.pad(X, ((pad_len, 0), (0, 0)), mode='constant')
            
        windows = []
        for i in range(len(X) - self.seq_len + 1):
            windows.append(X[i:i + self.seq_len])
        return np.array(windows)

    def fit(self, X: np.ndarray, y: np.ndarray = None) -> None:
        """
        Trains the LSTM Autoencoder unsupervised on normal data for 20 epochs.
        Sets the reconstruction-error threshold at the 95th percentile of a validation set.
        
        Args:
            X: A 2D numpy array of engineered features.
            y: A 1D numpy array of labels. If provided, anomalies (y==1) are filtered out.
        """
        logger.info(f"Fitting LSTM Autoencoder for {self.epochs} epochs on device: {self.device}...")
        self.model.train()
        
        # Filter anomalies if labels are provided
        if y is not None:
            if len(X) != len(y):
                raise ValueError("X and y must have the same length.")
            X = X[y == 0]
            logger.info(f"Filtered out anomalies. Training on {len(X)} normal samples.")
            
        # Split into train and validation for threshold calibration
        split_idx = int(len(X) * 0.8)
        X_train = X[:split_idx]
        X_val = X[split_idx:]
        
        # Ensure 3D sliding windows
        if X_train.ndim == 2:
            X_win = self._create_windows(X_train)
        elif X_train.ndim == 3:
            X_win = X_train
        else:
            raise ValueError("X must be 2D or 3D array.")
            
        dataset = TensorDataset(torch.FloatTensor(X_win))
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        for epoch in range(self.epochs):
            total_loss = 0
            for batch in dataloader:
                batch_x = batch[0].to(self.device)
                
                self.optimizer.zero_grad()
                reconstructed = self.model(batch_x)
                
                loss = self.criterion(reconstructed, batch_x).mean()
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
                
            if (epoch + 1) % 5 == 0 or epoch == 0:
                logger.info(f"Epoch {epoch+1}/{self.epochs}, Loss: {total_loss/len(dataloader):.4f}")
                
        self.is_fitted = True
        
        logger.info("Calculating 95th percentile reconstruction error threshold on validation set...")
        if X_val.ndim == 2:
            X_val_win = self._create_windows(X_val)
        elif X_val.ndim == 3:
            X_val_win = X_val
            
        val_dataset = TensorDataset(torch.FloatTensor(X_val_win))
        
        # MUST run in no_grad even during threshold calculation to save memory
        with torch.no_grad():
            self.model.eval()
            all_errors = []
            eval_loader = DataLoader(val_dataset, batch_size=self.batch_size, shuffle=False)
            
            for batch in eval_loader:
                batch_x = batch[0].to(self.device)
                reconstructed = self.model(batch_x)
                
                # The anomaly score is the MSE reconstruction error of the *last* point in the sequence
                errors = self.criterion(reconstructed[:, -1, :], batch_x[:, -1, :]).mean(dim=1).cpu().numpy()
                all_errors.extend(errors)
        
        self.threshold = float(np.percentile(all_errors, 95))
        logger.info(f"LSTM threshold successfully set to {self.threshold:.4f} (95th percentile).")

    def score(self, X: np.ndarray) -> Union[float, np.ndarray]:
        """
        Scores input points based on reconstruction error.
        
        CRITICAL RULE (CLAUDE.md Section 17): The inference/scoring path must run 
        entirely inside torch.no_grad() to prevent latency benchmark failures (p99 > 50ms).
        
        Args:
            X: A 2D or 3D numpy array of engineered features.
            
        Returns:
            A float score for a single prediction, or a 1D array of scores.
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before scoring.")
            
        if len(X) < self.seq_len:
            return None
            
        if X.ndim == 2:
            X_win = self._create_windows(X)
        elif X.ndim == 3:
            X_win = X
        else:
            raise ValueError("X must be 2D or 3D array.")
            
        all_errors = []
        self.model.eval()
        
        # === CRITICAL PATH FOR LOW LATENCY ===
        with torch.no_grad():
            batch_x = torch.FloatTensor(X_win).to(self.device)
            reconstructed = self.model(batch_x)
            
            # Reconstruction error of the final point in the window
            errors = self.criterion(reconstructed[:, -1, :], batch_x[:, -1, :]).mean(dim=1).cpu().numpy()
            all_errors.extend(errors)
                
        scores = np.array(all_errors)
        
        if len(scores) == 1:
            return float(scores[0])
        return scores
        
    def save(self, path: str) -> None:
        """Saves the PyTorch model state and threshold."""
        if not self.is_fitted:
            raise ValueError("Cannot save an unfitted model.")
        state = {
            'model_state': self.model.state_dict(),
            'threshold': self.threshold,
            'n_features': self.n_features,
            'seq_len': self.seq_len,
            'hidden_dim': self.model.hidden_dim
        }
        torch.save(state, path)
        logger.info(f"PyTorch LSTM model saved to {path}")

    def load(self, path: str) -> None:
        """Loads the PyTorch model state and threshold."""
        state = torch.load(path, map_location=self.device)
        self.n_features = state['n_features']
        self.seq_len = state['seq_len']
        self.model = LSTMAutoencoder(n_features=self.n_features, hidden_dim=state['hidden_dim'])
        self.model.load_state_dict(state['model_state'])
        self.model.to(self.device)
        self.threshold = state['threshold']
        self.is_fitted = True
        logger.info(f"PyTorch LSTM model loaded from {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LSTM Autoencoder Anomaly Detection")
    parser.add_argument("--train", action="store_true", help="Train the LSTM Autoencoder model")
    args = parser.parse_args()

    if args.train:
        from data.stream_sim import generate_synthetic_stream
        from features.engineer import FeatureEngineer
        
        logger.info("Starting standalone training run for LSTM Autoencoder...")
        logger.info("Generating synthetic data stream (1000 points)...")
        stream = generate_synthetic_stream(num_points=1000, seed=42)
        engineer = FeatureEngineer()
        
        features_list = []
        history = []
        
        for point in stream:
            val = point['value']
            feats = engineer.compute_features(history, val)
            if feats is not None:
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
        
        # Hardcoding n_features to 7 based on the engineered list
        model = LSTMAETrainer(n_features=7, epochs=20)
        # Pass labels to fit so it can filter out the anomalies before training
        model.fit(X_train, y_test)
        
        # Evaluate to get metrics
        # For batch scoring, the LSTM will drop the first seq_len - 1 points.
        scores = model.score(X_train)
        
        preds = (scores > model.threshold).astype(int)
        
        from sklearn.metrics import precision_score, recall_score, f1_score
        from tracking.mlflow_utils import log_model_metrics, start_experiment
        
        trunc = model.seq_len - 1
        y_test_trunc = y_test[trunc:]
        
        p = precision_score(y_test_trunc, preds, zero_division=0)
        r = recall_score(y_test_trunc, preds, zero_division=0)
        f = f1_score(y_test_trunc, preds, zero_division=0)
        
        start_experiment("anomaly_detection_pipeline")
        log_model_metrics(
            run_name="lstm_standalone_train",
            model_type="lstm_autoencoder",
            params={"n_features": 7, "epochs": 20},
            metrics={"precision": p, "recall": r, "f1_score": f}
        )
        
        # Save model to disk
        model_path = "lstm_autoencoder.pt"
        model.save(model_path)
        logger.info(f"Training complete. Artifact saved to {model_path}.")
