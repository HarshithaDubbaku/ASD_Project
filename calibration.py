"""
Model Calibration Framework
Extension 6: Probability calibration for improved prediction reliability
"""

import numpy as np
from sklearn.calibration import CalibratedClassifierCV, IsotonicRegression
from sklearn.linear_model import LogisticRegression
from typing import Dict, List, Tuple, Any
import json
from datetime import datetime


class ModelCalibrator:
    """Calibrate model probabilities for better reliability."""
    
    def __init__(self, model):
        """
        Initialize calibrator with a trained model.
        
        Args:
            model: Trained scikit-learn classifier
        """
        self.model = model
        self.calibrator_isotonic = None
        self.calibrator_platt = None
        self.calibration_data = None
        self.calibration_metrics = None
        
    def split_calibration_data(self, X, y, test_size: float = 0.3, random_state: int = 42) -> Tuple:
        """
        Split data for calibration (stratified split).
        
        Args:
            X: Feature matrix
            y: Labels
            test_size: Fraction for calibration set
            random_state: Random seed
            
        Returns:
            Tuple of (X_train, X_cal, y_train, y_cal)
        """
        np.random.seed(random_state)
        n_samples = len(X)
        n_cal = int(n_samples * test_size)
        
        indices = np.random.permutation(n_samples)
        cal_indices = indices[:n_cal]
        train_indices = indices[n_cal:]
        
        return X[train_indices], X[cal_indices], y[train_indices], y[cal_indices]
    
    def get_raw_probabilities(self, X) -> np.ndarray:
        """
        Get raw probabilities from uncalibrated model.
        
        Args:
            X: Feature matrix
            
        Returns:
            Probabilities for positive class
        """
        return self.model.predict_proba(X)[:, 1]
    
    def fit_isotonic_calibration(self, X_cal, y_cal) -> Dict[str, Any]:
        """
        Fit isotonic regression calibration (non-parametric).
        
        Args:
            X_cal: Calibration features
            y_cal: Calibration labels
            
        Returns:
            Calibration metrics
        """
        # Get raw probabilities
        raw_probs = self.get_raw_probabilities(X_cal)
        
        # Fit isotonic regression (no random_state parameter)
        self.calibrator_isotonic = IsotonicRegression(out_of_bounds='clip')
        self.calibrator_isotonic.fit(raw_probs, y_cal)
        
        # Get calibrated probabilities
        calibrated_probs = self.calibrator_isotonic.predict(raw_probs)
        
        # Calculate metrics
        metrics = self._calculate_calibration_metrics(y_cal, raw_probs, calibrated_probs, 'isotonic')
        
        return metrics
    
    def fit_platt_calibration(self, X_cal, y_cal) -> Dict[str, Any]:
        """
        Fit Platt scaling calibration (parametric).
        
        Args:
            X_cal: Calibration features
            y_cal: Calibration labels
            
        Returns:
            Calibration metrics
        """
        # Get raw probabilities
        raw_probs = self.get_raw_probabilities(X_cal).reshape(-1, 1)
        
        # Fit logistic regression to map raw probs to calibrated
        self.calibrator_platt = LogisticRegression(random_state=42)
        self.calibrator_platt.fit(raw_probs, y_cal)
        
        # Get calibrated probabilities
        calibrated_probs = self.calibrator_platt.predict_proba(raw_probs)[:, 1]
        
        # Calculate metrics
        metrics = self._calculate_calibration_metrics(y_cal, raw_probs.ravel(), calibrated_probs, 'platt')
        
        return metrics
    
    def _calculate_calibration_metrics(self, y_true, raw_probs, calibrated_probs, method: str) -> Dict[str, Any]:
        """
        Calculate calibration metrics.
        
        Args:
            y_true: True labels
            raw_probs: Raw uncalibrated probabilities
            calibrated_probs: Calibrated probabilities
            method: Calibration method name
            
        Returns:
            Dictionary of metrics
        """
        # Expected Calibration Error (ECE)
        n_bins = 10
        bin_sums = np.zeros(n_bins)
        bin_true = np.zeros(n_bins)
        bin_total = np.zeros(n_bins)
        
        for i in range(len(y_true)):
            bin_idx = int(calibrated_probs[i] * (n_bins - 1))
            bin_sums[bin_idx] += abs(calibrated_probs[i] - y_true[i])
            bin_true[bin_idx] += y_true[i]
            bin_total[bin_idx] += 1
        
        ece = 0
        for i in range(n_bins):
            if bin_total[i] > 0:
                ece += (bin_total[i] / len(y_true)) * bin_sums[i] / bin_total[i]
        
        # Brier Score (mean squared error)
        raw_brier = np.mean((raw_probs - y_true) ** 2)
        cal_brier = np.mean((calibrated_probs - y_true) ** 2)
        brier_improvement = raw_brier - cal_brier
        
        # Maximum Calibration Error (MCE)
        mce = np.max([abs(calibrated_probs[i] - y_true[i]) for i in range(len(y_true))])
        
        # Accuracy
        raw_accuracy = np.mean(np.round(raw_probs) == y_true)
        cal_accuracy = np.mean(np.round(calibrated_probs) == y_true)
        
        # Confidence-accuracy gap
        raw_confidence = np.mean(np.maximum(raw_probs, 1 - raw_probs))
        cal_confidence = np.mean(np.maximum(calibrated_probs, 1 - calibrated_probs))
        raw_gap = abs(raw_confidence - raw_accuracy)
        cal_gap = abs(cal_confidence - cal_accuracy)
        
        return {
            'method': method,
            'expected_calibration_error': float(ece),
            'raw_brier_score': float(raw_brier),
            'calibrated_brier_score': float(cal_brier),
            'brier_improvement': float(brier_improvement),
            'max_calibration_error': float(mce),
            'raw_accuracy': float(raw_accuracy),
            'calibrated_accuracy': float(cal_accuracy),
            'raw_confidence': float(raw_confidence),
            'calibrated_confidence': float(cal_confidence),
            'raw_confidence_gap': float(raw_gap),
            'calibrated_confidence_gap': float(cal_gap),
            'reliability_improvement': float(raw_gap - cal_gap),
        }
    
    def fit_both_methods(self, X_cal, y_cal) -> Dict[str, Any]:
        """
        Fit both calibration methods and compare.
        
        Args:
            X_cal: Calibration features
            y_cal: Calibration labels
            
        Returns:
            Comparison of both methods
        """
        isotonic_metrics = self.fit_isotonic_calibration(X_cal, y_cal)
        platt_metrics = self.fit_platt_calibration(X_cal, y_cal)
        
        # Determine better method
        if isotonic_metrics['expected_calibration_error'] < platt_metrics['expected_calibration_error']:
            best_method = 'isotonic'
            best_metrics = isotonic_metrics
        else:
            best_method = 'platt'
            best_metrics = platt_metrics
        
        return {
            'timestamp': datetime.now().isoformat(),
            'isotonic': isotonic_metrics,
            'platt': platt_metrics,
            'best_method': best_method,
            'best_metrics': best_metrics,
        }
    
    def calibrate_probabilities(self, X, method: str = 'isotonic') -> np.ndarray:
        """
        Calibrate probabilities using fitted calibrator.
        
        Args:
            X: Feature matrix
            method: 'isotonic' or 'platt'
            
        Returns:
            Calibrated probabilities
        """
        raw_probs = self.get_raw_probabilities(X)
        
        if method == 'isotonic':
            if self.calibrator_isotonic is None:
                raise ValueError("Isotonic calibrator not fitted")
            return self.calibrator_isotonic.predict(raw_probs)
        
        elif method == 'platt':
            if self.calibrator_platt is None:
                raise ValueError("Platt calibrator not fitted")
            raw_probs_reshaped = raw_probs.reshape(-1, 1)
            return self.calibrator_platt.predict_proba(raw_probs_reshaped)[:, 1]
        
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def get_calibration_curve_data(self, X_test, y_test, n_bins: int = 10, method: str = 'isotonic') -> Dict[str, Any]:
        """
        Generate calibration curve data (for plotting).
        
        Args:
            X_test: Test features
            y_test: Test labels
            n_bins: Number of bins for curve
            method: Calibration method to use
            
        Returns:
            Data for plotting calibration curve
        """
        raw_probs = self.get_raw_probabilities(X_test)
        calibrated_probs = self.calibrate_probabilities(X_test, method)
        
        # Bin the probabilities
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        true_positive_rate = []
        observed_frequency = []
        confidence_bins = []
        
        for i in range(n_bins):
            mask = (calibrated_probs >= bin_edges[i]) & (calibrated_probs < bin_edges[i + 1])
            if mask.sum() > 0:
                observed_frequency.append(np.mean(y_test[mask]))
                confidence_bins.append(np.mean(calibrated_probs[mask]))
            else:
                observed_frequency.append(np.nan)
                confidence_bins.append(bin_centers[i])
        
        return {
            'confidence_bins': [float(x) for x in confidence_bins if not np.isnan(x)],
            'observed_frequency': [float(x) for x in observed_frequency if not np.isnan(x)],
            'perfect_calibration': [float(x) for x in bin_centers],
            'method': method,
        }
    
    def get_calibration_quality_assessment(self, metrics: Dict) -> Dict[str, Any]:
        """
        Assess calibration quality and provide recommendations.
        
        Args:
            metrics: Calibration metrics dictionary
            
        Returns:
            Quality assessment and recommendations
        """
        ece = metrics['expected_calibration_error']
        reliability_improvement = metrics.get('reliability_improvement', 0)
        brier_improvement = metrics['brier_improvement']
        
        # Quality classification
        if ece < 0.05:
            quality = 'Excellent'
            quality_icon = '⭐⭐⭐⭐⭐'
        elif ece < 0.10:
            quality = 'Good'
            quality_icon = '⭐⭐⭐⭐'
        elif ece < 0.15:
            quality = 'Fair'
            quality_icon = '⭐⭐⭐'
        else:
            quality = 'Poor'
            quality_icon = '⭐⭐'
        
        # Recommendations
        recommendations = []
        
        if ece > 0.10:
            recommendations.append("Model probabilities are not well-calibrated")
            recommendations.append("Consider using isotonic regression for better calibration")
        
        if reliability_improvement < 0.01:
            recommendations.append("Calibration provides minimal reliability improvement")
            recommendations.append("Current model may already be well-calibrated")
        else:
            recommendations.append(f"Calibration improves reliability by {reliability_improvement:.1%}")
        
        if brier_improvement > 0:
            recommendations.append(f"Brier score improved by {brier_improvement:.4f}")
        
        if metrics['calibrated_confidence_gap'] > 0.2:
            recommendations.append("Confidence-accuracy gap is still significant")
            recommendations.append("More calibration data may help")
        
        return {
            'quality': quality,
            'quality_icon': quality_icon,
            'ece': float(ece),
            'reliability_improvement': float(reliability_improvement),
            'brier_improvement': float(brier_improvement),
            'recommendations': recommendations,
        }
    
    def export_calibration_results(self, results: Dict, filename: str = 'calibration_results.json') -> bool:
        """
        Export calibration results to JSON.
        
        Args:
            results: Calibration results dictionary
            filename: Output filename
            
        Returns:
            Success status
        """
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting calibration results: {e}")
            return False


