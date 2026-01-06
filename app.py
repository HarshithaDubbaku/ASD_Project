from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import os
import io
from werkzeug.security import generate_password_hash, check_password_hash
from app_utils import load_json, save_json, load_model
from models import db, User, Response, RetrainingHistory, init_db
from confidence import calculate_prediction_confidence
from shap import explain_prediction, get_feature_contribution_text
from ab_testing import ABTestFramework, load_models_for_test
from calibration import ModelCalibrator, generate_synthetic_calibration_data, calculate_prediction_calibration
from auto_retraining import AutoRetrainingScheduler, PerformanceMonitor, get_auto_retraining_status
from csv_export import CSVExporter, AnalyticsGenerator, get_user_analytics
from i18n import init_language_manager, get_current_language, set_language
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask import g


app = Flask(__name__)
# IMPORTANT: change this secret in production and keep it out of source control
app.secret_key = os.environ.get('FLASK_SECRET', 'change_this_secret')
app.jinja_env.globals['enumerate'] = enumerate
app.jinja_env.filters['enumerate'] = enumerate

# Initialize i18n
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
init_language_manager(app, os.path.join(BASE_DIR, 'translations'))


# Project paths
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
# Prefer joblib over pkl for better scikit-learn compatibility
MODEL_JOBLIB = os.path.join(BASE_DIR, 'model', 'asd_model.joblib')
MODEL_PKL = os.path.join(BASE_DIR, 'model', 'asd_model.pkl')
MODEL_PATH = MODEL_JOBLIB if os.path.exists(MODEL_JOBLIB) else MODEL_PKL

# Lazy-loaded model reference
model = None

# Note: users are persisted in SQLite via SQLAlchemy; legacy JSON store will be migrated on startup

# SQLAlchemy / Flask-Login configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# initialize db with app
db.init_app(app)

# Age-grouped question banks. Keys: 'toddler', 'early_child', 'child', 'adolescent', 'adult'
# Each list contains 10 questions so the existing mapping to model features remains valid.
questions_parent = {
    'toddler': [
        "Does your child have difficulties with social interactions?",
        "Does your child show repetitive movements or routines?",
        "Does your child have trouble responding to others' emotions?",
        "Does your child seem unusually sensitive to sounds, textures or lights?",
        "Does your child prefer to play alone rather than with others?",
        "Has your child shown delays in speech or babbling?",
        "Does your child show intense interest in a particular object or topic?",
        "Does your child become very upset when routines change?",
        "Does your child form strong attachments to particular objects?",
        "Does your child avoid or have difficulty with eye contact?"
    ],
    'early_child': [
        "Does your child have trouble making friends or joining play?",
        "Does your child repeat actions or lines of play often?",
        "Does your child struggle to understand others' feelings?",
        "Does your child have sensory over- or under-reactions?",
        "Does your child prefer solitary play?",
        "Has your child experienced speech or language delays?",
        "Does your child have very focused interests?",
        "Does your child become distressed by small routine changes?",
        "Does your child show unusual attachments to objects?",
        "Does your child avoid eye contact?"
    ],
    'child': [
        "Does your child find social situations confusing or difficult?",
        "Does your child display repetitive behaviors or rituals?",
        "Does your child have difficulty interpreting others' emotions?",
        "Does your child have sensory sensitivities (noise, textures, lights)?",
        "Does your child prefer solitary activities?",
        "Has your child had delayed speech or language development?",
        "Does your child have unusually intense interests?",
        "Does your child get very upset when routines change?",
        "Does your child develop strong attachments to items?",
        "Does your child avoid or struggle with eye contact?"
    ],
    'adolescent': [
        "Do social interactions feel confusing or tiring for your child?",
        "Does your child engage in repetitive behaviors or routines?",
        "Does your child have trouble understanding others' emotions?",
        "Does your child have sensory sensitivities that affect daily life?",
        "Does your child prefer being alone most of the time?",
        "Did your child have delayed speech as a younger child?",
        "Does your child have intense, focused interests?",
        "Does your child react strongly to changes in routine?",
        "Does your child keep unusual attachments to objects?",
        "Does your child avoid eye contact or find it uncomfortable?"
    ],
    'adult': [
        "Do you (or the person) find social interaction challenging?",
        "Do you have repetitive habits, rituals or routines?",
        "Do you find it hard to read or understand others' emotions?",
        "Do you have sensory sensitivities (sounds, textures, lights)?",
        "Do you prefer to be alone most of the time?",
        "Did you experience delayed speech or language development in childhood?",
        "Do you have very focused or intense interests?",
        "Do changes in routine cause significant distress?",
        "Do you form strong attachments to specific objects?",
        "Do you avoid eye contact or find it uncomfortable?"
    ]
}

