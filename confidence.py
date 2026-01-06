"""
Confidence Interval & Uncertainty Quantification Module
=======================================================

Provides confidence bounds for ASD predictions using multiple methods:
1. Bootstrap aggregation (variance across Random Forest estimators)
2. Prediction variance (using tree predictions distribution)
3. Calibration-based confidence intervals
"""

import numpy as np
from typing import Tuple, Dict, Optional


class ConfidenceCalculator:
    """Calculate confidence intervals for model predictions."""
    
    @staticmethod
    def bootstrap_confidence(model, features: list, n_bootstrap: int = 100, 
                           confidence_level: float = 0.95) -> Dict:
        """
        Calculate confidence interval using bootstrap sampling from estimators.
        
        Args:
            model: Trained RandomForestClassifier
            features: Feature vector [0-1] for 5 features
            n_bootstrap: Number of bootstrap samples (default 100, max is n_estimators)
            confidence_level: Confidence level for interval (default 0.95 = 95%)
        
        Returns:
            Dict with:
                - prediction: Point estimate (probability)
                - ci_lower: Lower confidence bound
                - ci_upper: Upper confidence bound
                - std_error: Standard error
                - confidence_level: Requested confidence level
                - width: CI width (ci_upper - ci_lower)
                - quality: "High", "Medium", or "Low" based on width
        """
        if not hasattr(model, 'estimators_'):
            return {
                'prediction': float(model.predict_proba([features])[0, 1]),
                'ci_lower': None,
                'ci_upper': None,
                'std_error': None,
                'confidence_level': confidence_level,
                'width': None,
                'quality': 'Unknown',
                'method': 'point_estimate'
            }
        
        n_estimators = len(model.estimators_)
        n_samples = min(n_bootstrap, n_estimators)
        
        # Sample tree predictions
        predictions = []
        for i in range(n_samples):
            tree = model.estimators_[i % n_estimators]
            # Get probability for ASD class (index 1)
            prob = tree.predict_proba([features])[0, 1]
            predictions.append(prob)
        
        predictions = np.array(predictions)
        point_estimate = predictions.mean()
        std_error = predictions.std()
        
        # Calculate confidence interval using percentile method
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        ci_lower = np.percentile(predictions, lower_percentile)
        ci_upper = np.percentile(predictions, upper_percentile)
        
        # Clamp to [0, 1]
        ci_lower = max(0.0, min(1.0, ci_lower))
        ci_upper = max(0.0, min(1.0, ci_upper))
        point_estimate = max(0.0, min(1.0, point_estimate))
        
        ci_width = ci_upper - ci_lower
        
        # Assess confidence quality
        if ci_width < 0.15:
            quality = "High"
        elif ci_width < 0.30:
            quality = "Medium"
        else:
            quality = "Low"
        
        return {
            'prediction': float(point_estimate),
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'std_error': float(std_error),
            'confidence_level': confidence_level,
            'width': float(ci_width),
            'quality': quality,
            'method': 'bootstrap'
        }
    
    @staticmethod
    def tree_variance_confidence(model, features: list, 
                                confidence_level: float = 0.95) -> Dict:
        """
        Calculate confidence using variance across all Random Forest estimators.
        
        Uses the variance in predictions from individual trees to quantify uncertainty.
        
        Args:
            model: Trained RandomForestClassifier
            features: Feature vector
            confidence_level: Confidence level for interval
        
        Returns:
            Dict with confidence bounds and quality assessment
        """
        if not hasattr(model, 'estimators_'):
            prob = float(model.predict_proba([features])[0, 1])
            return {
                'prediction': prob,
                'ci_lower': None,
                'ci_upper': None,
                'std_error': None,
                'confidence_level': confidence_level,
                'width': None,
                'quality': 'Unknown',
                'method': 'point_estimate'
            }
        
        # Get predictions from all trees
        tree_predictions = []
        for tree in model.estimators_:
            prob = tree.predict_proba([features])[0, 1]
            tree_predictions.append(prob)
        
        tree_predictions = np.array(tree_predictions)
        point_estimate = tree_predictions.mean()
        std_error = tree_predictions.std()
        
        # Use normal approximation for CI
        # z-score for 95% confidence: 1.96, for 90%: 1.645, for 99%: 2.576
        alpha = 1 - confidence_level
        z_score = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence_level, 1.96)
        
        margin = z_score * std_error
        ci_lower = max(0.0, point_estimate - margin)
        ci_upper = min(1.0, point_estimate + margin)
        
        ci_width = ci_upper - ci_lower
        
        if ci_width < 0.15:
            quality = "High"
        elif ci_width < 0.30:
            quality = "Medium"
        else:
            quality = "Low"
        
        return {
            'prediction': float(point_estimate),
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'std_error': float(std_error),
            'confidence_level': confidence_level,
            'width': float(ci_width),
            'quality': quality,
            'method': 'tree_variance'
        }
    
    @staticmethod
    def get_confidence_interpretation(conf_info: Dict) -> Dict:
        """
        Interpret confidence interval and prediction together.
        
        Returns: Dict with:
            - confidence_assessment: "Very High", "High", "Medium", "Low", "Very Low"
            - interpretation: Human-readable text
            - recommendation: Clinical recommendation based on confidence + score
        """
        if conf_info['ci_lower'] is None:
            return {
                'confidence_assessment': 'Unknown',
                'interpretation': 'Confidence bounds could not be calculated.',
                'recommendation': 'Use standard interpretation based on score.'
            }
        
        prediction = conf_info['prediction']
        width = conf_info['width']
        ci_lower = conf_info['ci_lower']
        ci_upper = conf_info['ci_upper']
        
        # Assess confidence quality
        if width < 0.10:
            confidence_assessment = "Very High"
        elif width < 0.20:
            confidence_assessment = "High"
        elif width < 0.35:
            confidence_assessment = "Medium"
        elif width < 0.50:
            confidence_assessment = "Low"
        else:
            confidence_assessment = "Very Low"
        
        # Build interpretation
        interpretation_parts = []
        
        if prediction < 0.25:
            score_assessment = "Unlikely ASD"
        elif prediction < 0.50:
            score_assessment = "Borderline/Below Average"
        elif prediction < 0.75:
            score_assessment = "Borderline/Above Average"
        else:
            score_assessment = "Likely ASD traits"
        
        interpretation_parts.append(f"Score Assessment: {score_assessment}")
        
        # Add confidence detail
        if confidence_assessment in ["Very High", "High"]:
            interpretation_parts.append(
                f"Confidence: {confidence_assessment}. The model is consistent across estimates."
            )
        elif confidence_assessment == "Medium":
            interpretation_parts.append(
                f"Confidence: {confidence_assessment}. Moderate uncertainty in prediction."
            )
        else:
            interpretation_parts.append(
                f"Confidence: {confidence_assessment}. Significant uncertainty in prediction."
            )
        
        # Add confidence interval detail
        interpretation_parts.append(
            f"Likely Range: {ci_lower*100:.1f}% - {ci_upper*100:.1f}%"
        )
        
        interpretation = " ".join(interpretation_parts)
        
        # Clinical recommendations
        if prediction < 0.30:
            if confidence_assessment in ["Very High", "High"]:
                recommendation = "Assessment suggests low likelihood of ASD. No further screening recommended at this time."
            else:
                recommendation = "Assessment suggests low likelihood of ASD, but with some uncertainty. Monitor for any behavioral changes."
        elif prediction < 0.50:
            recommendation = "Borderline result. Consider follow-up screening with a healthcare provider for confirmation."
        elif prediction < 0.70:
            recommendation = "Assessment suggests traits consistent with ASD. Recommend professional evaluation."
        else:
            if confidence_assessment in ["Very High", "High"]:
                recommendation = "Assessment suggests likely ASD traits. Professional evaluation strongly recommended."
            else:
                recommendation = "Assessment suggests possible ASD traits. Professional evaluation recommended."
        
        return {
            'confidence_assessment': confidence_assessment,
            'interpretation': interpretation,
            'recommendation': recommendation
        }
    
    @staticmethod
    def batch_confidence(model, features_list: list, 
                        confidence_level: float = 0.95) -> list:
        """Calculate confidence for multiple predictions efficiently."""
        return [
            ConfidenceCalculator.bootstrap_confidence(model, features, 
                                                     confidence_level=confidence_level)
            for features in features_list
        ]


def calculate_prediction_confidence(model, features: list, 
                                   method: str = 'bootstrap',
                                   confidence_level: float = 0.95) -> Dict:
    """
    Convenience function to calculate prediction confidence.
    
    Args:
        model: Trained RandomForestClassifier
        features: Feature vector [0-1] for 5 features
        method: 'bootstrap' or 'tree_variance'
        confidence_level: 0.90, 0.95, or 0.99
    
    Returns:
        Dict with confidence bounds and interpretation
    """
    calculator = ConfidenceCalculator()
    
    if method == 'tree_variance':
        conf_info = calculator.tree_variance_confidence(model, features, confidence_level)
    else:
        conf_info = calculator.bootstrap_confidence(model, features, confidence_level=confidence_level)
    
    # Add interpretation
    interpretation = calculator.get_confidence_interpretation(conf_info)
    
    return {
        **conf_info,
        **interpretation
    }
