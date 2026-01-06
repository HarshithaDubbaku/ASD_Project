"""
Test suite for confidence interval calculations (Extension 3)
"""

import pytest
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from confidence import ConfidenceCalculator, calculate_prediction_confidence


@pytest.fixture
def trained_model():
    """Create a simple trained RandomForestClassifier for testing."""
    X = np.random.RandomState(42).beta(2, 5, size=(100, 5))
    y = np.random.RandomState(42).randint(0, 2, 100)
    model = RandomForestClassifier(n_estimators=20, random_state=42)
    model.fit(X, y)
    return model


def test_bootstrap_confidence_returns_dict(trained_model):
    """Test that bootstrap_confidence returns a proper dict."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    result = ConfidenceCalculator.bootstrap_confidence(trained_model, features)
    
    assert isinstance(result, dict)
    assert 'prediction' in result
    assert 'ci_lower' in result
    assert 'ci_upper' in result
    assert 'std_error' in result
    assert 'quality' in result
    assert 'method' in result
    assert result['method'] == 'bootstrap'


def test_bootstrap_confidence_bounds(trained_model):
    """Test that CI bounds make sense."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    result = ConfidenceCalculator.bootstrap_confidence(trained_model, features)
    
    # Check that bounds are valid
    assert 0 <= result['prediction'] <= 1
    assert 0 <= result['ci_lower'] <= 1
    assert 0 <= result['ci_upper'] <= 1
    assert result['ci_lower'] <= result['prediction'] <= result['ci_upper']
    assert result['ci_lower'] <= result['ci_upper']
    assert 0 <= result['width'] <= 1


def test_tree_variance_confidence(trained_model):
    """Test tree_variance_confidence method."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    result = ConfidenceCalculator.tree_variance_confidence(trained_model, features)
    
    assert result['method'] == 'tree_variance'
    assert result['ci_lower'] <= result['prediction'] <= result['ci_upper']
    assert 0 <= result['std_error'] <= 1


def test_confidence_quality_assessment(trained_model):
    """Test that confidence quality is correctly assessed."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    result = ConfidenceCalculator.bootstrap_confidence(trained_model, features)
    
    assert result['quality'] in ['High', 'Medium', 'Low']
    
    # High confidence: narrow CI
    if result['width'] < 0.15:
        assert result['quality'] == 'High'
    # Medium confidence
    elif result['width'] < 0.30:
        assert result['quality'] == 'Medium'
    # Low confidence: wide CI
    else:
        assert result['quality'] == 'Low'


def test_get_confidence_interpretation(trained_model):
    """Test confidence interpretation generation."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    conf_info = ConfidenceCalculator.bootstrap_confidence(trained_model, features)
    interpretation = ConfidenceCalculator.get_confidence_interpretation(conf_info)
    
    assert 'confidence_assessment' in interpretation
    assert 'interpretation' in interpretation
    assert 'recommendation' in interpretation
    
    assert interpretation['confidence_assessment'] in [
        'Very High', 'High', 'Medium', 'Low', 'Very Low', 'Unknown'
    ]
    assert len(interpretation['interpretation']) > 0
    assert len(interpretation['recommendation']) > 0


def test_calculate_prediction_confidence_bootstrap(trained_model):
    """Test convenience function with bootstrap method."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    result = calculate_prediction_confidence(trained_model, features, method='bootstrap')
    
    assert 'prediction' in result
    assert 'ci_lower' in result
    assert 'interpretation' in result
    assert 'recommendation' in result


def test_calculate_prediction_confidence_tree_variance(trained_model):
    """Test convenience function with tree_variance method."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    result = calculate_prediction_confidence(trained_model, features, method='tree_variance')
    
    assert result['method'] == 'tree_variance'
    assert 'std_error' in result


def test_confidence_levels(trained_model):
    """Test different confidence levels."""
    features = [0.5, 0.3, 0.7, 0.2, 0.4]
    
    for conf_level in [0.90, 0.95, 0.99]:
        result = ConfidenceCalculator.bootstrap_confidence(
            trained_model, features, confidence_level=conf_level
        )
        assert result['confidence_level'] == conf_level


def test_batch_confidence(trained_model):
    """Test batch confidence calculation."""
    features_list = [
        [0.5, 0.3, 0.7, 0.2, 0.4],
        [0.1, 0.2, 0.3, 0.4, 0.5],
        [0.9, 0.8, 0.7, 0.6, 0.5]
    ]
    
    results = ConfidenceCalculator.batch_confidence(trained_model, features_list)
    
    assert len(results) == 3
    assert all('prediction' in r for r in results)
    assert all('ci_lower' in r for r in results)


def test_interpretation_for_high_score():
    """Test interpretation for high ASD score."""
    conf_info = {
        'prediction': 0.85,
        'ci_lower': 0.75,
        'ci_upper': 0.95,
        'std_error': 0.05,
        'confidence_level': 0.95,
        'width': 0.20,
        'quality': 'High',
        'method': 'bootstrap'
    }
    
    interpretation = ConfidenceCalculator.get_confidence_interpretation(conf_info)
    
    assert 'High Probability' in interpretation['interpretation'] or 'ASD traits' in interpretation['interpretation']
    assert 'professional evaluation' in interpretation['recommendation'].lower()


def test_interpretation_for_low_score():
    """Test interpretation for low ASD score."""
    conf_info = {
        'prediction': 0.15,
        'ci_lower': 0.05,
        'ci_upper': 0.25,
        'std_error': 0.05,
        'confidence_level': 0.95,
        'width': 0.20,
        'quality': 'High',
        'method': 'bootstrap'
    }
    
    interpretation = ConfidenceCalculator.get_confidence_interpretation(conf_info)
    
    assert 'low likelihood' in interpretation['interpretation'].lower() or 'unlikely' in interpretation['interpretation'].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
