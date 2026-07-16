import numpy as np
from typing import List, Optional, Dict, Any

class FeatureEngineer:
    """
    Engineers time-series features over a rolling window.
    
    Computes rolling mean, rolling standard deviation, z-score, lag features,
    rate-of-change, interquartile range (IQR), and Fast Fourier Transform (FFT) peak.
    """

    def __init__(self, window_size: int = 60, lag: int = 1):
        """
        Initializes the FeatureEngineer with a specific window size and lag.
        
        Args:
            window_size: The number of historical points required to compute features.
            lag: The lag step for computing rate of change and lag features.
        """
        self.window_size = window_size
        self.lag = lag

    def compute_features(self, history: List[float], current_value: float) -> Optional[Dict[str, float]]:
        """
        Computes all engineered features for the current point given historical values.
        
        If the length of history is less than the required window_size minus one, 
        returns None to indicate insufficient warm-up period.
        
        Args:
            history: A list of recent historical values, excluding the current value.
            current_value: The newest data point value.
            
        Returns:
            A dictionary containing the computed features, or None if warm-up is incomplete.
        """
        if len(history) < self.window_size - 1:
            return None
            
        # Use only the most recent points to form the full window
        window = history[-(self.window_size - 1):] + [current_value]
        
        features = {}
        features['rolling_mean'] = self._compute_mean(window)
        features['rolling_std'] = self._compute_std(window)
        features['z_score'] = self._compute_z_score(current_value, features['rolling_mean'], features['rolling_std'])
        features['lag_value'] = self._compute_lag(window)
        features['rate_of_change'] = self._compute_roc(current_value, features['lag_value'])
        features['iqr'] = self._compute_iqr(window)
        features['fft_peak'] = self._compute_fft_peak(window)
        
        return features

    def _compute_mean(self, window: List[float]) -> float:
        """
        Computes the mean of the window.
        
        Args:
            window: The rolling window of historical values plus the current value.
            
        Returns:
            The mean as a float.
        """
        return float(np.mean(window))

    def _compute_std(self, window: List[float]) -> float:
        """
        Computes the standard deviation of the window.
        
        Args:
            window: The rolling window of historical values plus the current value.
            
        Returns:
            The standard deviation as a float.
        """
        return float(np.std(window))

    def _compute_z_score(self, value: float, mean: float, std: float) -> float:
        """
        Computes the z-score of the value relative to the window.
        
        Guards against division-by-zero for flat/constant signals, returning 0.0 instead.
        
        Args:
            value: The current value.
            mean: The rolling mean.
            std: The rolling standard deviation.
            
        Returns:
            The z-score as a float.
        """
        if std == 0.0:
            return 0.0
        return (value - mean) / std

    def _compute_lag(self, window: List[float]) -> float:
        """
        Computes the lag feature from the window.
        
        Args:
            window: The rolling window of historical values plus the current value.
            
        Returns:
            The value at the specified lag index, or the oldest available point.
        """
        lag_idx = -(self.lag + 1)
        if len(window) >= abs(lag_idx):
            return float(window[lag_idx])
        return float(window[0])

    def _compute_roc(self, value: float, lag_value: float) -> float:
        """
        Computes the rate of change between the current value and lag value.
        
        Guards against division by zero.
        
        Args:
            value: The current value.
            lag_value: The value at the lag index.
            
        Returns:
            The rate of change as a float.
        """
        if lag_value == 0.0:
            return 0.0
        return (value - lag_value) / abs(lag_value)

    def _compute_iqr(self, window: List[float]) -> float:
        """
        Computes the interquartile range (IQR) of the window.
        
        Args:
            window: The rolling window of historical values plus the current value.
            
        Returns:
            The IQR as a float.
        """
        q75, q25 = np.percentile(window, [75, 25])
        return float(q75 - q25)

    def _compute_fft_peak(self, window: List[float]) -> float:
        """
        Computes the magnitude of the dominant frequency peak using FFT.
        
        Ignores the DC component (index 0).
        
        Args:
            window: The rolling window of historical values plus the current value.
            
        Returns:
            The highest FFT magnitude (excluding DC) as a non-negative float.
        """
        fft_vals = np.abs(np.fft.fft(window))
        # Ignore the DC component (index 0)
        if len(fft_vals) > 1:
            return float(np.max(fft_vals[1:]))
        return 0.0
