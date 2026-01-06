"""
A/B Testing Framework for Model Comparison
Extension 5: Statistical comparison of different model versions
"""

import json
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any
from datetime import datetime
import joblib
import os


class ABTestFramework:
    """Compare two model versions statistically."""
    
    def __init__(self, model_v1, model_v2=None):
        """
        Initialize A/B test framework.
        
        Args:
            model_v1: First model (baseline/control)
            model_v2: Second model (treatment) - if None, will load default
        """
        self.model_v1 = model_v1
        self.model_v2 = model_v2
        self.results = None
        self.test_data = None
        
    def generate_test_data(self, n_samples: int = 200) -> List[List[int]]:
        """
        Generate balanced test dataset.
        
        Args:
            n_samples: Total samples to generate
            
        Returns:
            List of feature vectors [f0, f1, f2, f3, f4]
        """
        np.random.seed(42)
        features = []
        
        # Generate balanced positive and negative cases
        n_per_class = n_samples // 2
        
        # Positive cases (higher feature values)
        for _ in range(n_per_class):
            feature_vector = [
                np.random.randint(0, 2),  # Social
                np.random.randint(0, 2),  # Repetitive
                np.random.randint(0, 2),  # Emotional
                np.random.randint(0, 2),  # Sensory
                np.random.randint(0, 2),  # Solitude
            ]
            features.append(feature_vector)
        
        # Negative cases (lower feature values)
        for _ in range(n_per_class):
            feature_vector = [
                np.random.randint(0, 2),
                np.random.randint(0, 2),
                np.random.randint(0, 2),
                np.random.randint(0, 2),
                np.random.randint(0, 2),
            ]
            features.append(feature_vector)
        
        self.test_data = features
        return features
    
    def run_predictions(self, test_data: List[List[int]] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run both models on test data.
        
        Args:
            test_data: Feature vectors to test (uses generated if None)
            
        Returns:
            Tuple of (predictions_v1, predictions_v2)
        """
        if test_data is None:
            if self.test_data is None:
                test_data = self.generate_test_data()
            else:
                test_data = self.test_data
        
        # Convert to numpy array
        X_test = np.array(test_data)
        
        # Get predictions as probabilities
        preds_v1 = self.model_v1.predict_proba(X_test)[:, 1] * 100
        preds_v2 = self.model_v2.predict_proba(X_test)[:, 1] * 100 if self.model_v2 else preds_v1
        
        return preds_v1, preds_v2
    
    def calculate_metrics(self, preds_v1: np.ndarray, preds_v2: np.ndarray) -> Dict[str, Any]:
        """
        Calculate performance metrics for both models.
        
        Args:
            preds_v1: Model V1 predictions
            preds_v2: Model V2 predictions
            
        Returns:
            Dictionary with metrics
        """
        metrics = {
            'model_v1': {
                'mean': float(np.mean(preds_v1)),
                'median': float(np.median(preds_v1)),
                'std': float(np.std(preds_v1)),
                'min': float(np.min(preds_v1)),
                'max': float(np.max(preds_v1)),
                'q25': float(np.percentile(preds_v1, 25)),
                'q75': float(np.percentile(preds_v1, 75)),
            },
            'model_v2': {
                'mean': float(np.mean(preds_v2)),
                'median': float(np.median(preds_v2)),
                'std': float(np.std(preds_v2)),
                'min': float(np.min(preds_v2)),
                'max': float(np.max(preds_v2)),
                'q25': float(np.percentile(preds_v2, 25)),
                'q75': float(np.percentile(preds_v2, 75)),
            }
        }
        return metrics
    
    def ttest_comparison(self, preds_v1: np.ndarray, preds_v2: np.ndarray) -> Dict[str, Any]:
        """
        Perform independent t-test between models.
        
        Args:
            preds_v1: Model V1 predictions
            preds_v2: Model V2 predictions
            
        Returns:
            T-test results
        """
        t_stat, p_value = stats.ttest_ind(preds_v1, preds_v2)
        
        # Effect size (Cohen's d)
        pooled_std = np.sqrt((np.std(preds_v1)**2 + np.std(preds_v2)**2) / 2)
        cohens_d = (np.mean(preds_v1) - np.mean(preds_v2)) / pooled_std if pooled_std > 0 else 0
        
        # Handle NaN in cohens_d (identical arrays)
        if np.isnan(cohens_d):
            cohens_d = 0.0
        
        cohens_d_abs = abs(cohens_d)
        
        return {
            't_statistic': float(t_stat),
            'p_value': float(p_value) if not np.isnan(p_value) else 1.0,
            'cohens_d': float(cohens_d),
            'significant': bool(p_value < 0.05) if not np.isnan(p_value) else False,
            'effect_size': 'small' if cohens_d_abs < 0.2 else ('medium' if cohens_d_abs < 0.8 else 'large')
        }
    
    def confidence_interval_comparison(self, preds_v1: np.ndarray, preds_v2: np.ndarray) -> Dict[str, Any]:
        """
        Calculate 95% confidence intervals for mean predictions.
        
        Args:
            preds_v1: Model V1 predictions
            preds_v2: Model V2 predictions
            
        Returns:
            95% CI for both models
        """
        ci_v1 = stats.t.interval(0.95, len(preds_v1)-1, 
                                  loc=np.mean(preds_v1), 
                                  scale=stats.sem(preds_v1))
        ci_v2 = stats.t.interval(0.95, len(preds_v2)-1,
                                  loc=np.mean(preds_v2),
                                  scale=stats.sem(preds_v2))
        
        return {
            'model_v1': {
                'mean': float(np.mean(preds_v1)),
                'ci_lower': float(ci_v1[0]),
                'ci_upper': float(ci_v1[1]),
            },
            'model_v2': {
                'mean': float(np.mean(preds_v2)),
                'ci_lower': float(ci_v2[0]),
                'ci_upper': float(ci_v2[1]),
            },
            'overlap': ci_v1[1] >= ci_v2[0] and ci_v2[1] >= ci_v1[0],  # CIs overlap?
        }
    
    def mann_whitney_test(self, preds_v1: np.ndarray, preds_v2: np.ndarray) -> Dict[str, Any]:
        """
        Perform Mann-Whitney U test (non-parametric alternative to t-test).
        
        Args:
            preds_v1: Model V1 predictions
            preds_v2: Model V2 predictions
            
        Returns:
            Mann-Whitney U test results
        """
        u_stat, p_value = stats.mannwhitneyu(preds_v1, preds_v2, alternative='two-sided')
        
        return {
            'u_statistic': float(u_stat),
            'p_value': float(p_value),
            'significant': p_value < 0.05,
        }
    
    def run_full_comparison(self, test_data: List[List[int]] = None) -> Dict[str, Any]:
        """
        Run complete A/B test comparison.
        
        Args:
            test_data: Test data to use (generates if None)
            
        Returns:
            Comprehensive comparison results
        """
        # Generate or use provided test data
        if test_data is None:
            test_data = self.generate_test_data()
        
        # Run predictions
        preds_v1, preds_v2 = self.run_predictions(test_data)
        
        # Calculate all metrics
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'sample_size': len(test_data),
            
            # Descriptive statistics
            'descriptive_stats': self.calculate_metrics(preds_v1, preds_v2),
            
            # T-test
            'ttest': self.ttest_comparison(preds_v1, preds_v2),
            
            # Confidence intervals
            'confidence_intervals': self.confidence_interval_comparison(preds_v1, preds_v2),
            
            # Mann-Whitney U (non-parametric)
            'mann_whitney': self.mann_whitney_test(preds_v1, preds_v2),
            
            # Raw predictions
            'predictions': {
                'model_v1': [float(x) for x in preds_v1],
                'model_v2': [float(x) for x in preds_v2],
            }
        }
        
        # Convert booleans to strings for JSON serialization
        self.results['ttest']['significant'] = bool(self.results['ttest']['significant'])
        self.results['mann_whitney']['significant'] = bool(self.results['mann_whitney']['significant'])
        self.results['confidence_intervals']['overlap'] = bool(self.results['confidence_intervals']['overlap'])
        
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get human-readable summary of test results.
        
        Returns:
            Summary dictionary
        """
        if self.results is None:
            return {'error': 'No test results available. Run run_full_comparison first.'}
        
        stats_v1 = self.results['descriptive_stats']['model_v1']
        stats_v2 = self.results['descriptive_stats']['model_v2']
        ttest = self.results['ttest']
        
        # Determine winner
        if ttest['significant']:
            if stats_v1['mean'] > stats_v2['mean']:
                winner = 'Model V1 (Control)'
                difference = stats_v1['mean'] - stats_v2['mean']
            else:
                winner = 'Model V2 (Treatment)'
                difference = stats_v2['mean'] - stats_v1['mean']
        else:
            winner = 'No significant difference'
            difference = abs(stats_v1['mean'] - stats_v2['mean'])
        
        return {
            'sample_size': self.results['sample_size'],
            'model_v1_mean': round(stats_v1['mean'], 2),
            'model_v2_mean': round(stats_v2['mean'], 2),
            'difference': round(difference, 2),
            'p_value': round(ttest['p_value'], 4),
            'significant': ttest['significant'],
            'effect_size': ttest['effect_size'],
            'winner': winner,
            'confidence': 'High (p < 0.05)' if ttest['significant'] else 'Low (p >= 0.05)',
            'recommendation': f"Model V2 shows {ttest['effect_size']} improvement" if winner == 'Model V2 (Treatment)' 
                            else f"Model V1 still preferred ({ttest['effect_size']} difference)" 
                            if winner == 'Model V1 (Control)' 
                            else "Models perform equivalently - deploy based on other criteria"
        }
    
    def export_results(self, filename: str = 'ab_test_results.json') -> bool:
        """
        Export test results to JSON file.
        
        Args:
            filename: Output filename
            
        Returns:
            Success status
        """
        if self.results is None:
            return False
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting results: {e}")
            return False


def load_models_for_test(v1_path: str = 'model/asd_model.joblib', 
                         v2_path: str = None):
    """
    Load models for A/B testing.
    
    Args:
        v1_path: Path to model V1 (control/baseline)
        v2_path: Path to model V2 (treatment) - if None, loads v1 as both
        
    Returns:
        Tuple of (model_v1, model_v2)
    """
    try:
        model_v1 = joblib.load(v1_path)
        print(f"✓ Loaded Model V1 from {v1_path}")
    except Exception as e:
        print(f"✗ Failed to load Model V1: {e}")
        return None, None
    
    if v2_path:
        try:
            model_v2 = joblib.load(v2_path)
            print(f"✓ Loaded Model V2 from {v2_path}")
        except Exception as e:
            print(f"✗ Failed to load Model V2: {e}")
            model_v2 = model_v1
    else:
        model_v2 = model_v1
    
    return model_v1, model_v2


def run_ab_test(model_v1, model_v2=None, n_samples: int = 200) -> Dict[str, Any]:
    """
    Convenience function to run A/B test.
    
    Args:
        model_v1: Model V1 (baseline)
        model_v2: Model V2 (treatment)
        n_samples: Number of test samples
        
    Returns:
        Full comparison results
    """
    framework = ABTestFramework(model_v1, model_v2)
    return framework.run_full_comparison(framework.generate_test_data(n_samples))


if __name__ == '__main__':
    # Example usage
    model_v1, model_v2 = load_models_for_test()
    
    if model_v1:
        framework = ABTestFramework(model_v1, model_v2)
        results = framework.run_full_comparison(framework.generate_test_data(200))
        summary = framework.get_summary()
        
        print("\n=== A/B Test Summary ===")
        print(f"Sample Size: {summary['sample_size']}")
        print(f"Model V1 Mean: {summary['model_v1_mean']}%")
        print(f"Model V2 Mean: {summary['model_v2_mean']}%")
        print(f"Difference: {summary['difference']}%")
        print(f"P-value: {summary['p_value']}")
        print(f"Significant: {summary['significant']}")
        print(f"Winner: {summary['winner']}")
        print(f"Recommendation: {summary['recommendation']}")
