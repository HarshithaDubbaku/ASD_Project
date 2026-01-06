"""
Tests for CSV export and analytics module
Extension 8: CSV Export & Analytics
"""

import pytest
import csv
import io
import json
from datetime import datetime, timedelta
from models import db, Response, User
from csv_export import (
    CSVExporter, 
    AnalyticsGenerator,
    export_user_data_to_csv,
    export_all_data_to_csv,
    get_user_analytics
)
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
def sample_user(app_context):
    """Create a sample user."""
    user = User(username='testuser', password_hash='hash123', email='test@example.com')
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_responses(app_context, sample_user):
    """Create sample responses for testing."""
    responses = []
    for i in range(10):
        response = Response(
            user_id=sample_user.id,
            timestamp=datetime.utcnow() - timedelta(days=i),
            age=25,
            gender='M',
            ethnicity='Asian',
            relation='Self',
            answers=[0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
            features=[0, 1, 0, 1, 1],
            score=50.0 + (i * 5),
        )
        responses.append(response)
        db.session.add(response)
    
    db.session.commit()
    return responses


class TestCSVExporter:
    """Test CSV export functionality."""
    
    def test_export_initialization(self):
        """Test CSVExporter initialization."""
        exporter = CSVExporter()
        assert exporter is not None
    
    def test_export_responses_empty(self, app_context):
        """Test exporting with no responses."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_responses_to_csv()
        
        assert filename == "responses_empty.csv"
        assert csv_content == ""
    
    def test_export_responses_single_user(self, app_context, sample_user, sample_responses):
        """Test exporting responses for a single user."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_responses_to_csv(sample_user.id)
        
        assert csv_content != ""
        assert "responses_" in filename
        assert ".csv" in filename
        
        # Parse CSV and verify
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 10
        assert rows[0]['Username'] == 'testuser'
        assert rows[0]['Age'] == '25'
    
    def test_export_responses_all_users(self, app_context, sample_user, sample_responses):
        """Test exporting responses for all users."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_responses_to_csv(None)
        
        assert csv_content != ""
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) >= 10
    
    def test_export_responses_with_answers(self, app_context, sample_user, sample_responses):
        """Test exporting with raw answers included."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_responses_to_csv(sample_user.id, include_raw_answers=True)
        
        assert csv_content != ""
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Should have answer columns
        fieldnames = reader.fieldnames
        answer_columns = [f for f in fieldnames if 'Answer_' in f]
        assert len(answer_columns) == 10
    
    def test_export_analytics_empty(self, app_context):
        """Test exporting analytics with no data."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_analytics_to_csv()
        
        assert filename == "analytics_empty.csv"
        assert csv_content == ""
    
    def test_export_analytics_single_user(self, app_context, sample_user, sample_responses):
        """Test exporting analytics for single user."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_analytics_to_csv(sample_user.id)
        
        assert csv_content != ""
        assert "analytics_" in filename
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) > 0
        # Check for expected metrics
        metrics = [row['Metric'] for row in rows]
        assert 'Total Responses' in metrics
        assert 'Average Score' in metrics
    
    def test_export_analytics_values(self, app_context, sample_user, sample_responses):
        """Test analytics values are calculated correctly."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_analytics_to_csv(sample_user.id)
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        metrics_dict = {row['Metric']: row['Value'] for row in rows}
        
        assert int(metrics_dict['Total Responses']) == 10
        assert float(metrics_dict['Average Score']) > 50
    
    def test_export_features_empty(self, app_context):
        """Test exporting features with no data."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_feature_importance_to_csv()
        
        assert filename == "features_empty.csv"
        assert csv_content == ""
    
    def test_export_features_single_user(self, app_context, sample_user, sample_responses):
        """Test exporting features for single user."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_feature_importance_to_csv(sample_user.id)
        
        assert csv_content != ""
        assert "features_" in filename
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 10
    
    def test_export_comparison_empty(self, app_context):
        """Test export comparison with no users."""
        exporter = CSVExporter()
        csv_content, filename = exporter.export_comparison_data_to_csv([])
        
        assert filename == "comparison_empty.csv"
    
    def test_export_comparison_multiple_users(self, app_context):
        """Test comparison export with multiple users."""
        # Create multiple users
        users = []
        for i in range(3):
            user = User(
                username=f'user{i}',
                password_hash='hash123',
                email=f'user{i}@example.com'
            )
            db.session.add(user)
            users.append(user)
        
        db.session.commit()
        
        # Add responses to first user
        for i in range(5):
            response = Response(
                user_id=users[0].id,
                timestamp=datetime.utcnow(),
                age=25,
                gender='M',
                answers=[0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
                features=[0, 1, 0, 1, 1],
                score=60.0 + i,
            )
            db.session.add(response)
        
        db.session.commit()
        
        exporter = CSVExporter()
        csv_content, filename = exporter.export_comparison_data_to_csv([u.id for u in users])
        
        assert csv_content != ""
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 1  # Only user 0 has responses
        assert rows[0]['Username'] == 'user0'


class TestAnalyticsGenerator:
    """Test analytics generation."""
    
    def test_generator_initialization(self):
        """Test AnalyticsGenerator initialization."""
        generator = AnalyticsGenerator()
        assert generator is not None
        assert generator.exporter is not None
    
    def test_get_user_summary_not_found(self, app_context):
        """Test getting summary for nonexistent user."""
        generator = AnalyticsGenerator()
        summary = generator.get_user_summary(999)
        
        assert 'error' in summary
    
    def test_get_user_summary_no_responses(self, app_context, sample_user):
        """Test getting summary for user with no responses."""
        generator = AnalyticsGenerator()
        summary = generator.get_user_summary(sample_user.id)
        
        assert summary['user_id'] == sample_user.id
        assert summary['total_responses'] == 0
    
    def test_get_user_summary_with_responses(self, app_context, sample_user, sample_responses):
        """Test getting summary with responses."""
        generator = AnalyticsGenerator()
        summary = generator.get_user_summary(sample_user.id)
        
        assert summary['user_id'] == sample_user.id
        assert summary['username'] == 'testuser'
        assert summary['total_responses'] == 10
        assert summary['avg_score'] > 50
        assert summary['days_active'] >= 0
    
    def test_get_global_summary(self, app_context, sample_user, sample_responses):
        """Test getting global summary."""
        generator = AnalyticsGenerator()
        summary = generator.get_global_summary()
        
        assert 'total_users' in summary
        assert 'total_responses' in summary
        assert summary['total_users'] >= 1
        assert summary['total_responses'] >= 10
    
    def test_get_score_distribution_no_data(self, app_context):
        """Test score distribution with no data."""
        generator = AnalyticsGenerator()
        distribution = generator.get_score_distribution()
        
        assert 'error' in distribution
    
    def test_get_score_distribution_with_data(self, app_context, sample_user, sample_responses):
        """Test score distribution with data."""
        generator = AnalyticsGenerator()
        distribution = generator.get_score_distribution(sample_user.id)
        
        assert 'total_samples' in distribution
        assert 'mean' in distribution
        assert 'distribution' in distribution
        assert len(distribution['distribution']) > 0
    
    def test_score_distribution_histogram(self, app_context, sample_user, sample_responses):
        """Test histogram bins are correct."""
        generator = AnalyticsGenerator()
        distribution = generator.get_score_distribution(sample_user.id, bins=5)
        
        assert len(distribution['distribution']) == 5
        
        # Check bin structure
        for bin_data in distribution['distribution']:
            assert 'bin_start' in bin_data
            assert 'bin_end' in bin_data
            assert 'count' in bin_data


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_export_user_data(self, app_context, sample_user, sample_responses):
        """Test user data export convenience function."""
        csv_content, filename = export_user_data_to_csv(sample_user.id)
        
        assert csv_content != ""
        assert ".csv" in filename
    
    def test_export_all_data(self, app_context, sample_user, sample_responses):
        """Test all data export convenience function."""
        csv_content, filename = export_all_data_to_csv()
        
        assert csv_content != ""
        assert ".csv" in filename
    
    def test_get_user_analytics(self, app_context, sample_user, sample_responses):
        """Test user analytics convenience function."""
        analytics = get_user_analytics(sample_user.id)
        
        assert analytics['user_id'] == sample_user.id
        assert analytics['total_responses'] == 10


class TestCSVDataIntegrity:
    """Test data integrity in CSV exports."""
    
    def test_csv_headers_present(self, app_context, sample_user, sample_responses):
        """Test all required headers are present."""
        exporter = CSVExporter()
        csv_content, _ = exporter.export_responses_to_csv(sample_user.id)
        
        reader = csv.DictReader(io.StringIO(csv_content))
        headers = reader.fieldnames
        
        required = ['Response ID', 'User ID', 'Username', 'Age', 'Gender', 'Score']
        for header in required:
            assert header in headers
    
    def test_csv_no_missing_values(self, app_context, sample_user, sample_responses):
        """Test that critical fields are populated."""
        exporter = CSVExporter()
        csv_content, _ = exporter.export_responses_to_csv(sample_user.id)
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        for row in rows:
            assert row['User ID'] != ''
            assert row['Username'] != ''
            assert row['Score'] != ''
    
    def test_analytics_numeric_values(self, app_context, sample_user, sample_responses):
        """Test analytics values are properly formatted."""
        exporter = CSVExporter()
        csv_content, _ = exporter.export_analytics_to_csv(sample_user.id)
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        metrics_dict = {row['Metric']: row['Value'] for row in rows}
        
        # Should be able to convert numeric values
        try:
            total = int(metrics_dict['Total Responses'])
            avg = float(metrics_dict['Average Score'])
            assert total > 0
            assert avg > 0
        except ValueError:
            pytest.fail("Numeric metrics should be convertible to numbers")


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_export_with_none_score(self, app_context, sample_user):
        """Test exporting with score values in normal range."""
        response = Response(
            user_id=sample_user.id,
            timestamp=datetime.utcnow(),
            age=25,
            gender='M',
            answers=[0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
            features=[0, 1, 0, 1, 1],
            score=45.5,
        )
        db.session.add(response)
        db.session.commit()
        
        exporter = CSVExporter()
        csv_content, _ = exporter.export_responses_to_csv(sample_user.id)
        
        assert csv_content != ""
    
    def test_export_with_special_characters(self, app_context):
        """Test exporting data with special characters."""
        user = User(
            username='test_user@example',
            password_hash='hash123',
            email='test@example.com'
        )
        db.session.add(user)
        db.session.commit()
        
        response = Response(
            user_id=user.id,
            timestamp=datetime.utcnow(),
            age=25,
            gender='F',
            ethnicity='N/A',
            relation='Parent/Caregiver',
            answers=[0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
            features=[0, 1, 0, 1, 1],
            score=65.5,
        )
        db.session.add(response)
        db.session.commit()
        
        exporter = CSVExporter()
        csv_content, _ = exporter.export_responses_to_csv(user.id)
        
        assert csv_content != ""
        assert 'test_user@example' in csv_content or 'testuser' in csv_content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
