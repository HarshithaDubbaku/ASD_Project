"""
Auto Retraining Framework
Extension 7: Scheduled model retraining with performance monitoring
"""

import numpy as np
import joblib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
from sklearn.ensemble import RandomForestClassifier
from models import db, Response
import os


class PerformanceMonitor:
    """Monitor model performance metrics over time."""
    
    def __init__(self, model_path: str = 'model/asd_model.joblib'):
        """
        Initialize performance monitor.
        
        Args:
            model_path: Path to saved model
        """
        self.model_path = model_path
        self.model = None
        self.performance_history = []
        self.metrics_file = 'model/performance_metrics.json'
        self.load_model()
        self.load_history()
    
    def load_model(self) -> bool:
        """Load model from disk."""
        try:
            self.model = joblib.load(self.model_path)
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
    
    def load_history(self) -> bool:
        """Load performance history from disk."""
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r') as f:
                    self.performance_history = json.load(f)
                return True
        except Exception as e:
            print(f"Error loading history: {e}")
        return False
    
    def save_history(self) -> bool:
        """Save performance history to disk."""
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, 'w') as f:
                json.dump(self.performance_history, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving history: {e}")
            return False
    
    def calculate_metrics_from_responses(self, lookback_days: int = 7) -> Dict[str, Any]:
        """
        Calculate performance metrics from recent user responses.
        
        Args:
            lookback_days: Number of days to look back
            
        Returns:
            Dictionary of performance metrics
        """
        # Get responses from lookback period
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        try:
            responses = Response.query.filter(
                Response.timestamp >= cutoff_date
            ).all()
        except Exception:
            # If database query fails, return empty metrics
            return self._empty_metrics()
        
        if len(responses) == 0:
            return self._empty_metrics()
        
        # Extract features and actual outcomes (if available from calibration)
        correct = 0
        total = 0
        predictions = []
        scores = []
        
        for response in responses:
            if response.features and response.score is not None:
                try:
                    features = json.loads(response.features) if isinstance(response.features, str) else response.features
                    features_array = np.array(features).reshape(1, -1)
                    pred = self.model.predict(features_array)[0]
                    predictions.append(pred)
                    scores.append(response.score / 100.0)
                    
                    # Track accuracy (using threshold of 0.5)
                    if (response.score >= 50 and pred == 1) or (response.score < 50 and pred == 0):
                        correct += 1
                    total += 1
                except Exception:
                    continue
        
        if total == 0:
            return self._empty_metrics()
        
        # Calculate accuracy
        accuracy = correct / total
        
        # Calculate average score
        avg_score = np.mean(scores) if scores else 0.5
        
        # Calculate prediction distribution
        n_positive = sum(1 for p in predictions if p == 1)
        positive_rate = n_positive / len(predictions) if predictions else 0.0
        
        # Calculate confidence (average probability)
        confidences = self.model.predict_proba(
            np.array([json.loads(r.features) if isinstance(r.features, str) else r.features 
                     for r in responses if r.features])
        )
        avg_confidence = np.mean(np.max(confidences, axis=1)) if len(confidences) > 0 else 0.5
        
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'lookback_days': lookback_days,
            'total_responses': total,
            'accuracy': float(accuracy),
            'avg_score': float(avg_score),
            'positive_rate': float(positive_rate),
            'avg_confidence': float(avg_confidence),
            'confidence_accuracy_gap': float(abs(avg_confidence - accuracy)),
        }
        
        return metrics
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'total_responses': 0,
            'accuracy': 0.0,
            'avg_score': 0.5,
            'positive_rate': 0.0,
            'avg_confidence': 0.5,
            'confidence_accuracy_gap': 0.0,
        }
    
    def record_metrics(self, metrics: Dict[str, Any]) -> bool:
        """
        Record performance metrics.
        
        Args:
            metrics: Metrics to record
            
        Returns:
            Success status
        """
        self.performance_history.append(metrics)
        return self.save_history()
    
    def get_performance_trend(self, n_records: int = 10) -> Dict[str, Any]:
        """
        Get performance trend over recent records.
        
        Args:
            n_records: Number of recent records to analyze
            
        Returns:
            Trend analysis
        """
        if len(self.performance_history) < 2:
            return {'trend': 'insufficient_data', 'message': 'Need more data points'}
        
        recent = self.performance_history[-n_records:] if n_records < len(self.performance_history) else self.performance_history
        
        accuracies = [m['accuracy'] for m in recent]
        gaps = [m['confidence_accuracy_gap'] for m in recent]
        
        # Calculate trend (simple linear trend)
        if len(accuracies) >= 2:
            accuracy_trend = accuracies[-1] - accuracies[0]
            gap_trend = gaps[-1] - gaps[0]
        else:
            accuracy_trend = 0
            gap_trend = 0
        
        avg_accuracy = np.mean(accuracies)
        avg_gap = np.mean(gaps)
        
        # Determine if retraining is needed
        needs_retraining = (
            avg_accuracy < 0.75 or  # Accuracy below 75%
            avg_gap > 0.2 or         # Confidence gap above 20%
            accuracy_trend < -0.05   # Accuracy declining
        )
        
        return {
            'n_records': len(recent),
            'avg_accuracy': float(avg_accuracy),
            'accuracy_trend': float(accuracy_trend),
            'avg_confidence_gap': float(avg_gap),
            'gap_trend': float(gap_trend),
            'needs_retraining': bool(needs_retraining),
            'retraining_reason': self._get_retraining_reason(avg_accuracy, avg_gap, accuracy_trend),
        }
    
    def _get_retraining_reason(self, accuracy: float, gap: float, trend: float) -> str:
        """Get reason why retraining is needed."""
        reasons = []
        
        if accuracy < 0.75:
            reasons.append(f"Low accuracy ({accuracy:.2%})")
        if gap > 0.2:
            reasons.append(f"High confidence gap ({gap:.2%})")
        if trend < -0.05:
            reasons.append(f"Accuracy declining ({trend:.2%})")
        
        if not reasons:
            return "Model performing well"
        
        return "; ".join(reasons)


