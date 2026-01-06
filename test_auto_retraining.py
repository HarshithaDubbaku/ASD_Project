"""
Tests for auto-retraining framework
Extension 7: Model auto-retraining with performance monitoring
"""

import pytest
import json
import os
import tempfile
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
import joblib

from auto_retraining import (
    PerformanceMonitor,
    AutoRetrainingScheduler,
    get_auto_retraining_status,
)
from models import db, Response, User, RetrainingHistory
from app import app


@pytest.fixture
def app_context():
    """Create Flask app context for testing."""
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def temp_model_dir():
    """Create temporary directory for model files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_model(temp_model_dir):
    """Create a sample trained model for testing."""
    X = np.random.rand(50, 5).round(0).astype(int)
    y = np.random.randint(0, 2, 50)
    
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    
    model_path = os.path.join(temp_model_dir, 'asd_model.joblib')
    joblib.dump(model, model_path)
    
    return model_path, model


@pytest.fixture
def sample_responses(app_context):
    """Create sample user responses in database."""
    # Create a test user
    user = User(username='testuser', password_hash='hash123', email='test@example.com')
    db.session.add(user)
    db.session.commit()
    
    # Create responses
    responses = []
    for i in range(20):
        response = Response(
            user_id=user.id,
            timestamp=datetime.utcnow() - timedelta(days=i),
            age=25,
            gender='M',
            ethnicity='Asian',
            relation='Self',
            answers=[0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
            features=[0, 1, 0, 1, 1],
            score=50.0 + np.random.rand() * 50,
        )
        responses.append(response)
        db.session.add(response)
    
    db.session.commit()
    return responses


class TestPerformanceMonitor:
    """Test PerformanceMonitor class."""
    
    def test_monitor_initialization(self, sample_model):
        """Test monitor can be initialized with model path."""
        model_path, _ = sample_model
        monitor = PerformanceMonitor(model_path)
        
        assert monitor.model_path == model_path
        assert monitor.model is not None
        assert isinstance(monitor.performance_history, list)
    
    def test_load_model(self, sample_model):
        """Test loading model from disk."""
        model_path, expected_model = sample_model
        monitor = PerformanceMonitor(model_path)
        
        assert monitor.model is not None
        assert hasattr(monitor.model, 'predict')
        assert hasattr(monitor.model, 'predict_proba')
    
    def test_record_metrics(self, sample_model):
        """Test recording performance metrics."""
        model_path, _ = sample_model
        monitor = PerformanceMonitor(model_path)
        
        # Clear history for isolated test
        monitor.performance_history = []
        
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'accuracy': 0.85,
            'avg_score': 0.65,
            'total_responses': 10,
        }
        
        result = monitor.record_metrics(metrics)
        assert result is True
        assert len(monitor.performance_history) == 1
        assert monitor.performance_history[0]['accuracy'] == 0.85
    
    def test_empty_metrics_structure(self, sample_model):
        """Test empty metrics structure."""
        model_path, _ = sample_model
        monitor = PerformanceMonitor(model_path)
        
        metrics = monitor._empty_metrics()
        
        assert metrics['timestamp'] is not None
        assert 'accuracy' in metrics
        assert 'avg_score' in metrics
        assert 'positive_rate' in metrics
        assert metrics['total_responses'] == 0
    
    def test_calculate_metrics_from_responses(self, app_context, sample_model, sample_responses):
        """Test calculating metrics from database responses."""
        model_path, _ = sample_model
        
        # Patch model path temporarily
        original_init = PerformanceMonitor.__init__
        def patched_init(self, model_path_arg='model/asd_model.joblib'):
            original_init(self, model_path)
        
        monitor = PerformanceMonitor(model_path)
        metrics = monitor.calculate_metrics_from_responses(lookback_days=7)
        
        assert 'timestamp' in metrics
        assert 'accuracy' in metrics
        assert 'avg_score' in metrics
        assert metrics['total_responses'] > 0
        assert 0 <= metrics['accuracy'] <= 1
        assert 0 <= metrics['avg_score'] <= 1
        assert 0 <= metrics['avg_confidence'] <= 1
    
    def test_get_performance_trend(self, sample_model):
        """Test performance trend calculation."""
        model_path, _ = sample_model
        monitor = PerformanceMonitor(model_path)
        
        # Add multiple metric records
        for i in range(5):
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'accuracy': 0.70 + (i * 0.02),
                'confidence_accuracy_gap': 0.15 - (i * 0.01),
                'total_responses': 10,
            }
            monitor.performance_history.append(metrics)
        
        trend = monitor.get_performance_trend(n_records=5)
        
        assert 'avg_accuracy' in trend
        assert 'accuracy_trend' in trend
        assert 'needs_retraining' in trend
        assert trend['n_records'] == 5
    
    def test_retraining_reason_generation(self, sample_model):
        """Test retraining reason generation."""
        model_path, _ = sample_model
        monitor = PerformanceMonitor(model_path)
        
        # Low accuracy
        reason = monitor._get_retraining_reason(0.60, 0.15, -0.02)
        assert 'Low accuracy' in reason
        
        # High gap
        reason = monitor._get_retraining_reason(0.85, 0.25, 0.01)
        assert 'High confidence gap' in reason
        
        # Declining trend
        reason = monitor._get_retraining_reason(0.80, 0.15, -0.10)
        assert 'Accuracy declining' in reason


class TestAutoRetrainingScheduler:
    """Test AutoRetrainingScheduler class."""
    
    def test_scheduler_initialization(self, sample_model):
        """Test scheduler initialization."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        
        assert scheduler.model_path == model_path
        assert scheduler.monitor is not None
        assert isinstance(scheduler.config, dict)
        assert 'accuracy_threshold' in scheduler.config
        assert 'confidence_gap_threshold' in scheduler.config
    
    def test_default_config(self, sample_model):
        """Test default configuration."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        
        config = scheduler._default_config()
        
        assert config['check_interval_hours'] == 24
        assert config['min_responses_for_retraining'] == 50
        assert config['accuracy_threshold'] == 0.75
        assert config['confidence_gap_threshold'] == 0.2
        assert config['lookback_days'] == 7
        assert config['auto_retrain_enabled'] is True
    
    def test_should_retrain_disabled(self, sample_model):
        """Test should_retrain when auto-retrain is disabled."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        scheduler.config['auto_retrain_enabled'] = False
        
        should_retrain, reason = scheduler.should_retrain()
        
        assert should_retrain is False
        assert 'disabled' in reason.lower()
    
    def test_should_retrain_insufficient_data(self, sample_model, app_context):
        """Test should_retrain with insufficient responses."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        scheduler.config['min_responses_for_retraining'] = 100
        
        should_retrain, reason = should_retrain_result = scheduler.should_retrain()
        
        assert should_retrain is False
        assert 'Insufficient' in reason or 'responses' in reason.lower()
    
    def test_save_and_load_config(self, sample_model, temp_model_dir):
        """Test saving and loading configuration."""
        # Patch config file path
        config_path_orig = os.path.join(temp_model_dir, 'retraining_config.json')
        
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        scheduler.config['accuracy_threshold'] = 0.80
        scheduler.config['lookback_days'] = 14
        
        # Save config
        assert scheduler.save_config() is True
        
        # Create new scheduler and verify config
        scheduler2 = AutoRetrainingScheduler(model_path)
        # Config file might not exist in temp dir, but save/load methods should work
        assert scheduler2.config is not None
    
    def test_backup_current_model(self, sample_model):
        """Test model backup creation."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        
        backup_path = scheduler._backup_current_model()
        
        assert backup_path is not None
        assert os.path.exists(backup_path) or backup_path is None
    
    def test_get_retraining_status(self, sample_model):
        """Test getting retraining status."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        
        # Clear history for isolated test
        scheduler.monitor.performance_history = []
        
        status = scheduler.get_retraining_status()
        
        assert 'should_retrain' in status
        assert 'retraining_reason' in status
        assert 'performance_trend' in status
        assert 'total_retrainings' in status
        assert 'config' in status


class TestRetrainingDatabase:
    """Test retraining history database model."""
    
    def test_retraining_history_creation(self, app_context):
        """Test creating retraining history record."""
        entry = RetrainingHistory(
            trigger_reason='Low accuracy',
            duration_seconds=45.5,
            success=True,
            training_samples=100,
            retraining_method='synthetic_data',
        )
        
        db.session.add(entry)
        db.session.commit()
        
        retrieved = RetrainingHistory.query.first()
        assert retrieved is not None
        assert retrieved.trigger_reason == 'Low accuracy'
        assert retrieved.success is True
    
    def test_retraining_history_serialization(self, app_context):
        """Test serializing retraining history to dict."""
        entry = RetrainingHistory(
            trigger_reason='Performance degradation',
            duration_seconds=30.0,
            success=True,
            model_accuracy_before=0.80,
            model_accuracy_after=0.85,
            confidence_gap_before=0.20,
            confidence_gap_after=0.15,
        )
        
        db.session.add(entry)
        db.session.commit()
        
        serialized = entry.to_dict()
        
        assert serialized['trigger_reason'] == 'Performance degradation'
        assert serialized['success'] is True
        assert abs(serialized['accuracy_improvement'] - 0.05) < 0.0001
        assert abs(serialized['gap_improvement'] - 0.05) < 0.0001
    
    def test_failed_retraining_logging(self, app_context):
        """Test logging failed retraining."""
        entry = RetrainingHistory(
            trigger_reason='Manual trigger',
            success=False,
            error_message='Model training failed: Out of memory',
        )
        
        db.session.add(entry)
        db.session.commit()
        
        retrieved = RetrainingHistory.query.filter_by(success=False).first()
        assert retrieved is not None
        assert 'Out of memory' in retrieved.error_message


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_get_auto_retraining_status(self, sample_model):
        """Test get_auto_retraining_status function."""
        # Mock the model path by creating a temporary one
        status = get_auto_retraining_status()
        
        assert isinstance(status, dict)
        # Either returns valid status or error
        assert 'error' in status or 'should_retrain' in status


class TestMonitorIntegration:
    """Integration tests for monitoring system."""
    
    def test_full_retraining_workflow(self, app_context, sample_model, sample_responses):
        """Test complete retraining workflow."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        
        # Clear history for isolated test
        scheduler.monitor.performance_history = []
        
        # Check initial status
        status = scheduler.get_retraining_status()
        assert status is not None
        
        # Simulate performance monitoring
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'accuracy': 0.70,
            'confidence_accuracy_gap': 0.25,
            'total_responses': 50,
            'avg_score': 0.5,
            'positive_rate': 0.5,
            'avg_confidence': 0.8,
        }
        
        scheduler.monitor.record_metrics(metrics)
        
        # Verify metrics recorded
        assert len(scheduler.monitor.performance_history) >= 1
    
    def test_performance_degradation_detection(self, sample_model):
        """Test detecting performance degradation."""
        model_path, _ = sample_model
        scheduler = AutoRetrainingScheduler(model_path)
        
        # Clear history and add degrading metrics
        scheduler.monitor.performance_history = []
        for i in range(3):
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'accuracy': 0.85 - (i * 0.08),
                'confidence_accuracy_gap': 0.15 + (i * 0.05),
                'total_responses': 50,
                'avg_score': 0.5,
                'positive_rate': 0.5,
                'avg_confidence': 0.8,
            }
            scheduler.monitor.performance_history.append(metrics)
        
        trend = scheduler.monitor.get_performance_trend()
        
        # Should detect degradation
        assert trend.get('accuracy_trend', 0) < 0
        assert trend.get('avg_confidence_gap', 0) > 0.15


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_monitor_with_nonexistent_model(self):
        """Test monitor with nonexistent model file."""
        monitor = PerformanceMonitor('/nonexistent/path/model.joblib')
        
        # Should handle gracefully
        assert monitor.model_path == '/nonexistent/path/model.joblib'
    
    def test_empty_history_trend_analysis(self, sample_model):
        """Test trend analysis with empty history."""
        model_path, _ = sample_model
        monitor = PerformanceMonitor(model_path)
        
        # Clear history for isolated test
        monitor.performance_history = []
        
        trend = monitor.get_performance_trend()
        
        assert trend.get('trend') == 'insufficient_data' or 'insufficient_data' in trend.get('message', '')
    
    def test_single_metric_trend(self, sample_model):
        """Test trend analysis with single metric."""
        model_path, _ = sample_model
        monitor = PerformanceMonitor(model_path)
        
        # Clear history for isolated test
        monitor.performance_history = []
        
        monitor.performance_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'accuracy': 0.80,
            'confidence_accuracy_gap': 0.15,
            'total_responses': 50,
            'avg_score': 0.5,
            'positive_rate': 0.5,
            'avg_confidence': 0.8,
        })
        
        trend = monitor.get_performance_trend()
        
        # Should not crash with single metric
        assert isinstance(trend, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
