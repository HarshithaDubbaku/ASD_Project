"""
A/B Testing Module Tests
Extension 5: Unit tests for A/B testing framework
"""

import pytest
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from ab_testing import ABTestFramework, load_models_for_test, run_ab_test
import joblib
import os


@pytest.fixture
def dummy_model():
    """Create a dummy RandomForest model for testing."""
    X_train = np.random.randint(0, 2, (100, 5))
    y_train = np.random.randint(0, 2, 100)
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X_train, y_train)
    return model


@pytest.fixture
def ab_framework(dummy_model):
    """Create ABTestFramework instance."""
    return ABTestFramework(dummy_model, dummy_model)


class TestABTestFramework:
    """Test A/B Testing Framework class."""
    
    def test_initialization(self, dummy_model):
        """Test framework initialization."""
        framework = ABTestFramework(dummy_model, dummy_model)
        assert framework.model_v1 is not None
        assert framework.model_v2 is not None
        assert framework.results is None
        assert framework.test_data is None
    
    def test_test_data_generation(self, ab_framework):
        """Test synthetic data generation."""
        test_data = ab_framework.generate_test_data(n_samples=200)
        
        assert len(test_data) == 200
        assert all(len(sample) == 5 for sample in test_data)
        assert all(all(f in [0, 1] for f in sample) for sample in test_data)
        assert ab_framework.test_data is not None
    
    def test_test_data_generation_small(self, ab_framework):
        """Test data generation with small sample size."""
        test_data = ab_framework.generate_test_data(n_samples=10)
        assert len(test_data) == 10
        assert all(len(sample) == 5 for sample in test_data)
    
    def test_run_predictions_without_data(self, ab_framework):
        """Test predictions with auto-generated data."""
        preds_v1, preds_v2 = ab_framework.run_predictions()
        
        assert len(preds_v1) > 0
        assert len(preds_v2) > 0
        assert all(0 <= p <= 100 for p in preds_v1)
        assert all(0 <= p <= 100 for p in preds_v2)
    
    def test_run_predictions_with_data(self, ab_framework):
        """Test predictions with provided data."""
        test_data = [[1, 0, 1, 0, 1], [0, 1, 0, 1, 0]]
        preds_v1, preds_v2 = ab_framework.run_predictions(test_data)
        
        assert len(preds_v1) == 2
        assert len(preds_v2) == 2
    
    def test_calculate_metrics(self, ab_framework):
        """Test metrics calculation."""
        preds_v1 = np.array([10, 20, 30, 40, 50])
        preds_v2 = np.array([15, 25, 35, 45, 55])
        
        metrics = ab_framework.calculate_metrics(preds_v1, preds_v2)
        
        assert 'model_v1' in metrics
        assert 'model_v2' in metrics
        assert metrics['model_v1']['mean'] == 30.0
        assert metrics['model_v2']['mean'] == 35.0
        assert 'std' in metrics['model_v1']
        assert 'q25' in metrics['model_v1']
        assert 'q75' in metrics['model_v1']
    
    def test_calculate_metrics_values(self, ab_framework):
        """Test specific metric values."""
        preds_v1 = np.array([10, 20, 30, 40, 50])
        preds_v2 = np.array([10, 20, 30, 40, 50])
        
        metrics = ab_framework.calculate_metrics(preds_v1, preds_v2)
        
        assert metrics['model_v1']['min'] == 10.0
        assert metrics['model_v1']['max'] == 50.0
        assert metrics['model_v1']['median'] == 30.0
    
    def test_ttest_comparison(self, ab_framework):
        """Test t-test comparison."""
        preds_v1 = np.array([10, 15, 20, 25, 30])
        preds_v2 = np.array([40, 45, 50, 55, 60])
        
        result = ab_framework.ttest_comparison(preds_v1, preds_v2)
        
        assert 't_statistic' in result
        assert 'p_value' in result
        assert 'cohens_d' in result
        assert 'significant' in result
        assert 'effect_size' in result
        assert result['significant'] == True  # Should be significant
    
    def test_ttest_no_significant_difference(self, ab_framework):
        """Test t-test with no significant difference."""
        preds_v1 = np.array([25, 26, 27, 28, 29])
        preds_v2 = np.array([25, 26, 27, 28, 29])
        
        result = ab_framework.ttest_comparison(preds_v1, preds_v2)
        
        assert result['p_value'] == 1.0  # Identical arrays
        assert result['significant'] == False
    
    def test_confidence_interval_comparison(self, ab_framework):
        """Test confidence interval calculation."""
        preds_v1 = np.random.normal(50, 10, 100)
        preds_v2 = np.random.normal(55, 10, 100)
        
        ci_result = ab_framework.confidence_interval_comparison(preds_v1, preds_v2)
        
        assert 'model_v1' in ci_result
        assert 'model_v2' in ci_result
        assert 'overlap' in ci_result
        
        assert 'mean' in ci_result['model_v1']
        assert 'ci_lower' in ci_result['model_v1']
        assert 'ci_upper' in ci_result['model_v1']
        
        # CI lower should be less than mean, upper greater
        assert ci_result['model_v1']['ci_lower'] < ci_result['model_v1']['mean']
        assert ci_result['model_v1']['ci_upper'] > ci_result['model_v1']['mean']
    
    def test_mann_whitney_test(self, ab_framework):
        """Test Mann-Whitney U test."""
        preds_v1 = np.array([10, 20, 30, 40, 50])
        preds_v2 = np.array([60, 70, 80, 90, 100])
        
        result = ab_framework.mann_whitney_test(preds_v1, preds_v2)
        
        assert 'u_statistic' in result
        assert 'p_value' in result
        assert 'significant' in result
        assert result['p_value'] < 0.05  # Should be significant
    
    def test_run_full_comparison(self, ab_framework):
        """Test full comparison workflow."""
        results = ab_framework.run_full_comparison(ab_framework.generate_test_data(100))
        
        assert results is not None
        assert 'timestamp' in results
        assert 'sample_size' in results
        assert results['sample_size'] == 100
        assert 'descriptive_stats' in results
        assert 'ttest' in results
        assert 'confidence_intervals' in results
        assert 'mann_whitney' in results
        assert 'predictions' in results
    
    def test_results_stored(self, ab_framework):
        """Test that results are stored in framework."""
        results = ab_framework.run_full_comparison(ab_framework.generate_test_data(50))
        
        assert ab_framework.results is not None
        assert ab_framework.results == results
    
    def test_get_summary_no_results(self, ab_framework):
        """Test summary when no results available."""
        summary = ab_framework.get_summary()
        
        assert 'error' in summary
        assert summary['error'] == 'No test results available. Run run_full_comparison first.'
    
    def test_get_summary_with_results(self, ab_framework):
        """Test summary with results."""
        ab_framework.run_full_comparison(ab_framework.generate_test_data(100))
        summary = ab_framework.get_summary()
        
        assert 'sample_size' in summary
        assert 'model_v1_mean' in summary
        assert 'model_v2_mean' in summary
        assert 'difference' in summary
        assert 'p_value' in summary
        assert 'significant' in summary
        assert 'winner' in summary
        assert 'recommendation' in summary
    
    def test_summary_winner_determination(self, ab_framework):
        """Test winner determination in summary."""
        ab_framework.run_full_comparison(ab_framework.generate_test_data(100))
        summary = ab_framework.get_summary()
        
        # Winner should be one of the models or tie
        assert summary['winner'] in ['Model V1 (Control)', 'Model V2 (Treatment)', 'No significant difference']
    
    def test_export_results_no_results(self, ab_framework):
        """Test export without results."""
        success = ab_framework.export_results('test_output.json')
        assert success == False
    
    def test_export_results_with_results(self, ab_framework, tmp_path):
        """Test export with results."""
        ab_framework.run_full_comparison(ab_framework.generate_test_data(50))
        
        output_file = str(tmp_path / 'ab_test_results.json')
        success = ab_framework.export_results(output_file)
        
        assert success == True
        assert os.path.exists(output_file)
    
    def test_export_results_content(self, ab_framework, tmp_path):
        """Test exported results content."""
        import json
        
        ab_framework.run_full_comparison(ab_framework.generate_test_data(50))
        
        output_file = str(tmp_path / 'ab_test_results.json')
        ab_framework.export_results(output_file)
        
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        assert 'timestamp' in data
        assert 'sample_size' in data
        assert 'ttest' in data


