import os
from app_utils import load_model, HAS_JOBLIB
from app import MODEL_PATH
print('HAS_JOBLIB:', HAS_JOBLIB)
print('MODEL_PATH:', MODEL_PATH)
print('MODEL_PATH exists:', os.path.exists(MODEL_PATH))
model = load_model(MODEL_PATH)
print('Loaded model is None:', model is None)
try:
    print('Model type:', type(model))
    print('Has predict_proba:', hasattr(model, 'predict_proba'))
    print('n_features_in_:', getattr(model, 'n_features_in_', None))
except Exception as e:
    print('Error inspecting model:', e)
