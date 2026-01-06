import os
import json
import pickle
from typing import Any, Dict, Optional
import re

try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False


def load_json(path: str) -> Dict[str, Any]:
    """Load JSON from path, return empty dict on error or missing file."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Save JSON data to the given path (overwrites)."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        # best-effort save; in production you'd log this
        pass


def load_model(path: str) -> Optional[Any]:
    """Load and return a model from path.
    
    Tries joblib first (preferred for scikit-learn), falls back to pickle.
    Returns None on failure.
    """
    if not os.path.exists(path):
        return None
    
    # Try joblib first (better for sklearn models)
    if HAS_JOBLIB and path.endswith('.joblib'):
        try:
            return joblib.load(path)
        except Exception:
            pass
    
    # Try pickle (fallback for .pkl files)
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None


def validate_password(password: str):
    """Validate password strength.

    Rules:
      - At least 8 characters
      - At least one uppercase letter
      - At least one digit
      - At least one special character (non-alphanumeric)

    Returns (True, '') when valid, or (False, message) when invalid.
    """
    if not isinstance(password, str):
        return False, 'Password must be a string.'

    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'

    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'

    if not re.search(r'\d', password):
        return False, 'Password must contain at least one number.'

    if not re.search(r'[^A-Za-z0-9]', password):
        return False, 'Password must contain at least one special character.'

    return True, ''


def validate_email(email: str):
    """Simple email format validation. Returns (True, '') if valid, else (False, message)."""
    if not isinstance(email, str):
        return False, 'Email must be a string.'
    email = email.strip()
    if not email:
        return False, 'Email is required.'

    # Simple regex for email validation
    import re
    pattern = r'^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, 'Invalid email address.'
    return True, ''
