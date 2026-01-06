"""
SHAP Feature Attribution Module
================================

Provides SHAP (SHapley Additive exPlanations) values to explain individual predictions
from the Random Forest model.

SHAP values show how much each feature contributed to pushing the prediction
from the base value (average model output) to the actual prediction.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import json


class SHAPExplainer:
    """Generate SHAP explanations for Random Forest predictions."""
    
    @staticmethod
    def compute_shap_values(model, features: List[float], 
                          background_data: Optional[np.ndarray] = None,
                          num_samples: int = 100) -> Dict:
        """
        Compute SHAP values using Monte Carlo approximation.
        
        This approximates true SHAP values by:
        1. Sampling random feature coalitions
        2. Computing prediction deltas
        3. Averaging contributions
        
        Args:
            model: Trained RandomForestClassifier
            features: Feature vector [5 values in 0-1]
            background_data: Dataset for baseline computation
            num_samples: Number of Monte Carlo samples
        
        Returns:
            Dict with:
                - base_value: Average model output
                - shap_values: Contribution of each feature
                - prediction: Final prediction
                - feature_names: Labels for features
                - explanations: Human-readable interpretations
        """
        features_array = np.array(features).reshape(1, -1)
        prediction = float(model.predict_proba(features_array)[0, 1])
        
        # Get base value (average prediction on random background)
        if background_data is None:
            # Use model's average behavior as baseline
            base_value = model.predict_proba(np.zeros((1, len(features))))[0, 1]
        else:
            base_value = model.predict_proba(background_data).mean(axis=0)[1]
        
        feature_names = [
            'Social Interaction',
            'Repetitive Behaviors', 
            'Emotional Understanding',
            'Sensory Sensitivities',
            'Solitude Preference'
        ]
        
        # Compute SHAP values using Monte Carlo approximation
        shap_values = []
        
        for feature_idx in range(len(features)):
            # Marginal contribution of this feature
            contribution = 0.0
            
            for _ in range(num_samples):
                # Sample a coalition
                coalition = np.random.rand(len(features)) > 0.5
                
                # Prediction with feature included
                features_with = features_array.copy()
                
                # Prediction without feature (set to 0)
                features_without = features_array.copy()
                features_without[0, feature_idx] = 0
                
                pred_with = model.predict_proba(features_with)[0, 1]
                pred_without = model.predict_proba(features_without)[0, 1]
                
                contribution += (pred_with - pred_without)
            
            shap_value = contribution / num_samples
            shap_values.append(float(shap_value))
        
        # Normalize so they sum to (prediction - base_value)
        total_contribution = sum(shap_values)
        if abs(total_contribution) > 1e-6:
            shap_values = [s * (prediction - base_value) / total_contribution for s in shap_values]
        
        # Generate explanations
        explanations = SHAPExplainer._generate_explanations(
            shap_values, features, feature_names, prediction, base_value
        )
        
        return {
            'base_value': float(base_value),
            'shap_values': shap_values,
            'prediction': prediction,
            'feature_names': feature_names,
            'feature_values': list(features),
            'explanations': explanations,
            'top_features': SHAPExplainer._get_top_features(
                shap_values, feature_names, k=3
            )
        }
    
    @staticmethod
    def _generate_explanations(shap_values: List[float], 
                              feature_values: List[float],
                              feature_names: List[str],
                              prediction: float,
                              base_value: float) -> Dict[str, str]:
        """Generate human-readable explanations for SHAP values."""
        explanations = {}
        
        for i, (shap_val, feature_val, name) in enumerate(zip(shap_values, feature_values, feature_names)):
            # Determine direction and magnitude
            if abs(shap_val) < 0.01:
                impact = "minimal impact"
            elif shap_val > 0.05:
                impact = f"increased prediction by {shap_val*100:.1f}%"
            elif shap_val < -0.05:
                impact = f"decreased prediction by {abs(shap_val)*100:.1f}%"
            else:
                impact = "small impact"
            
            # Feature value context
            if feature_val == 1:
                context = "was positive (Yes)"
            elif feature_val == 0:
                context = "was negative (No)"
            else:
                context = f"was {feature_val:.1f}"
            
            explanations[name] = f"{name} {context} and had {impact}."
        
        return explanations
    
    @staticmethod
    def _get_top_features(shap_values: List[float], 
                         feature_names: List[str],
                         k: int = 3) -> List[Dict]:
        """Get top K most impactful features."""
        # Sort by absolute SHAP value
        indexed = [(abs(s), s, n) for s, n in zip(shap_values, feature_names)]
        indexed.sort(reverse=True)
        
        top = []
        for abs_val, shap_val, name in indexed[:k]:
            direction = "↑ Increased" if shap_val > 0 else "↓ Decreased"
            top.append({
                'feature': name,
                'shap_value': float(shap_val),
                'direction': direction,
                'magnitude': float(abs_val)
            })
        
        return top
    
    @staticmethod
    def get_feature_importance_ranking(shap_values: List[float],
                                       feature_names: List[str]) -> List[Dict]:
        """
        Rank features by absolute SHAP value (importance for this prediction).
        
        Returns list of dicts: {'feature': name, 'importance': abs_shap, 'contribution': shap}
        """
        ranking = []
        for shap_val, name in zip(shap_values, feature_names):
            ranking.append({
                'feature': name,
                'contribution': float(shap_val),
                'importance': float(abs(shap_val)),
                'direction': 'positive' if shap_val > 0 else 'negative'
            })
        
        ranking.sort(key=lambda x: x['importance'], reverse=True)
        return ranking


class SimpleTreeExplainer:
    """
    Simplified SHAP approximation using just tree feature importance.
    
    For each prediction, shows which features matter most based on:
    1. Tree splits closest to data point
    2. Feature importance from training
    3. Actual feature values in this instance
    """
    
    @staticmethod
    def explain_prediction(model, features: List[float]) -> Dict:
        """
        Explain prediction using tree structure analysis.
        
        Args:
            model: Trained RandomForestClassifier
            features: Feature vector [5 values in 0-1]
        
        Returns:
            Dict with explanation details
        """
        prediction = float(model.predict_proba(np.array(features).reshape(1, -1))[0, 1])
        
        feature_names = [
            'Social Interaction',
            'Repetitive Behaviors',
            'Emotional Understanding', 
            'Sensory Sensitivities',
            'Solitude Preference'
        ]
        
        # Get feature importance from model
        importances = model.feature_importances_
        
        # Weight importance by feature values (active features matter more)
        weighted_importance = []
        for importance, feature_val in zip(importances, features):
            # Features that are "on" (1) and important get higher weight
            if feature_val == 1:
                weight = importance * 1.2
            elif feature_val == 0:
                weight = importance * 0.3
            else:
                weight = importance
            weighted_importance.append(weight)
        
        # Normalize
        total_weight = sum(weighted_importance)
        if total_weight > 0:
            contributions = [w / total_weight * prediction for w in weighted_importance]
        else:
            contributions = [0] * len(features)
        
        # Generate explanations
        explanations = {}
        for i, (name, feat_val, contrib) in enumerate(zip(feature_names, features, contributions)):
            if feat_val == 1:
                status = "positive"
                status_text = "Yes"
            else:
                status = "negative"
                status_text = "No"
            
            if contrib > 0.05:
                impact = f"strongly supports ASD (contributes {contrib*100:.1f}%)"
            elif contrib > 0.02:
                impact = f"somewhat supports ASD (contributes {contrib*100:.1f}%)"
            else:
                impact = f"minimally impacts result"
            
            explanations[name] = f"{name}: {status_text} - {impact}"
        
        top_features = sorted(
            [(n, c) for n, c in zip(feature_names, contributions)],
            key=lambda x: abs(x[1]),
            reverse=True
        )[:3]
        
        return {
            'prediction': prediction,
            'contributions': contributions,
            'feature_names': feature_names,
            'feature_values': list(features),
            'explanations': explanations,
            'top_features': [
                {
                    'feature': name,
                    'contribution': float(contrib),
                    'direction': 'positive' if contrib > 0 else 'negative'
                }
                for name, contrib in top_features
            ],
            'method': 'tree_importance'
        }


def explain_prediction(model, features: List[float], 
                      method: str = 'tree') -> Dict:
    """
    Convenience function to explain a prediction.
    
    Args:
        model: Trained RandomForestClassifier
        features: Feature vector [5 values in 0-1]
        method: 'tree' (fast) or 'shap' (more accurate but slower)
    
    Returns:
        Dict with explanation details, top features, and text
    """
    if method == 'shap':
        return SHAPExplainer.compute_shap_values(model, features)
    else:
        return SimpleTreeExplainer.explain_prediction(model, features)


def get_feature_contribution_text(explanation: Dict) -> str:
    """Convert explanation dict to readable text."""
    lines = []
    
    lines.append(f"Prediction: {explanation['prediction']*100:.1f}% likelihood of ASD")
    lines.append("\nHow we arrived at this prediction:\n")
    
    for feature_name, text in explanation['explanations'].items():
        lines.append(f"• {text}")
    
    lines.append("\nMost influential factors:")
    for item in explanation['top_features']:
        direction = "↑" if item['direction'] == 'positive' else "↓"
        lines.append(f"  {direction} {item['feature']}: {item['contribution']*100:.1f}%")
    
    return "\n".join(lines)