questions_self = {
    'toddler': [
        "(Self) Do you find social interaction difficult?",
        "(Self) Do you have repetitive routines or movements?",
        "(Self) Do you struggle to understand others' emotions?",
        "(Self) Do sensory things (noise, touch) bother you a lot?",
        "(Self) Do you prefer being alone rather than socializing?",
        "(Self) Did you have delays in speech as a child?",
        "(Self) Do you have focused interests?",
        "(Self) Do you find changes to routine very upsetting?",
        "(Self) Do you tend to become attached to objects?",
        "(Self) Do you avoid making eye contact?"
    ],
    'early_child': [
        "Do you find making friends or joining play difficult?",
        "Do you repeat actions or speech patterns often?",
        "Do you struggle to interpret others' feelings?",
        "Are you sensitive to sounds, textures or lights?",
        "Do you prefer solitary activities?",
        "Did you experience speech delays?",
        "Do you have intense interests?",
        "Do small changes make you very anxious?",
        "Do you have strong attachments to objects?",
        "Do you avoid eye contact?"
    ],
    'child': [
        "Do you find social situations confusing or stressful?",
        "Do you perform repetitive behaviors or rituals?",
        "Do you have difficulty understanding others' emotions?",
        "Do sensory issues affect you?",
        "Do you often prefer to be alone?",
        "Did you have delayed speech development?",
        "Do you have unusually intense interests?",
        "Do routine changes upset you greatly?",
        "Do you form unusual attachments to items?",
        "Do you avoid eye contact?"
    ],
    'adolescent': [
        "Do social interactions feel difficult or exhausting?",
        "Do you have repetitive routines or behaviors?",
        "Do you have difficulty reading others' emotions?",
        "Do sensory sensitivities affect your daily life?",
        "Do you prefer being alone most of the time?",
        "Did you have delayed speech as a child?",
        "Do you have very focused interests?",
        "Do changes in routine cause big distress?",
        "Do you keep strong attachments to objects?",
        "Do you avoid eye contact?"
    ],
    'adult': [
        "Do you find social interaction challenging?",
        "Do you have repetitive habits or strict routines?",
        "Do you find it difficult to interpret others' emotions?",
        "Do sensory inputs (noise, smell, touch) bother you more than others?",
        "Do you prefer to be alone most of the time?",
        "Did you have delayed speech or language development?",
        "Do you have very intense and focused interests?",
        "Do unexpected changes in routine cause major distress?",
        "Do you form strong attachments to objects?",
        "Do you avoid eye contact or find it uncomfortable?"
    ]
}

# Mapping from questionnaire question indices (1-based) to the original 5 model features.
# Now using WEIGHTED mapping with (question_index, weight) tuples.
# Weights reflect diagnostic importance: higher weight = more critical for that feature.
# Feature value = (sum of weighted Yes answers) / (sum of weights) >= WEIGHTED_THRESHOLD
# Indexing: questions are 1-based (q1, q2, ..., q10)
PARENT_TO_FEATURES = {
    0: [(1, 1.0), (3, 0.9), (10, 0.95), (6, 0.7)],   
        # feature 0: Social Interaction (q1=social, q3=emotions, q10=eye contact [most critical], q6=speech delay)
    1: [(2, 1.0), (7, 0.8), (8, 0.9), (9, 0.7)],    
        # feature 1: Repetitive Behaviors (q2=repetitive [most critical], q7=interests, q8=routine distress, q9=attachments)
    2: [(3, 1.0)],             
        # feature 2: Emotional Understanding (q3 is primary)
    3: [(4, 1.0)],             
        # feature 3: Sensory Sensitivities (q4 is primary)
    4: [(5, 1.0)],             
        # feature 4: Preference for Solitude (q5 is primary)
}

SELF_TO_FEATURES = PARENT_TO_FEATURES  # same mapping for self-version; adjust if needed

# Aggregation mode for mapping answers -> model features.
# Options:
#  - 'any' : feature = 1 if any mapped question is Yes
#  - 'majority' : feature = 1 if > half of mapped questions are Yes
#  - 'weighted' : feature = 1 if (sum of weighted Yes) / (sum of weights) >= WEIGHTED_THRESHOLD
AGGREGATION_MODE = 'weighted'  # Changed from 'majority' to 'weighted' for better feature importance
WEIGHTED_THRESHOLD = 0.6  # Threshold for weighted aggregation (60% weighted score needed for feature=1)