class AutoRetrainingScheduler:
    """Schedule and manage automatic model retraining."""
    
    def __init__(self, model_path: str = 'model/asd_model.joblib'):
        """
        Initialize auto-retraining scheduler.
        
        Args:
            model_path: Path to model
        """
        self.model_path = model_path
        self.monitor = PerformanceMonitor(model_path)
        self.retraining_log = []
        self.config = self._default_config()
        self.load_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'check_interval_hours': 24,
            'min_responses_for_retraining': 50,
            'accuracy_threshold': 0.75,
            'confidence_gap_threshold': 0.2,
            'lookback_days': 7,
            'auto_retrain_enabled': True,
            'max_retrain_frequency_hours': 168,  # 1 week
        }
    
    def load_config(self) -> bool:
        """Load configuration from disk."""
        try:
            if os.path.exists('model/retraining_config.json'):
                with open('model/retraining_config.json', 'r') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
                return True
        except Exception:
            pass
        return False
    
    def save_config(self) -> bool:
        """Save configuration to disk."""
        try:
            os.makedirs('model', exist_ok=True)
            with open('model/retraining_config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception:
            return False
    
    def should_retrain(self) -> Tuple[bool, str]:
        """
        Check if model should be retrained.
        
        Returns:
            Tuple of (should_retrain, reason)
        """
        if not self.config['auto_retrain_enabled']:
            return False, "Auto-retraining disabled"
        
        # Get recent performance metrics
        metrics = self.monitor.calculate_metrics_from_responses(
            lookback_days=self.config['lookback_days']
        )
        
        # Check if enough responses
        if metrics['total_responses'] < self.config['min_responses_for_retraining']:
            return False, f"Insufficient responses ({metrics['total_responses']})"
        
        # Check performance
        if metrics['accuracy'] < self.config['accuracy_threshold']:
            reason = f"Low accuracy ({metrics['accuracy']:.2%} < {self.config['accuracy_threshold']:.2%})"
            return True, reason
        
        if metrics['confidence_accuracy_gap'] > self.config['confidence_gap_threshold']:
            reason = f"High confidence gap ({metrics['confidence_accuracy_gap']:.2%} > {self.config['confidence_gap_threshold']:.2%})"
            return True, reason
        
        # Check trend
        trend = self.monitor.get_performance_trend()
        if trend.get('needs_retraining'):
            return True, trend.get('retraining_reason', 'Performance trend indicates retraining needed')
        
        return False, "Performance is acceptable"
    
    def execute_retraining(self, new_model=None) -> Dict[str, Any]:
        """
        Execute model retraining.
        
        Args:
            new_model: Optional new model to use; if None, trains from scratch
            
        Returns:
            Retraining results
        """
        start_time = datetime.utcnow()
        
        # If new model provided, use it; otherwise create placeholder
        if new_model is not None:
            model = new_model
            training_method = 'provided_model'
        else:
            # Generate synthetic training data and retrain
            from train_model import train_model
            try:
                model = train_model()
                training_method = 'synthetic_data'
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e),
                    'timestamp': start_time.isoformat(),
                }
        
        # Save new model
        try:
            backup_path = self._backup_current_model()
            joblib.dump(model, self.model_path)
            
            end_time = datetime.utcnow()
            
            # Record retraining
            result = {
                'success': True,
                'timestamp': start_time.isoformat(),
                'duration_seconds': (end_time - start_time).total_seconds(),
                'model_path': self.model_path,
                'backup_path': backup_path,
                'training_method': training_method,
                'new_metrics': self.monitor.calculate_metrics_from_responses(),
            }
            
            self.retraining_log.append(result)
            self._save_retraining_log()
            
            # Update monitor's model
            self.monitor.load_model()
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': start_time.isoformat(),
            }
    
    def _backup_current_model(self) -> str:
        """
        Backup current model before retraining.
        
        Returns:
            Path to backup model
        """
        if not os.path.exists(self.model_path):
            return None
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_path = f'model/asd_model_backup_{timestamp}.joblib'
        
        try:
            joblib.dump(joblib.load(self.model_path), backup_path)
            return backup_path
        except Exception:
            return None
    
    def _save_retraining_log(self) -> bool:
        """Save retraining log."""
        try:
            os.makedirs('model', exist_ok=True)
            with open('model/retraining_log.json', 'w') as f:
                json.dump(self.retraining_log, f, indent=2)
            return True
        except Exception:
            return False
    
    def load_retraining_log(self) -> bool:
        """Load retraining log from disk."""
        try:
            if os.path.exists('model/retraining_log.json'):
                with open('model/retraining_log.json', 'r') as f:
                    self.retraining_log = json.load(f)
                return True
        except Exception:
            pass
        return False
    
    def get_retraining_status(self) -> Dict[str, Any]:
        """
        Get current retraining status.
        
        Returns:
            Status information
        """
        should_retrain, reason = self.should_retrain()
        trend = self.monitor.get_performance_trend()
        
        # Get last retraining
        last_retraining = None
        if self.retraining_log:
            last_successful = [r for r in self.retraining_log if r['success']]
            if last_successful:
                last_retraining = last_successful[-1]
        
        return {
            'should_retrain': should_retrain,
            'retraining_reason': reason,
            'performance_trend': trend,
            'last_retraining': last_retraining,
            'total_retrainings': len(self.retraining_log),
            'config': self.config,
        }


def get_auto_retraining_status() -> Dict[str, Any]:
    """
    Convenience function to get auto-retraining status.
    
    Returns:
        Status dictionary
    """
    try:
        scheduler = AutoRetrainingScheduler()
        return scheduler.get_retraining_status()
    except Exception as e:
        return {
            'error': str(e),
            'status': 'error',
        }


if __name__ == '__main__':
    # Example usage
    scheduler = AutoRetrainingScheduler()
    
    print("\n=== Auto Retraining Status ===")
    status = scheduler.get_retraining_status()
    
    print(f"Should retrain: {status['should_retrain']}")
    print(f"Reason: {status['retraining_reason']}")
    print(f"Performance trend: {status['performance_trend']}")
    print(f"Total retrainings: {status['total_retrainings']}")
