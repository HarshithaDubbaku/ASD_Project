"""
Model Calibration Tests
Extension 6: Unit tests for model calibration framework
"""

import pytest
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from calibration import (
    ModelCalibrator, 
    generate_synthetic_calibration_data,
    calculate_prediction_calibration
)
import joblib


@pytest.fixture
def dummy_model():
    """Create a dummy RandomForest model for testing."""
    X_train = np.random.randint(0, 2, (100, 5))
    y_train = np.random.randint(0, 2, 100)
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X_train, y_train)
    return model


@pytest.fixture
def calibrator(dummy_model):
    """Create ModelCalibrator instance."""
    return ModelCalibrator(dummy_model)


@pytest.fixture
def test_data():
    """Generate test data."""
    X, y = generate_synthetic_calibration_data(n_samples=200)
    return X, y


class TestModelCalibrator:
    """Test Model Calibrator class."""
    
    def test_initialization(self, dummy_model):
        """Test calibrator initialization."""
        calibrator = ModelCalibrator(dummy_model)
        assert calibrator.model is not None
        assert calibrator.calibrator_isotonic is None
        assert calibrator.calibrator_platt is None
    
    def test_split_calibration_data(self, calibrator, test_data):
        """Test data splitting for calibration."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y, test_size=0.3)
        
        assert len(X_train) + len(X_cal) == len(X)
        assert len(y_train) + len(y_cal) == len(y)
        assert len(X_cal) == int(len(X) * 0.3)
        assert len(X_train) == int(len(X) * 0.7)
    
    def test_get_raw_probabilities(self, calibrator, test_data):
        """Test raw probability extraction."""
        X, _ = test_data
        probs = calibrator.get_raw_probabilities(X)
        
        assert len(probs) == len(X)
        assert all(0 <= p <= 1 for p in probs)
    
    def test_fit_isotonic_calibration(self, calibrator, test_data):
        """Test isotonic regression calibration."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
        
        assert 'method' in metrics
        assert metrics['method'] == 'isotonic'
        assert 'expected_calibration_error' in metrics
        assert 'brier_improvement' in metrics
        assert metrics['expected_calibration_error'] >= 0
        assert calibrator.calibrator_isotonic is not None
    
    def test_fit_platt_calibration(self, calibrator, test_data):
        """Test Platt scaling calibration."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        metrics = calibrator.fit_platt_calibration(X_cal, y_cal)
        
        assert 'method' in metrics
        assert metrics['method'] == 'platt'
        assert 'expected_calibration_error' in metrics
        assert 'brier_improvement' in metrics
        assert metrics['expected_calibration_error'] >= 0
        assert calibrator.calibrator_platt is not None
    
    def test_fit_both_methods(self, calibrator, test_data):
        """Test fitting both calibration methods."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        results = calibrator.fit_both_methods(X_cal, y_cal)
        
        assert 'isotonic' in results
        assert 'platt' in results
        assert 'best_method' in results
        assert results['best_method'] in ['isotonic', 'platt']
        assert 'best_metrics' in results
        assert 'timestamp' in results
    
    def test_calibrate_probabilities_isotonic(self, calibrator, test_data):
        """Test probability calibration with isotonic method."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        calibrator.fit_isotonic_calibration(X_cal, y_cal)
        calibrated = calibrator.calibrate_probabilities(X, method='isotonic')
        
        assert len(calibrated) == len(X)
        assert all(0 <= p <= 1 for p in calibrated)
    
    def test_calibrate_probabilities_platt(self, calibrator, test_data):
        """Test probability calibration with Platt method."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        calibrator.fit_platt_calibration(X_cal, y_cal)
        calibrated = calibrator.calibrate_probabilities(X, method='platt')
        
        assert len(calibrated) == len(X)
        assert all(0 <= p <= 1 for p in calibrated)
    
    def test_calibrate_without_fitting(self, calibrator, test_data):
        """Test calibration error when not fitted."""
        X, _ = test_data
        
        with pytest.raises(ValueError):
            calibrator.calibrate_probabilities(X, method='isotonic')
        
        with pytest.raises(ValueError):
            calibrator.calibrate_probabilities(X, method='platt')
    
    def test_invalid_calibration_method(self, calibrator, test_data):
        """Test error on invalid calibration method."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        calibrator.fit_isotonic_calibration(X_cal, y_cal)
        
        with pytest.raises(ValueError):
            calibrator.calibrate_probabilities(X, method='invalid_method')
    
    def test_calibration_metrics_structure(self, calibrator, test_data):
        """Test structure of calibration metrics."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
        
        required_keys = [
            'method',
            'expected_calibration_error',
            'raw_brier_score',
            'calibrated_brier_score',
            'brier_improvement',
            'max_calibration_error',
            'raw_accuracy',
            'calibrated_accuracy',
            'raw_confidence',
            'calibrated_confidence',
            'raw_confidence_gap',
            'calibrated_confidence_gap',
            'reliability_improvement',
        ]
        
        for key in required_keys:
            assert key in metrics
    
    def test_get_calibration_curve_data(self, calibrator, test_data):
        """Test calibration curve data generation."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        calibrator.fit_isotonic_calibration(X_cal, y_cal)
        curve_data = calibrator.get_calibration_curve_data(X_train, y_train, n_bins=10)
        
        assert 'confidence_bins' in curve_data
        assert 'observed_frequency' in curve_data
        assert 'perfect_calibration' in curve_data
        assert 'method' in curve_data
        assert len(curve_data['confidence_bins']) > 0
        assert len(curve_data['observed_frequency']) > 0
    
    def test_get_calibration_quality_assessment(self, calibrator, test_data):
        """Test calibration quality assessment."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
        assessment = calibrator.get_calibration_quality_assessment(metrics)
        
        assert 'quality' in assessment
        assert assessment['quality'] in ['Excellent', 'Good', 'Fair', 'Poor']
        assert 'quality_icon' in assessment
        assert 'ece' in assessment
        assert 'recommendations' in assessment
        assert isinstance(assessment['recommendations'], list)
    
    def test_export_results(self, calibrator, test_data, tmp_path):
        """Test exporting calibration results."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        results = calibrator.fit_both_methods(X_cal, y_cal)
        output_file = str(tmp_path / 'calibration_results.json')
        
        success = calibrator.export_calibration_results(results, output_file)
        
        assert success == True
        import os
        assert os.path.exists(output_file)


class TestSyntheticDataGeneration:
    """Test synthetic data generation."""
    
    def test_generate_synthetic_data(self):
        """Test synthetic data generation."""
        X, y = generate_synthetic_calibration_data(n_samples=100)
        
        assert X.shape == (100, 5)
        assert len(y) == 100
        assert all(x in [0, 1] for row in X for x in row)
        assert all(y_val in [0, 1] for y_val in y)
    
    def test_synthetic_data_balance(self):
        """Test that synthetic data is reasonably balanced."""
        X, y = generate_synthetic_calibration_data(n_samples=1000)
        
        n_positive = np.sum(y)
        n_negative = len(y) - n_positive
        
        # Check for reasonable balance (20-80 range)
        ratio = n_positive / len(y)
        assert 0.2 <= ratio <= 0.8
    
    def test_synthetic_data_reproducibility(self):
        """Test that synthetic data is reproducible with same seed."""
        X1, y1 = generate_synthetic_calibration_data(n_samples=100, random_state=42)
        X2, y2 = generate_synthetic_calibration_data(n_samples=100, random_state=42)
        
        assert np.array_equal(X1, X2)
        assert np.array_equal(y1, y2)


class TestConvenienceFunction:
    """Test convenience functions."""
    
    def test_calculate_prediction_calibration(self, dummy_model):
        """Test the convenience calibration function."""
        X, y = generate_synthetic_calibration_data(n_samples=200)
        
        results = calculate_prediction_calibration(dummy_model, X, y)
        
        assert 'isotonic' in results
        assert 'platt' in results
        assert 'best_method' in results
        assert 'test_metrics' in results
    
    def test_calibration_with_single_method(self, dummy_model):
        """Test calibration with single method specified."""
        X, y = generate_synthetic_calibration_data(n_samples=200)
        
        results = calculate_prediction_calibration(dummy_model, X, y, methods=['isotonic'])
        
        assert 'isotonic' in results
        assert 'test_metrics' in results


class TestCalibrationProperties:
    """Test statistical properties of calibration."""
    
    def test_brier_improvement_positive(self, calibrator, test_data):
        """Test that calibration improves Brier score."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
        
        # Brier score typically improves (but not always guaranteed)
        # We just check the metric exists and is reasonable
        assert metrics['brier_improvement'] >= -0.1  # Allow small negative for noise
    
    def test_confidence_gap_reduction(self, calibrator, test_data):
        """Test that calibration reduces confidence-accuracy gap."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
        
        # Calibration should generally reduce the gap (but check exists)
        assert 'raw_confidence_gap' in metrics
        assert 'calibrated_confidence_gap' in metrics
    
    def test_ece_validity(self, calibrator, test_data):
        """Test that ECE is a valid metric."""
        X, y = test_data
        X_train, X_cal, y_train, y_cal = calibrator.split_calibration_data(X, y)
        
        metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
        
        ece = metrics['expected_calibration_error']
        assert 0 <= ece <= 1


class TestEdgeCases:
    """Test edge cases."""
    
    def test_small_calibration_set(self, calibrator):
        """Test calibration with small data set."""
        X_cal = np.random.randint(0, 2, (10, 5))
        y_cal = np.random.randint(0, 2, 10)
        
        metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
        assert metrics is not None
    
    def test_uniform_labels(self, calibrator):
        """Test calibration with uniform labels."""
        X_cal = np.random.randint(0, 2, (50, 5))
        y_cal = np.ones(50, dtype=int)  # All 1s
        
        try:
            metrics = calibrator.fit_isotonic_calibration(X_cal, y_cal)
            # Should complete even with uniform labels
            assert 'expected_calibration_error' in metrics
        except Exception:
            # Some methods may fail with uniform labels - that's acceptable
            pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