class TestModelLoading:
    """Test model loading functionality."""
    
    def test_load_models_missing_files(self):
        """Test loading with missing files."""
        model_v1, model_v2 = load_models_for_test(
            v1_path='nonexistent/model.joblib',
            v2_path='nonexistent/model2.joblib'
        )
        
        assert model_v1 is None
        assert model_v2 is None
    
    def test_load_single_model_as_both(self, dummy_model, tmp_path):
        """Test loading single model for both versions."""
        model_path = str(tmp_path / 'model.joblib')
        joblib.dump(dummy_model, model_path)
        
        model_v1, model_v2 = load_models_for_test(v1_path=model_path, v2_path=None)
        
        assert model_v1 is not None
        assert model_v2 is not None


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_run_ab_test_function(self, dummy_model):
        """Test the convenience run_ab_test function."""
        results = run_ab_test(dummy_model, dummy_model, n_samples=50)
        
        assert results is not None
        assert 'sample_size' in results
        assert results['sample_size'] == 50
    
    def test_run_ab_test_with_single_model(self, dummy_model):
        """Test run_ab_test with single model."""
        results = run_ab_test(dummy_model, n_samples=30)
        
        assert results is not None
        assert results['sample_size'] == 30


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_predictions(self, ab_framework):
        """Test with empty predictions."""
        preds_v1 = np.array([])
        preds_v2 = np.array([])
        
        # Should handle gracefully
        try:
            result = ab_framework.ttest_comparison(preds_v1, preds_v2)
            # If it doesn't raise, check result structure
            assert 'p_value' in result
        except ValueError:
            # Empty arrays might raise - this is acceptable
            pass
    
    def test_single_prediction(self, ab_framework):
        """Test with single prediction."""
        preds_v1 = np.array([50.0])
        preds_v2 = np.array([50.0])
        
        metrics = ab_framework.calculate_metrics(preds_v1, preds_v2)
        
        assert metrics['model_v1']['mean'] == 50.0
        assert metrics['model_v1']['min'] == 50.0
        assert metrics['model_v1']['max'] == 50.0
    
    def test_identical_predictions(self, ab_framework):
        """Test with identical predictions."""
        preds = np.array([50.0] * 10)
        
        result = ab_framework.ttest_comparison(preds, preds)
        
        # Identical arrays yield NaN which is handled as 1.0
        assert result['p_value'] in [1.0, np.nan] or np.isnan(result['p_value'])
        assert result['cohens_d'] == 0.0
        assert result['significant'] == False
    
    def test_large_sample_size(self, ab_framework):
        """Test with large sample size."""
        preds_v1 = np.random.normal(50, 10, 10000)
        preds_v2 = np.random.normal(51, 10, 10000)
        
        result = ab_framework.ttest_comparison(preds_v1, preds_v2)
        
        # With large samples, even small differences become significant
        assert 'p_value' in result
        assert 'significant' in result


