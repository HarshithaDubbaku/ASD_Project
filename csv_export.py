"""
CSV Export & Analytics Module
Extension 8: Export user responses and analytics to CSV format
"""

import csv
import json
import io
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from models import db, Response, User
import numpy as np


class CSVExporter:
    """Export responses and analytics to CSV format."""
    
    def __init__(self):
        """Initialize CSV exporter."""
        pass
    
    def export_responses_to_csv(self, user_id: Optional[int] = None, 
                               include_raw_answers: bool = False) -> Tuple[str, str]:
        """
        Export responses to CSV format.
        
        Args:
            user_id: Filter by specific user (None = all users)
            include_raw_answers: Include raw questionnaire answers
            
        Returns:
            Tuple of (csv_content, filename)
        """
        try:
            if user_id:
                responses = Response.query.filter_by(user_id=user_id).all()
            else:
                responses = Response.query.all()
            
            if not responses:
                return "", "responses_empty.csv"
            
            # Prepare CSV output
            output = io.StringIO()
            
            # Define headers
            headers = [
                'Response ID', 'User ID', 'Username', 'Timestamp', 'Age', 'Gender', 
                'Ethnicity', 'Relation', 'Score', 'Prediction', 'Confidence',
                'CI Lower', 'CI Upper', 'Quality', 'SHAP Method'
            ]
            
            if include_raw_answers:
                headers.extend([f'Answer_{i+1}' for i in range(10)])
            
            headers.extend([f'Feature_{i+1}' for i in range(5)])
            
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            # Write data rows
            for response in responses:
                try:
                    user = User.query.get(response.user_id)
                    username = user.username if user else 'Unknown'
                    
                    # Parse features and answers
                    features = self._parse_json(response.features, [0, 0, 0, 0, 0])
                    answers = self._parse_json(response.answers, [0]*10) if include_raw_answers else []
                    
                    row = {
                        'Response ID': response.id,
                        'User ID': response.user_id,
                        'Username': username,
                        'Timestamp': response.timestamp.isoformat() if response.timestamp else '',
                        'Age': response.age or '',
                        'Gender': response.gender or '',
                        'Ethnicity': response.ethnicity or '',
                        'Relation': response.relation or '',
                        'Score': round(response.score, 2) if response.score else '',
                        'Prediction': response.prediction if hasattr(response, 'prediction') else '',
                        'Confidence': round(response.confidence, 2) if hasattr(response, 'confidence') and response.confidence else '',
                        'CI Lower': round(response.ci_lower, 2) if hasattr(response, 'ci_lower') and response.ci_lower else '',
                        'CI Upper': round(response.ci_upper, 2) if hasattr(response, 'ci_upper') and response.ci_upper else '',
                        'Quality': response.confidence_quality if hasattr(response, 'confidence_quality') else '',
                        'SHAP Method': response.shap_method if hasattr(response, 'shap_method') else '',
                    }
                    
                    # Add raw answers if requested
                    if include_raw_answers:
                        for i, answer in enumerate(answers[:10]):
                            row[f'Answer_{i+1}'] = answer
                    
                    # Add features
                    for i, feature in enumerate(features[:5]):
                        row[f'Feature_{i+1}'] = feature
                    
                    writer.writerow(row)
                except Exception as e:
                    print(f"Error writing row for response {response.id}: {e}")
                    continue
            
            csv_content = output.getvalue()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"responses_{timestamp}.csv"
            
            return csv_content, filename
            
        except Exception as e:
            print(f"Error exporting responses to CSV: {e}")
            return "", "responses_error.csv"
    
    def export_analytics_to_csv(self, user_id: Optional[int] = None) -> Tuple[str, str]:
        """
        Export analytics and statistics to CSV.
        
        Args:
            user_id: Filter by specific user (None = all users)
            
        Returns:
            Tuple of (csv_content, filename)
        """
        try:
            if user_id:
                responses = Response.query.filter_by(user_id=user_id).all()
            else:
                responses = Response.query.all()
            
            if not responses:
                return "", "analytics_empty.csv"
            
            # Calculate statistics
            scores = [r.score for r in responses if r.score is not None]
            predictions = [r.prediction if hasattr(r, 'prediction') else 0 for r in responses]
            confidences = [r.confidence if hasattr(r, 'confidence') and r.confidence else 0.5 for r in responses]
            
            analytics_data = {
                'Metric': [
                    'Total Responses',
                    'Average Score',
                    'Median Score',
                    'Std Dev Score',
                    'Min Score',
                    'Max Score',
                    'Positive Predictions',
                    'Negative Predictions',
                    'Positive Rate (%)',
                    'Average Confidence',
                    'Median Confidence',
                    'Min Confidence',
                    'Max Confidence',
                    'Response Date Range',
                    'Days Active',
                ],
                'Value': [
                    len(responses),
                    round(np.mean(scores), 2) if scores else 0,
                    round(np.median(scores), 2) if scores else 0,
                    round(np.std(scores), 2) if scores else 0,
                    round(np.min(scores), 2) if scores else 0,
                    round(np.max(scores), 2) if scores else 0,
                    sum(predictions),
                    len(predictions) - sum(predictions),
                    round(100 * sum(predictions) / len(predictions), 2) if predictions else 0,
                    round(np.mean(confidences), 2) if confidences else 0.5,
                    round(np.median(confidences), 2) if confidences else 0.5,
                    round(np.min(confidences), 2) if confidences else 0.5,
                    round(np.max(confidences), 2) if confidences else 0.5,
                    self._get_date_range(responses),
                    self._get_days_active(responses),
                ]
            }
            
            # Write CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['Metric', 'Value'])
            writer.writeheader()
            
            for i in range(len(analytics_data['Metric'])):
                writer.writerow({
                    'Metric': analytics_data['Metric'][i],
                    'Value': analytics_data['Value'][i]
                })
            
            csv_content = output.getvalue()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"analytics_{timestamp}.csv"
            
            return csv_content, filename
            
        except Exception as e:
            print(f"Error exporting analytics to CSV: {e}")
            return "", "analytics_error.csv"
    
    def export_feature_importance_to_csv(self, user_id: Optional[int] = None) -> Tuple[str, str]:
        """
        Export feature importance and SHAP values to CSV.
        
        Args:
            user_id: Filter by specific user (None = all users)
            
        Returns:
            Tuple of (csv_content, filename)
        """
        try:
            if user_id:
                responses = Response.query.filter_by(user_id=user_id).all()
            else:
                responses = Response.query.all()
            
            if not responses:
                return "", "features_empty.csv"
            
            feature_names = [
                'Solitude Preference',
                'Social Interaction',
                'Repetitive Behaviors',
                'Emotional Understanding',
                'Sensory Sensitivities'
            ]
            
            output = io.StringIO()
            headers = ['Response ID', 'Timestamp', 'SHAP Values', 'Feature Contributions']
            headers.extend(feature_names)
            
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            for response in responses:
                try:
                    shap_values = self._parse_json(response.shap_values, [0, 0, 0, 0, 0]) if hasattr(response, 'shap_values') else [0]*5
                    
                    row = {
                        'Response ID': response.id,
                        'Timestamp': response.timestamp.isoformat() if response.timestamp else '',
                        'SHAP Values': 'Yes' if any(shap_values) else 'No',
                        'Feature Contributions': response.shap_method if hasattr(response, 'shap_method') else '',
                    }
                    
                    for i, name in enumerate(feature_names):
                        row[name] = round(float(shap_values[i]), 4) if i < len(shap_values) else 0
                    
                    writer.writerow(row)
                except Exception as e:
                    print(f"Error writing row for response {response.id}: {e}")
                    continue
            
            csv_content = output.getvalue()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"features_{timestamp}.csv"
            
            return csv_content, filename
            
        except Exception as e:
            print(f"Error exporting features to CSV: {e}")
            return "", "features_error.csv"
    
    def export_comparison_data_to_csv(self, user_ids: List[int]) -> Tuple[str, str]:
        """
        Export comparison data between multiple users.
        
        Args:
            user_ids: List of user IDs to compare
            
        Returns:
            Tuple of (csv_content, filename)
        """
        try:
            if not user_ids:
                return "", "comparison_empty.csv"
            
            comparison_data = []
            
            for uid in user_ids:
                user = User.query.get(uid)
                if not user:
                    continue
                
                responses = Response.query.filter_by(user_id=uid).all()
                if not responses:
                    continue
                
                scores = [r.score for r in responses if r.score is not None]
                
                comparison_data.append({
                    'User ID': uid,
                    'Username': user.username,
                    'Total Responses': len(responses),
                    'Avg Score': round(np.mean(scores), 2) if scores else 0,
                    'Latest Response': max(r.timestamp for r in responses).isoformat() if responses else '',
                    'Max Score': round(np.max(scores), 2) if scores else 0,
                    'Min Score': round(np.min(scores), 2) if scores else 0,
                })
            
            output = io.StringIO()
            headers = ['User ID', 'Username', 'Total Responses', 'Avg Score', 'Latest Response', 'Max Score', 'Min Score']
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            
            for row in comparison_data:
                writer.writerow(row)
            
            csv_content = output.getvalue()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"comparison_{timestamp}.csv"
            
            return csv_content, filename
            
        except Exception as e:
            print(f"Error exporting comparison data to CSV: {e}")
            return "", "comparison_error.csv"
    
    @staticmethod
    def _parse_json(data: Any, default: Any) -> Any:
        """Safely parse JSON data."""
        if isinstance(data, str):
            try:
                return json.loads(data)
            except:
                return default
        elif isinstance(data, (list, dict)):
            return data
        else:
            return default
    
    @staticmethod
    def _get_date_range(responses: List[Response]) -> str:
        """Get date range of responses."""
        if not responses:
            return "N/A"
        
        timestamps = [r.timestamp for r in responses if r.timestamp]
        if not timestamps:
            return "N/A"
        
        earliest = min(timestamps)
        latest = max(timestamps)
        
        return f"{earliest.date()} to {latest.date()}"
    
    @staticmethod
    def _get_days_active(responses: List[Response]) -> int:
        """Calculate days active."""
        if not responses:
            return 0
        
        timestamps = [r.timestamp for r in responses if r.timestamp]
        if not timestamps:
            return 0
        
        earliest = min(timestamps)
        latest = max(timestamps)
        delta = (latest - earliest).days
        
        return max(delta, 0)


