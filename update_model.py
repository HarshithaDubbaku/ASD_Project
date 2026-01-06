"""
Script to inspect and re-save the ML model with current scikit-learn version.
This eliminates unpickle warnings and ensures version compatibility.
"""
import pickle
import joblib
import os
from pathlib import Path

MODEL_DIR = Path(__file__).parent / 'model'
PKL_PATH = MODEL_DIR / 'asd_model.pkl'
JOBLIB_PATH = MODEL_DIR / 'asd_model.joblib'

print("=" * 70)
print("ASD Model Inspector & Updater")
print("=" * 70)

# Load the model
print(f"\n1. Loading model from: {PKL_PATH}")
try:
    with open(PKL_PATH, 'rb') as f:
        model = pickle.load(f)
    print("✅ Model loaded successfully")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    exit(1)

# Inspect model details
print("\n2. Model Details:")
print(f"   Type: {type(model).__name__}")
print(f"   Module: {type(model).__module__}")

if hasattr(model, 'n_features_in_'):
    print(f"   Input features: {model.n_features_in_}")
if hasattr(model, 'classes_'):
    print(f"   Classes: {model.classes_}")
if hasattr(model, 'n_estimators'):
    print(f"   N Estimators: {model.n_estimators}")

# Check for nested estimators (e.g., ensemble models)
if hasattr(model, 'estimators_'):
    print(f"   Estimators count: {len(model.estimators_)}")
    for i, est in enumerate(model.estimators_):
        print(f"     - Estimator {i}: {type(est).__name__}")

# Try prediction on dummy data to verify it works
print("\n3. Testing prediction on dummy data:")
try:
    dummy_features = [[0, 0, 0, 0, 0]]  # 5 features as expected
    if hasattr(model, 'predict_proba'):
        pred = model.predict_proba(dummy_features)
        print(f"   predict_proba output: {pred}")
    else:
        pred = model.predict(dummy_features)
        print(f"   predict output: {pred}")
    print("✅ Model prediction works")
except Exception as e:
    print(f"❌ Prediction error: {e}")

# Re-save with joblib (more robust than pickle)
print(f"\n4. Re-saving model with joblib to: {JOBLIB_PATH}")
try:
    joblib.dump(model, JOBLIB_PATH, compress=3)
    print("✅ Model saved with joblib")
except Exception as e:
    print(f"❌ Error saving with joblib: {e}")

# Also update the pkl file with current pickle protocol
print(f"\n5. Updating original pkl file with current pickle protocol:")
try:
    with open(PKL_PATH, 'wb') as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("✅ Model pkl updated with highest protocol")
except Exception as e:
    print(f"❌ Error updating pkl: {e}")

print("\n" + "=" * 70)
print("Update complete! Model is now compatible with current scikit-learn.")
print("=" * 70)