class TestStatisticalProperties:
    """Test statistical properties and correctness."""
    
    def test_mean_calculation_correctness(self, ab_framework):
        """Test that mean is calculated correctly."""
        preds = np.array([10, 20, 30, 40, 50])
        preds_copy = preds.copy()
        
        metrics = ab_framework.calculate_metrics(preds, preds_copy)
        
        expected_mean = np.mean(preds)
        assert abs(metrics['model_v1']['mean'] - expected_mean) < 0.001
    
    def test_ci_bounds_validity(self, ab_framework):
        """Test that confidence interval bounds are valid."""
        preds_v1 = np.random.normal(50, 10, 100)
        preds_v2 = np.random.normal(50, 10, 100)
        
        ci_result = ab_framework.confidence_interval_comparison(preds_v1, preds_v2)
        
        # CI lower should always be less than upper
        assert ci_result['model_v1']['ci_lower'] < ci_result['model_v1']['ci_upper']
        assert ci_result['model_v2']['ci_lower'] < ci_result['model_v2']['ci_upper']
        
        # Mean should be within CI
        assert ci_result['model_v1']['ci_lower'] <= ci_result['model_v1']['mean']
        assert ci_result['model_v1']['mean'] <= ci_result['model_v1']['ci_upper']
    
    def test_effect_size_classification(self, ab_framework):
        """Test effect size classification."""
        # Small effect (Cohen's d < 0.2)
        preds_v1 = np.random.normal(50, 5, 100)
        preds_v2 = np.random.normal(51, 5, 100)
        result_small = ab_framework.ttest_comparison(preds_v1, preds_v2)
        assert result_small['effect_size'] == 'small'
        
        # Large effect (Cohen's d > 0.8)
        preds_v1 = np.random.normal(10, 5, 100)
        preds_v2 = np.random.normal(50, 5, 100)
        result_large = ab_framework.ttest_comparison(preds_v1, preds_v2)
        assert result_large['effect_size'] == 'large'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