def generate_synthetic_calibration_data(n_samples: int = 500, random_state: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic data for calibration testing.
    
    Args:
        n_samples: Number of samples
        random_state: Random seed
        
    Returns:
        Tuple of (X, y)
    """
    np.random.seed(random_state)
    
    # Generate features
    X = np.random.randint(0, 2, (n_samples, 5))
    
    # Generate labels based on feature sum with some noise
    y = np.zeros(n_samples)
    for i in range(n_samples):
        feature_sum = np.sum(X[i])
        prob = min(1.0, feature_sum / 5.0)  # Probability increases with feature sum
        y[i] = np.random.binomial(1, prob)
    
    return X, y.astype(int)


def calculate_prediction_calibration(model, X_test, y_test, methods: List[str] = None) -> Dict[str, Any]:
    """
    Convenience function to calculate calibration metrics.
    
    Args:
        model: Trained classifier
        X_test: Test features
        y_test: Test labels
        methods: List of methods to try ('isotonic', 'platt', or both)
        
    Returns:
        Complete calibration analysis
    """
    if methods is None:
        methods = ['isotonic', 'platt']
    
    calibrator = ModelCalibrator(model)
    
    # Split for calibration
    X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X_test, y_test)
    
    # Fit calibration methods
    results = calibrator.fit_both_methods(X_cal, y_cal)
    
    # Add test set evaluation
    test_metrics = {}
    for method in methods:
        calibrated_probs = calibrator.calibrate_probabilities(X_test, method)
        raw_probs = calibrator.get_raw_probabilities(X_test)
        test_metrics[f'{method}_test'] = calibrator._calculate_calibration_metrics(
            y_test, raw_probs, calibrated_probs, f'{method}_test'
        )
    
    results['test_metrics'] = test_metrics
    
    return results


if __name__ == '__main__':
    # Example usage
    from sklearn.ensemble import RandomForestClassifier
    import joblib
    
    try:
        model = joblib.load('model/asd_model.joblib')
        X, y = generate_synthetic_calibration_data(500)
        
        results = calculate_prediction_calibration(model, X, y)
        
        print("\n=== Calibration Results ===")
        print(f"Best method: {results['best_method']}")
        print(f"ECE: {results['best_metrics']['expected_calibration_error']:.4f}")
        print(f"Brier improvement: {results['best_metrics']['brier_improvement']:.4f}")
        print(f"Reliability improvement: {results['best_metrics'].get('reliability_improvement', 0):.2%}")
        
    except Exception as e:
        print(f"Error: {e}")
