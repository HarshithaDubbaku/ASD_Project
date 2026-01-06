from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from flask_login import UserMixin
import os
from typing import Dict

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)

    def get_id(self):
        # Ensure Flask-Login receives a string id
        return str(self.id)

    # Relationship to responses
    responses = db.relationship('Response', backref='user', lazy=True, cascade='all, delete-orphan')


class Response(db.Model):
    """Store questionnaire responses per user for history and analytics."""
    __tablename__ = 'responses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(50), nullable=True)
    ethnicity = db.Column(db.String(100), nullable=True)
    relation = db.Column(db.String(50), nullable=False, default='Self')  # Parent/Self
    jaundice = db.Column(db.String(50), nullable=True)
    used_app_before = db.Column(db.String(50), nullable=True)
    answers = db.Column(db.JSON, nullable=False)  # list of 0/1 for each question
    features = db.Column(db.JSON, nullable=False)  # list of 5 features
    score = db.Column(db.Float, nullable=False)  # prediction probability (0-100)
    
    # Confidence interval fields (Extension 3)
    ci_lower = db.Column(db.Float, nullable=True)  # Lower bound of 95% CI
    ci_upper = db.Column(db.Float, nullable=True)  # Upper bound of 95% CI
    confidence_quality = db.Column(db.String(20), nullable=True)  # "High", "Medium", "Low"
    confidence_assessment = db.Column(db.String(50), nullable=True)  # Confidence level assessment
    std_error = db.Column(db.Float, nullable=True)  # Standard error of estimate
    
    # Feature attribution fields (Extension 4)
    shap_values = db.Column(db.JSON, nullable=True)  # SHAP contributions for each feature
    feature_contributions = db.Column(db.JSON, nullable=True)  # Explanation text per feature
    
    def to_dict(self):
        """Serialize response for API/export."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'age': self.age,
            'gender': self.gender,
            'relation': self.relation,
            'score': self.score,
            'features': self.features,
            'answers_count': len(self.answers) if self.answers else 0,
        }


class RetrainingHistory(db.Model):
    """Track model retraining events and performance."""
    __tablename__ = 'retraining_history'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    trigger_reason = db.Column(db.String(255), nullable=False)  # Why retraining was triggered
    duration_seconds = db.Column(db.Float, nullable=True)  # Time taken for retraining
    success = db.Column(db.Boolean, default=True, nullable=False)  # Whether retraining succeeded
    error_message = db.Column(db.Text, nullable=True)  # Error details if failed
    model_accuracy_before = db.Column(db.Float, nullable=True)  # Accuracy before retraining
    model_accuracy_after = db.Column(db.Float, nullable=True)  # Accuracy after retraining
    confidence_gap_before = db.Column(db.Float, nullable=True)  # Confidence-accuracy gap before
    confidence_gap_after = db.Column(db.Float, nullable=True)  # Confidence-accuracy gap after
    training_samples = db.Column(db.Integer, nullable=True)  # Number of samples used
    backup_model_path = db.Column(db.String(255), nullable=True)  # Path to backup of old model
    retraining_method = db.Column(db.String(50), nullable=True)  # 'synthetic_data' or 'real_data'
    additional_info = db.Column(db.JSON, nullable=True)  # Additional metadata (renamed from metadata)
    
    def to_dict(self):
        """Serialize retraining history for API."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'trigger_reason': self.trigger_reason,
            'duration_seconds': self.duration_seconds,
            'success': self.success,
            'accuracy_improvement': (self.model_accuracy_after - self.model_accuracy_before) 
                                    if (self.model_accuracy_before and self.model_accuracy_after) else None,
            'gap_improvement': (self.confidence_gap_before - self.confidence_gap_after)
                              if (self.confidence_gap_before and self.confidence_gap_after) else None,
        }



def init_db(app, users_json_path: str):
    """Create tables and migrate users from a JSON file (if present).

    The JSON is expected to be a mapping username -> password_hash_or_plain.
    If a plain password is detected it will be hashed before saving.
    """
    with app.app_context():
        db.create_all()

        # Ensure 'email' column exists for older databases; add it if missing.
        try:
            from sqlalchemy import text
            # Check columns in users table
            res = db.session.execute(text("PRAGMA table_info('users');"))
            cols = [row[1] for row in res.fetchall()]
            if 'email' not in cols:
                # SQLite supports adding a nullable column via ALTER TABLE
                db.session.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255);") )
                db.session.commit()
        except Exception:
            # ignore migration errors - best-effort
            pass

        # Try to migrate from a simple JSON users store if it exists
        try:
            import json
            if os.path.exists(users_json_path):
                with open(users_json_path, 'r', encoding='utf-8') as f:
                    data: Dict[str, str] = json.load(f) or {}

                for username, pw in data.items():
                    if not username:
                        continue
                    # Skip existing users
                    if User.query.filter_by(username=username).first():
                        continue
                    # Allow migration from either a plain password string or a dict
                    pw_val = pw
                    email_val = None
                    if isinstance(pw, dict):
                        pw_val = pw.get('password') or pw.get('pw')
                        email_val = pw.get('email')

                    # Heuristic: if password string looks hashed (contains ':' it's likely pbkdf2)
                    if isinstance(pw_val, str) and (':' in pw_val or (pw_val and pw_val.startswith('pbkdf2:'))):
                        pw_hash = pw_val
                    else:
                        pw_hash = generate_password_hash(str(pw_val))

                    user = User(username=username, password_hash=pw_hash, email=email_val)
                    db.session.add(user)
                db.session.commit()
        except Exception:
            # best-effort migration; ignore errors
            pass