class AnalyticsGenerator:
    """Generate analytics reports from response data."""
    
    def __init__(self):
        """Initialize analytics generator."""
        self.exporter = CSVExporter()
    
    def get_user_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get summary statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Summary dictionary
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}
            
            responses = Response.query.filter_by(user_id=user_id).all()
            if not responses:
                return {
                    'user_id': user_id,
                    'username': user.username,
                    'total_responses': 0,
                    'message': 'No responses found'
                }
            
            scores = [r.score for r in responses if r.score is not None]
            predictions = [r.prediction if hasattr(r, 'prediction') else 0 for r in responses]
            
            return {
                'user_id': user_id,
                'username': user.username,
                'email': user.email,
                'total_responses': len(responses),
                'avg_score': round(np.mean(scores), 2) if scores else 0,
                'latest_score': round(responses[-1].score, 2) if responses[-1].score else 0,
                'positive_predictions': sum(predictions),
                'positive_rate': round(100 * sum(predictions) / len(predictions), 1) if predictions else 0,
                'days_active': CSVExporter._get_days_active(responses),
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_global_summary(self) -> Dict[str, Any]:
        """
        Get global analytics for all users.
        
        Returns:
            Global summary dictionary
        """
        try:
            users = User.query.all()
            responses = Response.query.all()
            
            if not responses:
                return {
                    'total_users': len(users),
                    'total_responses': 0,
                    'message': 'No responses found'
                }
            
            scores = [r.score for r in responses if r.score is not None]
            predictions = [r.prediction if hasattr(r, 'prediction') else 0 for r in responses]
            
            return {
                'total_users': len(users),
                'total_responses': len(responses),
                'avg_responses_per_user': round(len(responses) / len(users), 1) if users else 0,
                'avg_score': round(np.mean(scores), 2) if scores else 0,
                'positive_predictions': sum(predictions),
                'positive_rate': round(100 * sum(predictions) / len(predictions), 1) if predictions else 0,
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_score_distribution(self, user_id: Optional[int] = None, bins: int = 10) -> Dict[str, Any]:
        """
        Get score distribution data.
        
        Args:
            user_id: Filter by user (None = all users)
            bins: Number of histogram bins
            
        Returns:
            Distribution data
        """
        try:
            if user_id:
                responses = Response.query.filter_by(user_id=user_id).all()
            else:
                responses = Response.query.all()
            
            scores = [r.score for r in responses if r.score is not None]
            
            if not scores:
                return {'error': 'No score data'}
            
            hist, bin_edges = np.histogram(scores, bins=bins)
            
            distribution = []
            for i in range(len(hist)):
                distribution.append({
                    'bin_start': round(float(bin_edges[i]), 1),
                    'bin_end': round(float(bin_edges[i+1]), 1),
                    'count': int(hist[i]),
                })
            
            return {
                'total_samples': len(scores),
                'mean': round(float(np.mean(scores)), 2),
                'median': round(float(np.median(scores)), 2),
                'std': round(float(np.std(scores)), 2),
                'distribution': distribution,
            }
        except Exception as e:
            return {'error': str(e)}


def export_user_data_to_csv(user_id: int, include_answers: bool = False) -> Tuple[str, str]:
    """
    Convenience function to export user data to CSV.
    
    Args:
        user_id: User ID
        include_answers: Include raw questionnaire answers
        
    Returns:
        Tuple of (csv_content, filename)
    """
    exporter = CSVExporter()
    return exporter.export_responses_to_csv(user_id, include_answers)


def export_all_data_to_csv(include_answers: bool = False) -> Tuple[str, str]:
    """
    Convenience function to export all data to CSV.
    
    Args:
        include_answers: Include raw questionnaire answers
        
    Returns:
        Tuple of (csv_content, filename)
    """
    exporter = CSVExporter()
    return exporter.export_responses_to_csv(None, include_answers)


def get_user_analytics(user_id: int) -> Dict[str, Any]:
    """
    Convenience function to get user analytics.
    
    Args:
        user_id: User ID
        
    Returns:
        Analytics dictionary
    """
    generator = AnalyticsGenerator()
    return generator.get_user_summary(user_id)
