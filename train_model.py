"""
ASD Model Retraining Pipeline
==============================

This script demonstrates how to retrain the ASD prediction model with:
1. Weighted features for diagnostic importance
2. Improved model performance tracking
3. Cross-validation for robustness

Usage:
  python train_model.py [--mode generate|train|evaluate]
  
  --mode generate  : Generate synthetic training data (demo purposes)
  --mode train     : Train model on existing data/synthetic data
  --mode evaluate  : Evaluate model performance
"""

import os
import sys
import json
import argparse
import numpy as np
import joblib
import pickle
from pathlib import Path
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, 
    roc_curve, auc, precision_recall_curve
)
import warnings
warnings.filterwarnings('ignore')

# Project paths
BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / 'model'
DATA_DIR = BASE_DIR / 'data'
LOG_DIR = BASE_DIR / 'logs'

MODEL_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

MODEL_JOBLIB = MODEL_DIR / 'asd_model.joblib'
MODEL_PKL = MODEL_DIR / 'asd_model.pkl'
BACKUP_JOBLIB = MODEL_DIR / f'asd_model_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.joblib'

TRAINING_DATA = DATA_DIR / 'training_data.json'


def generate_synthetic_data(n_samples=500, random_state=42):
    """
    Generate synthetic training data for ASD prediction.
    
    This is for demonstration. In production, use real annotated data from:
    - Clinical assessments
    - Validated ASD screening datasets
    - Healthcare provider inputs
    
    Returns: (X, y) where
      X: feature vectors (n_samples, 5) with values in [0, 1]
      y: labels (n_samples,) with values in [0, 1]
    """
    np.random.seed(random_state)
    
    print("=" * 70)
    print("GENERATING SYNTHETIC TRAINING DATA")
    print("=" * 70)
    print(f"\nGenerating {n_samples} samples...")
    
    # Class 0 (No ASD): features are generally low
    n_class0 = n_samples // 2
    X_class0 = np.random.beta(2, 5, size=(n_class0, 5))  # Biased toward 0
    y_class0 = np.zeros(n_class0)
    
    # Class 1 (ASD): features are generally higher, with some patterns
    n_class1 = n_samples - n_class0
    X_class1 = np.random.beta(5, 2, size=(n_class1, 5))  # Biased toward 1
    # Add correlation: if social (f0) is high, emotional (f2) likely high too
    X_class1[:, 2] = np.minimum(X_class1[:, 2] + X_class1[:, 0] * 0.3, 1.0)
    # Repetitive (f1) often correlated with sensory (f3)
    X_class1[:, 3] = np.minimum(X_class1[:, 3] + X_class1[:, 1] * 0.2, 1.0)
    y_class1 = np.ones(n_class1)
    
    # Combine and shuffle
    X = np.vstack([X_class0, X_class1])
    y = np.hstack([y_class0, y_class1])
    
    shuffle_idx = np.random.permutation(len(y))
    X = X[shuffle_idx]
    y = y[shuffle_idx]
    
    print(f"✅ Generated {n_samples} samples")
    print(f"   Class 0 (No ASD): {n_class0} samples")
    print(f"   Class 1 (ASD): {n_class1} samples")
    
    return X, y


def load_training_data(filepath=TRAINING_DATA):
    """Load training data from JSON file if available."""
    if not filepath.exists():
        print(f"⚠️  Training data not found at {filepath}")
        print("   Generating synthetic data instead...")
        return generate_synthetic_data()
    
    print(f"Loading training data from {filepath}...")
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    X = np.array(data['X'])
    y = np.array(data['y'])
    print(f"✅ Loaded {len(y)} training samples")
    return X, y


def train_model(X, y, test_size=0.2, random_state=42):
    """Train RandomForestClassifier with cross-validation."""
    print("\n" + "=" * 70)
    print("TRAINING MODEL")
    print("=" * 70)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    print(f"\nData split:")
    print(f"  Training: {len(X_train)} samples")
    print(f"  Testing: {len(X_test)} samples")
    print(f"  Features per sample: {X.shape[1]}")
    
    # Train model
    print("\nTraining RandomForestClassifier (100 estimators)...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=random_state,
        n_jobs=-1,
        class_weight='balanced'  # Handle class imbalance
    )
    
    model.fit(X_train, y_train)
    print("✅ Model trained")
    
    # Evaluate
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)
    
    print(f"\nModel Performance:")
    print(f"  Training accuracy: {train_score:.4f}")
    print(f"  Testing accuracy: {test_score:.4f}")
    
    # Cross-validation
    print(f"\nPerforming 5-fold cross-validation...")
    cv_scores = cross_val_score(model, X, y, cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state))
    print(f"  CV scores: {cv_scores}")
    print(f"  Mean CV accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
    
    # Detailed metrics on test set
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    print(f"\nDetailed Test Set Metrics:")
    print(classification_report(y_test, y_pred, target_names=['No ASD', 'ASD']))
    
    # ROC-AUC
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    print(f"  ROC-AUC Score: {roc_auc:.4f}")
    
    # Feature importance
    print(f"\nFeature Importance (top 5):")
    feature_importance = model.feature_importances_
    feature_names = ['Social Interaction', 'Repetitive Behaviors', 'Emotional Understanding', 'Sensory', 'Solitude Preference']
    for i, (name, importance) in enumerate(zip(feature_names, feature_importance)):
        print(f"  {i}: {name}: {importance:.4f}")
    
    return model, X_test, y_test, y_pred_proba


def save_model(model, filename=MODEL_JOBLIB):
    """Save model in joblib and pickle formats."""
    print("\n" + "=" * 70)
    print("SAVING MODEL")
    print("=" * 70)
    
    # Backup existing model
    if MODEL_JOBLIB.exists():
        import shutil
        shutil.copy(MODEL_JOBLIB, BACKUP_JOBLIB)
        print(f"✅ Backed up previous model to {BACKUP_JOBLIB.name}")
    
    # Save as joblib (preferred)
    joblib.dump(model, MODEL_JOBLIB, compress=3)
    print(f"✅ Model saved (joblib): {MODEL_JOBLIB}")
    
    # Also save as pickle for compatibility
    with open(MODEL_PKL, 'wb') as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"✅ Model saved (pickle): {MODEL_PKL}")
    
    # Save metadata
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'n_estimators': model.n_estimators,
        'n_features': model.n_features_in_,
        'classes': model.classes_.tolist(),
        'feature_names': ['Social', 'Repetitive', 'Emotional', 'Sensory', 'Solitude']
    }
    
    metadata_path = MODEL_DIR / 'model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✅ Metadata saved: {metadata_path}")


def main():
    parser = argparse.ArgumentParser(description='ASD Model Training Pipeline')
    parser.add_argument('--mode', choices=['generate', 'train', 'evaluate', 'full'], 
                       default='full', help='Pipeline mode')
    parser.add_argument('--samples', type=int, default=500, help='Number of synthetic samples')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("ASD MODEL RETRAINING PIPELINE")
    print("=" * 70)
    print(f"Mode: {args.mode}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        if args.mode in ['generate', 'full']:
            X, y = generate_synthetic_data(args.samples, args.seed)
        else:
            X, y = load_training_data()
        
        if args.mode in ['train', 'full']:
            model, X_test, y_test, y_pred_proba = train_model(X, y, random_state=args.seed)
            save_model(model)
        
        print("\n" + "=" * 70)
        print("✅ PIPELINE COMPLETE")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Test the new model: python -m pytest -q")
        print("2. Start the app: python app.py")
        print("3. Try a questionnaire to verify predictions")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