# Home page
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/set_language/<lang_code>')
def set_language_route(lang_code):
    """Set the current language."""
    if set_language(lang_code):
        flash(g.t('settings.language_changed'), 'success')
    return redirect(request.referrer or url_for('home'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip()
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('register.html')

        # Validate password strength
        from app_utils import validate_password, validate_email
        ok, msg = validate_password(password)
        if not ok:
            flash(msg, 'error')
            return render_template('register.html')

        # Validate email
        ok_e, msg_e = validate_email(email)
        if not ok_e:
            flash(msg_e, 'error')
            return render_template('register.html')

        # Check email uniqueness
        if email and User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('register.html')

        user = User(username=username, password_hash=generate_password_hash(password), email=email or None)
        db.session.add(user)
        db.session.commit()
        flash('Registered successfully! Please login.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('user_info'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')

# User Info
@app.route('/user_info', methods=['GET', 'POST'])
@login_required
def user_info():
    # `current_user` is available from Flask-Login
    if request.method == 'POST':
        # Basic validation and normalization
        try:
            age = int(request.form.get('age', 0))
        except ValueError:
            age = 0

        session['age'] = age
        session['gender'] = request.form.get('gender', '').strip()
        session['ethnicity'] = request.form.get('ethnicity', '').strip()
        session['jaundice'] = request.form.get('jaundice', 'No')
        session['used_app_before'] = request.form.get('used_app_before', 'No')
        session['relation'] = request.form.get('relation', 'Self')
        return redirect(url_for('questionnaire'))
    return render_template('user_info.html')

# Questionnaire
@app.route('/questionnaire', methods=['GET', 'POST'])
@login_required
def questionnaire():

    relation = session.get('relation', 'Self')
    # determine age group from session (fallback to adult)
    age = session.get('age', 0)
    try:
        age = int(age)
    except Exception:
        age = 0

    def age_group(a: int) -> str:
        if a <= 3:
            return 'toddler'
        if 4 <= a <= 7:
            return 'early_child'
        if 8 <= a <= 12:
            return 'child'
        if 13 <= a <= 17:
            return 'adolescent'
        return 'adult'

    group = age_group(age)
    if relation.lower() == 'parent':
        questions = questions_parent.get(group, questions_parent['adult'])
    else:
        questions = questions_self.get(group, questions_self['adult'])

    if request.method == 'POST':
        answers = []
        for i in range(1, len(questions) + 1):
            ans = request.form.get(f'q{i}')
            if ans == 'Yes':
                answers.append(1)
            else:
                answers.append(0)

        # Map the (possibly expanded) answers into the original 5 model features
        if relation.lower() == 'parent':
            mapping = PARENT_TO_FEATURES
        else:
            mapping = SELF_TO_FEATURES

        # Aggregate answers into features according to AGGREGATION_MODE
        features = []
        for feat_idx in range(5):
            q_indices = mapping.get(feat_idx, [])
            # Collect answer values for mapped question indices (1-based -> 0-based)
            # Mapping may contain ints or (index, weight) tuples for weighted mode.
            vals = []
            for item in q_indices:
                # support both plain indices and (index, weight) pairs
                if isinstance(item, (list, tuple)) and len(item) >= 1:
                    q_idx = item[0]
                else:
                    q_idx = item
                try:
                    q_int = int(q_idx)
                except Exception:
                    continue
                if 1 <= q_int <= len(answers):
                    vals.append(answers[q_int - 1])

            if AGGREGATION_MODE == 'any':
                features.append(1 if any(vals) else 0)

            elif AGGREGATION_MODE == 'majority':
                # Strict majority: feature is 1 only when more than half of mapped questions are Yes
                if not vals:
                    features.append(0)
                else:
                    features.append(1 if sum(vals) > (len(vals) / 2.0) else 0)

            elif AGGREGATION_MODE == 'weighted':
                # Expect mapping values as list of (q_index, weight)
                total = 0.0
                weight_sum = 0.0
                for item in q_indices:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        q, w = item
                        if 1 <= q <= len(answers):
                            total += answers[q - 1] * float(w)
                            weight_sum += float(w)
                if weight_sum <= 0:
                    features.append(0)
                else:
                    features.append(1 if (total / weight_sum) >= WEIGHTED_THRESHOLD else 0)

            else:
                # Fallback to 'any'
                features.append(1 if any(vals) else 0)
        # Load model lazily
        global model
        if model is None:
            model = load_model(MODEL_PATH)

        if model is None:
            flash('Prediction model is not available. Contact administrator.', 'error')
            return redirect(url_for('user_info'))

        # Validate feature length
        try:
            # If model exposes expected input feature count, adjust features to match
            expected_n = getattr(model, 'n_features_in_', None)
            if expected_n is not None and len(features) != expected_n:
                # If there are more features than expected, truncate; if fewer, pad with zeros
                if len(features) > expected_n:
                    features = features[:expected_n]
                else:
                    features = features + [0] * (expected_n - len(features))

            if hasattr(model, 'predict_proba'):
                prob = model.predict_proba([features])[0]
                # If second column exists use it, else fallback to first
                score = (prob[1] if len(prob) > 1 else prob[0]) * 100
            else:
                pred = model.predict([features])[0]
                # model.predict returns label; map to 0/1 -> percent
                score = float(pred) * 100
            
            # Calculate confidence intervals (Extension 3)
            conf_info = calculate_prediction_confidence(model, features, method='bootstrap', confidence_level=0.95)
        except Exception as e:
            flash(f'Error during prediction: {e}', 'error')
            return redirect(url_for('user_info'))

        # Save response to database for history and analytics
        try:
            response = Response(
                user_id=current_user.id,
                age=session.get('age'),
                gender=session.get('gender'),
                ethnicity=session.get('ethnicity'),
                relation=session.get('relation', 'Self'),
                jaundice=session.get('jaundice'),
                used_app_before=session.get('used_app_before'),
                answers=answers,
                features=features,
                score=round(score, 2),
                # Confidence interval data (Extension 3)
                ci_lower=round(conf_info['ci_lower'] * 100, 2) if conf_info['ci_lower'] is not None else None,
                ci_upper=round(conf_info['ci_upper'] * 100, 2) if conf_info['ci_upper'] is not None else None,
                confidence_quality=conf_info['quality'],
                confidence_assessment=conf_info['confidence_assessment'],
                std_error=round(conf_info['std_error'], 4) if conf_info['std_error'] is not None else None
            )
            db.session.add(response)
            db.session.commit()
        except Exception as e:
            # Log but don't fail if saving response fails
            print(f"Warning: Could not save response: {e}")
        
        # Calculate SHAP explanations (Extension 4)
        shap_explanation = explain_prediction(model, features, method='tree')
        
        # Pass confidence info to template for display
        conf_display = {
            'ci_lower': round(conf_info['ci_lower'] * 100, 1) if conf_info['ci_lower'] is not None else None,
            'ci_upper': round(conf_info['ci_upper'] * 100, 1) if conf_info['ci_upper'] is not None else None,
            'quality': conf_info['quality'],
            'assessment': conf_info['confidence_assessment'],
            'interpretation': conf_info['interpretation'],
            'recommendation': conf_info['recommendation']
        }
        
        # Format SHAP explanation for display (Extension 4)
        shap_display = {
            'top_features': shap_explanation['top_features'],
            'feature_explanations': shap_explanation['explanations'],
            'feature_values': shap_explanation['feature_values'],
            'feature_names': shap_explanation['feature_names'],
            'contributions': [round(c * 100, 1) for c in shap_explanation['contributions']]
        }

        # Save SHAP data to database
        try:
            response.shap_values = shap_explanation['contributions']
            response.feature_contributions = shap_explanation['explanations']
            db.session.commit()
        except Exception as e:
            print(f"Warning: Could not save SHAP data: {e}")

        return render_template('result.html', score=round(score, 2), confidence=conf_display, shap=shap_display)
    
    return render_template('questionnaire.html', questions=questions)

@app.route('/history')
@login_required
def history():
    """Display user's past responses with scores and timestamps."""
    responses = Response.query.filter_by(user_id=current_user.id).order_by(Response.timestamp.desc()).all()
    
    # Calculate summary stats
    total_responses = len(responses)
    avg_score = sum(r.score for r in responses) / total_responses if responses else 0
    high_scores = sum(1 for r in responses if r.score >= 70)
    
    return render_template(
        'history.html',
        responses=responses,
        total_responses=total_responses,
        avg_score=round(avg_score, 2),
        high_scores=high_scores
    )

@app.route('/response/<int:response_id>')
@login_required
def view_response(response_id):
    """View details of a specific response."""
    response = Response.query.get_or_404(response_id)
    # Ensure user only views their own responses
    if response.user_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('history'))
    
    return render_template('response_detail.html', response=response)

@app.route('/ab_test', methods=['GET', 'POST'])
@login_required
def ab_test():
    """A/B testing route to compare model versions (Extension 5)."""
    results = None
    summary = None
    error = None
    
    if request.method == 'POST':
        try:
            # Get test parameters
            n_samples = int(request.form.get('n_samples', 200))
            n_samples = max(50, min(1000, n_samples))  # Clamp between 50-1000
            
            # Load models
            model_v1, model_v2 = load_models_for_test()
            if model_v1 is None:
                error = "Failed to load models"
            else:
                # Run A/B test
                framework = ABTestFramework(model_v1, model_v2)
                results = framework.run_full_comparison(framework.generate_test_data(n_samples))
                summary = framework.get_summary()
                
        except Exception as e:
            error = f"Error running A/B test: {str(e)}"
    
    return render_template('ab_test.html', results=results, summary=summary, error=error)

@app.route('/calibration', methods=['GET', 'POST'])
@login_required
def calibration():
    """Model calibration route to assess and improve probability reliability (Extension 6)."""
    calibration_results = None
    calibration_quality = None
    curve_data = None
    error = None
    
    if request.method == 'POST':
        try:
            # Load model
            try:
                model = load_model(MODEL_PATH)
            except Exception:
                error = "Failed to load model"
                return render_template('calibration.html', error=error)
            
            # Generate synthetic calibration data
            X_cal, y_cal = generate_synthetic_calibration_data(n_samples=300)
            
            # Calculate calibration metrics
            calibration_results = calculate_prediction_calibration(model, X_cal, y_cal)
            
            # Get quality assessment
            best_metrics = calibration_results['best_metrics']
            calibration_quality = {
                'method': calibration_results['best_method'],
                'ece': round(best_metrics['expected_calibration_error'], 4),
                'raw_brier': round(best_metrics['raw_brier_score'], 4),
                'calibrated_brier': round(best_metrics['calibrated_brier_score'], 4),
                'brier_improvement': round(best_metrics['brier_improvement'], 4),
                'reliability_improvement': round(best_metrics.get('reliability_improvement', 0), 4),
                'raw_accuracy': round(best_metrics['raw_accuracy'], 3),
                'calibrated_accuracy': round(best_metrics['calibrated_accuracy'], 3),
                'raw_confidence_gap': round(best_metrics['raw_confidence_gap'], 4),
                'calibrated_confidence_gap': round(best_metrics['calibrated_confidence_gap'], 4),
            }
            
            # Get isotonic metrics for comparison
            isotonic = calibration_results['isotonic']
            calibration_results_display = {
                'isotonic': {
                    'ece': round(isotonic['expected_calibration_error'], 4),
                    'brier': round(isotonic['calibrated_brier_score'], 4),
                    'improvement': round(isotonic['brier_improvement'], 4),
                    'gap': round(isotonic['calibrated_confidence_gap'], 4),
                },
                'platt': {
                    'ece': round(calibration_results['platt']['expected_calibration_error'], 4),
                    'brier': round(calibration_results['platt']['calibrated_brier_score'], 4),
                    'improvement': round(calibration_results['platt']['brier_improvement'], 4),
                    'gap': round(calibration_results['platt']['calibrated_confidence_gap'], 4),
                },
            }
            
        except Exception as e:
            error = f"Error calculating calibration: {str(e)}"
    
    return render_template('calibration.html', 
                         calibration_results=calibration_results_display if calibration_results else None,
                         calibration_quality=calibration_quality,
                         error=error)


@app.route('/retraining_monitor')
@login_required
def retraining_monitor():
    """Monitor model retraining status and performance."""
    try:
        status = get_auto_retraining_status()
    except Exception as e:
        status = {'error': str(e), 'status': 'error'}
    
    return render_template('retraining_monitor.html', status=status)


@app.route('/trigger_retraining', methods=['POST'])
@login_required
def trigger_retraining():
    """Trigger model retraining manually."""
    try:
        scheduler = AutoRetrainingScheduler()
        
        # Check if retraining is needed
        should_retrain, reason = scheduler.should_retrain()
        
        if not should_retrain:
            flash('Model is performing well. Retraining not necessary.', 'info')
            return redirect(url_for('retraining_monitor'))
        
        # Execute retraining
        result = scheduler.execute_retraining()
        
        if result['success']:
            # Log retraining to database
            log_entry = RetrainingHistory(
                trigger_reason=reason,
                duration_seconds=result.get('duration_seconds'),
                success=True,
                training_samples=len(Response.query.all()),
                retraining_method=result.get('training_method', 'synthetic_data'),
                backup_model_path=result.get('backup_path'),
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash('Model retraining completed successfully!', 'success')
        else:
            # Log failed retraining
            log_entry = RetrainingHistory(
                trigger_reason=reason,
                success=False,
                error_message=result.get('error', 'Unknown error'),
                retraining_method='synthetic_data',
            )
            db.session.add(log_entry)
            db.session.commit()
            
            flash(f'Retraining failed: {result.get("error", "Unknown error")}', 'error')
    
    except Exception as e:
        flash(f'Error triggering retraining: {str(e)}', 'error')
    
    return redirect(url_for('retraining_monitor'))


@app.route('/update_retraining_config', methods=['POST'])
@login_required
def update_retraining_config():
    """Update retraining configuration."""
    try:
        scheduler = AutoRetrainingScheduler()
        
        # Update configuration from form
        if 'accuracy_threshold' in request.form:
            scheduler.config['accuracy_threshold'] = float(request.form['accuracy_threshold']) / 100
        if 'confidence_gap_threshold' in request.form:
            scheduler.config['confidence_gap_threshold'] = float(request.form['confidence_gap_threshold']) / 100
        if 'lookback_days' in request.form:
            scheduler.config['lookback_days'] = int(request.form['lookback_days'])
        if 'min_responses_for_retraining' in request.form:
            scheduler.config['min_responses_for_retraining'] = int(request.form['min_responses_for_retraining'])
        if 'check_interval_hours' in request.form:
            scheduler.config['check_interval_hours'] = int(request.form['check_interval_hours'])
        if 'auto_retrain_enabled' in request.form:
            scheduler.config['auto_retrain_enabled'] = request.form['auto_retrain_enabled'] == 'True'
        
        scheduler.save_config()
        flash('Retraining configuration updated successfully!', 'success')
    
    except Exception as e:
        flash(f'Error updating configuration: {str(e)}', 'error')
    
    return redirect(url_for('retraining_monitor'))


@app.route('/api/retraining_status')
@login_required
def api_retraining_status():
    """API endpoint for retraining status (JSON)."""
    try:
        status = get_auto_retraining_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/export_data')
@login_required
def export_data():
    """Export user data to CSV."""
    try:
        exporter = CSVExporter()
        csv_content, filename = exporter.export_responses_to_csv(current_user.id, include_raw_answers=False)
        
        if not csv_content:
            flash('No data to export', 'warning')
            return redirect(url_for('history'))
        
        # Return CSV file
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'error')
        return redirect(url_for('history'))


@app.route('/export_analytics')
@login_required
def export_analytics():
    """Export analytics to CSV."""
    try:
        exporter = CSVExporter()
        csv_content, filename = exporter.export_analytics_to_csv(current_user.id)
        
        if not csv_content:
            flash('No analytics data to export', 'warning')
            return redirect(url_for('history'))
        
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error exporting analytics: {str(e)}', 'error')
        return redirect(url_for('history'))


@app.route('/export_features')
@login_required
def export_features():
    """Export feature importance/SHAP values to CSV."""
    try:
        exporter = CSVExporter()
        csv_content, filename = exporter.export_feature_importance_to_csv(current_user.id)
        
        if not csv_content:
            flash('No feature data to export', 'warning')
            return redirect(url_for('history'))
        
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error exporting features: {str(e)}', 'error')
        return redirect(url_for('history'))


@app.route('/api/user_analytics')
@login_required
def api_user_analytics():
    """API endpoint for user analytics (JSON)."""
    try:
        analytics = get_user_analytics(current_user.id)
        return jsonify(analytics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/score_distribution')
@login_required
def api_score_distribution():
    """API endpoint for score distribution data."""
    try:
        generator = AnalyticsGenerator()
        distribution = generator.get_score_distribution(current_user.id, bins=10)
        return jsonify(distribution)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('home'))


@login_manager.user_loader
def load_user(user_id):
    try:
        # Use the session.get API to avoid SQLAlchemy Query.get deprecation warnings
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return User.query.get(int(user_id))
    except Exception:
        return None

if __name__ == "__main__":
    # Ensure database and any legacy users are migrated
    try:
        init_db(app, USERS_FILE)
    except Exception:
        pass

    app.run(debug=True)
