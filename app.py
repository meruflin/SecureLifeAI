import os
import sys
import json
import joblib
import numpy as np
from functools import wraps
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask, render_template, request, redirect, url_for, session, 
    jsonify, flash
)

from database import (
    init_db, register_user, authenticate_user, get_user, save_profile,
    get_profile, save_application, get_applications, get_application_by_id
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['DATABASE'] = 'insurance.db'

# ─────────────────────────────────────────────────────────────────
# PROFILE NORMALIZATION
# ─────────────────────────────────────────────────────────────────

# `database.get_profile()` returns a tuple in this exact order:
# (id, user_id, gender, employment_type, height, weight, bmi,
#  smoking, alcohol, exercise_freq, medical_history, dependents,
#  family_diseases, owns_house, property_type, property_value,
#  two_wheelers, three_wheelers, four_wheelers, driving_history)

def _as_int(value, default=0):
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default

def _as_float(value, default=0.0):
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _as_str(value, default=''):
    if value is None:
        return default
    return str(value)

def profile_tuple_to_dict(profile_tuple):
    """Convert DB profile tuple to a typed dict; returns None if tuple is falsy."""
    if not profile_tuple:
        return None

    return {
        'id': _as_int(profile_tuple[0], 0),
        'user_id': _as_int(profile_tuple[1], 0),
        'gender': _as_str(profile_tuple[2], 'M'),
        'employment_type': _as_str(profile_tuple[3], 'salaried'),
        'height': _as_float(profile_tuple[4], 170.0),
        'weight': _as_float(profile_tuple[5], 70.0),
        'bmi': _as_float(profile_tuple[6], 25.0),
        'smoking': _as_int(profile_tuple[7], 0),
        'alcohol': _as_int(profile_tuple[8], 0),
        'exercise_freq': _as_str(profile_tuple[9], 'occasional'),
        'medical_history': _as_str(profile_tuple[10], 'none'),
        'dependents': _as_int(profile_tuple[11], 0),
        'family_diseases': _as_int(profile_tuple[12], 0),
        'owns_house': _as_int(profile_tuple[13], 0),
        'property_type': _as_str(profile_tuple[14], 'none'),
        'property_value': _as_float(profile_tuple[15], 0.0),
        'two_wheelers': _as_int(profile_tuple[16], 0),
        'three_wheelers': _as_int(profile_tuple[17], 0),
        'four_wheelers': _as_int(profile_tuple[18], 0),
        'driving_history': _as_str(profile_tuple[19], 'clean'),
    }

# ─────────────────────────────────────────────────────────────────
# LOGIN DECORATOR
# ─────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def csrf_token():
    """Generate CSRF token for session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = os.urandom(24).hex()
    return session['_csrf_token']

def validate_csrf_token(token):
    """Validate CSRF token from form."""
    if '_csrf_token' not in session or session['_csrf_token'] != token:
        return False
    return True

app.jinja_env.globals['csrf_token'] = csrf_token

# ─────────────────────────────────────────────────────────────────
# LOAD ML MODEL & SCALER
# ─────────────────────────────────────────────────────────────────

MODEL = None
SCALER = None
FEATURES = None

def load_model():
    global MODEL, SCALER, FEATURES
    try:
        MODEL = joblib.load('models/risk_model.pkl')
        SCALER = joblib.load('models/scaler.pkl')
        with open('models/features.json', 'r') as f:
            FEATURES = json.load(f)
    except Exception as e:
        print(f"Error loading model: {e}")
        return False
    return True

# ─────────────────────────────────────────────────────────────────
# HELPER: BUILD FEATURE VECTOR
# ─────────────────────────────────────────────────────────────────

def build_feature_vector(user_data):
    """Convert user profile to feature vector for ML model."""
    features = [
        user_data.get('age', 30),
        user_data.get('income', 500000),
        user_data.get('bmi', 25),
        user_data.get('smoking', 0),
        user_data.get('alcohol', 0),
        user_data.get('exercise_freq_code', 1),  # 0=none, 1=occasional, 2=regular
        user_data.get('medical_history_score', 0),
        user_data.get('dependents', 0),
        user_data.get('owns_house', 0),
        user_data.get('property_value_norm', 0),
        user_data.get('vehicles_total', 0),
        user_data.get('driving_score', 2),  # 0=major, 1=minor, 2=clean
        user_data.get('employment_score', 2),  # 0=unemployed, 1=self-emp, 2=salaried, 3=retired
        user_data.get('family_risk_score', 0),
    ]
    return np.array(features).reshape(1, -1)

# ─────────────────────────────────────────────────────────────────
# CORE: CALCULATE RISK SCORE
# ─────────────────────────────────────────────────────────────────

def calculate_risk_score(user_data):
    """Load model and calculate 0–100 risk score."""
    if MODEL is None or SCALER is None:
        return 50  # Default if model not loaded
    
    feature_vector = build_feature_vector(user_data)
    try:
        scaled = SCALER.transform(feature_vector)
        risk_score = MODEL.predict(scaled)[0]
        risk_score = float(max(5, min(95, risk_score)))  # Clamp 5–95
        return round(risk_score, 2)
    except Exception as e:
        print(f"Error calculating risk: {e}")
        return 50

# ─────────────────────────────────────────────────────────────────
# CORE: CALCULATE COVERAGE LIMITS
# ─────────────────────────────────────────────────────────────────

def calculate_coverage_limits(user_data, insurance_type='life'):
    """
    Calculate min/max coverage, with adjustments.
    Returns dict with risk_score, limits, multiplier, eligibility, factors, explanation.
    """
    risk_score = calculate_risk_score(user_data)
    income = float(user_data.get('income', 500000))
    
    # Risk band multipliers
    if risk_score <= 30:
        multipliers = {'life': 20, 'health': 15, 'vehicle': 10, 'property': 10}
        risk_band = 'low'
    elif risk_score <= 60:
        multipliers = {'life': 12, 'health': 10, 'vehicle': 7, 'property': 7}
        risk_band = 'medium'
    elif risk_score <= 80:
        multipliers = {'life': 6, 'health': 5, 'vehicle': 4, 'property': 4}
        risk_band = 'high'
    else:
        multipliers = {'life': 3, 'health': 2.5, 'vehicle': 2, 'property': 2}
        risk_band = 'very high'
    
    base_coverage = income * multipliers.get(insurance_type, 10)
    
    # Adjustment factors
    adjustments = []
    multiplier = 1.0
    
    # Negative adjustments
    if user_data.get('smoking', 0):
        multiplier *= 0.75
        adjustments.append({'label': 'Smoking', 'impact': 'negative', 'value': -25})
    
    if user_data.get('bmi', 25) > 35:
        multiplier *= 0.72
        adjustments.append({'label': 'Obesity (BMI > 35)', 'impact': 'negative', 'value': -28})
    elif user_data.get('bmi', 25) > 30:
        multiplier *= 0.85
        adjustments.append({'label': 'High BMI (> 30)', 'impact': 'negative', 'value': -15})
    
    if user_data.get('medical_history_score', 0) > 0:
        multiplier *= 0.80
        adjustments.append({'label': 'Medical History', 'impact': 'negative', 'value': -20})
    
    if user_data.get('driving_history') == 'major' or user_data.get('driving_score', 2) == 0:
        multiplier *= 0.70
        adjustments.append({'label': 'Major Traffic Accidents', 'impact': 'negative', 'value': -30})
    
    if user_data.get('employment_type') == 'unemployed' or user_data.get('employment_score', 2) == 0:
        multiplier *= 0.80
        adjustments.append({'label': 'Unemployed', 'impact': 'negative', 'value': -20})
    
    # Positive adjustments
    if user_data.get('owns_house', 0):
        multiplier *= 1.10
        adjustments.append({'label': 'Property Ownership', 'impact': 'positive', 'value': +10})
    
    if user_data.get('driving_history') == 'clean' or user_data.get('driving_score', 2) == 2:
        multiplier *= 1.10
        adjustments.append({'label': 'Clean Driving Record', 'impact': 'positive', 'value': +10})
    
    if user_data.get('employment_type') in ['salaried', 'retired'] or user_data.get('employment_score', 2) >= 2:
        multiplier *= 1.05
        adjustments.append({'label': 'Stable Employment', 'impact': 'positive', 'value': +5})
    
    if user_data.get('exercise_freq') == 'regular' or user_data.get('exercise_freq_code', 1) == 2:
        multiplier *= 1.05
        adjustments.append({'label': 'Regular Exercise', 'impact': 'positive', 'value': +5})
    
    # Calculate final limits
    min_coverage = base_coverage * 0.8 * multiplier
    max_coverage = base_coverage * 1.5 * multiplier
    
    eligibility_pct = max(20, min(95, 100 - risk_score))
    
    # Build explanation
    explanation = f"Your risk score is {risk_score:.0f} ({risk_band}). "
    if adjustments:
        neg_factors = [a['label'] for a in adjustments if a['impact'] == 'negative']
        pos_factors = [a['label'] for a in adjustments if a['impact'] == 'positive']
        if neg_factors:
            explanation += f"Coverage is reduced by {', '.join(neg_factors)}. "
        if pos_factors:
            explanation += f"Coverage is boosted by {', '.join(pos_factors)}. "
    explanation += f"Recommended coverage: ₹{min_coverage:,.0f} – ₹{max_coverage:,.0f}."
    
    return {
        'risk_score': risk_score,
        'min_coverage': round(min_coverage),
        'max_coverage': round(max_coverage),
        'multiplier': multiplier,
        'eligibility_pct': round(eligibility_pct),
        'factors': adjustments,
        'explanation': explanation,
        'risk_band': risk_band
    }

# ─────────────────────────────────────────────────────────────────
# CORE: EVALUATE APPLICATION
# ─────────────────────────────────────────────────────────────────

def evaluate_application(user_id, insurance_type, requested_amount, duration_years):
    """
    Evaluate and decide on insurance application.
    Returns approval/rejection with premium calculation.
    """
    user = get_user(user_id)
    profile = profile_tuple_to_dict(get_profile(user_id))
    
    # Build user data dict
    vehicles_total = (profile['two_wheelers'] + profile['three_wheelers'] + profile['four_wheelers']) if profile else 0
    user_data = {
        'age': user[2] if user else 30,
        'income': user[3] if user else 500000,
        'smoking': profile['smoking'] if profile else 0,
        'alcohol': profile['alcohol'] if profile else 0,
        'bmi': profile['bmi'] if profile else 25,
        'exercise_freq': profile['exercise_freq'] if profile else 'occasional',
        'exercise_freq_code': {'none': 0, 'occasional': 1, 'regular': 2}.get((profile['exercise_freq'] if profile else 'occasional'), 1),
        'medical_history_score': 1 if profile and profile['medical_history'] != 'none' else 0,
        'owns_house': profile['owns_house'] if profile else 0,
        'property_value_norm': (profile['property_value'] / 10000000) if profile and profile['property_value'] else 0,
        'vehicles_total': vehicles_total,
        'driving_score': {'major': 0, 'minor': 1, 'clean': 2}.get((profile['driving_history'] if profile else 'clean'), 2),
        'dependents': profile['dependents'] if profile else 0,
        'family_risk_score': 1 if profile and profile['family_diseases'] else 0,
        'employment_type': profile['employment_type'] if profile else 'salaried',
        'employment_score': {'unemployed': 0, 'self-employed': 1, 'salaried': 2, 'retired': 3}.get((profile['employment_type'] if profile else 'salaried'), 2),
        'driving_history': profile['driving_history'] if profile else 'clean',
    }
    
    limits = calculate_coverage_limits(user_data, insurance_type)
    
    # Decision logic
    if limits['min_coverage'] <= requested_amount <= limits['max_coverage']:
        status = 'approved'
        approved_amount = requested_amount
    else:
        status = 'rejected'
        approved_amount = 0
    
    # Premium calculation
    if approved_amount > 0:
        annual_rate = 0.02 + (limits['risk_score'] / 2000)
        premium = approved_amount * annual_rate * duration_years
    else:
        premium = 0
    
    # Save to database
    app_id = save_application(
        user_id, insurance_type, requested_amount, 
        approved_amount, duration_years, status, 
        limits['risk_score'], premium, limits['explanation']
    )
    
    return {
        'app_id': app_id,
        'status': status,
        'insurance_type': insurance_type,
        'requested_amount': requested_amount,
        'approved_amount': int(approved_amount),
        'min_allowed': limits['min_coverage'],
        'max_allowed': limits['max_coverage'],
        'duration_years': duration_years,
        'annual_rate': round(annual_rate * 100, 2) if approved_amount > 0 else 0,
        'premium': round(premium, 2),
        'risk_score': limits['risk_score'],
        'risk_band': limits['risk_band'],
        'explanation': limits['explanation']
    }

# ─────────────────────────────────────────────────────────────────
# ROUTES: PUBLIC
# ─────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    """Home page."""
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Sign up new user."""
    if request.method == 'POST':
        # CSRF validation
        if not validate_csrf_token(request.form.get('csrf_token', '')):
            flash('Security error. Please try again.', 'error')
            return redirect(url_for('signup'))
        
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        age_str = request.form.get('age', '')
        income_str = request.form.get('income', '')
        
        # Validation
        if not (name and email and password and age_str and income_str):
            flash('All fields are required.', 'error')
            return redirect(url_for('signup'))
        
        try:
            age = int(age_str)
            income = float(income_str)
        except ValueError:
            flash('Age must be a number, income must be a valid amount.', 'error')
            return redirect(url_for('signup'))
        
        if not (1 <= age <= 120):
            flash('Age must be between 1 and 120.', 'error')
            return redirect(url_for('signup'))
        
        if income <= 0:
            flash('Income must be greater than 0.', 'error')
            return redirect(url_for('signup'))
        
        # Register
        user_id = register_user(name, email, password, age, income)
        if user_id:
            flash('Signup successful! Please complete your profile.', 'success')
            session['user_id'] = user_id
            return redirect(url_for('complete_profile'))
        else:
            flash('Email already registered. Try logging in.', 'error')
            return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Log in user."""
    if request.method == 'POST':
        # CSRF validation
        if not validate_csrf_token(request.form.get('csrf_token', '')):
            flash('Security error. Please try again.', 'error')
            return redirect(url_for('login'))
        
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not (email and password):
            flash('Email and password are required.', 'error')
            return redirect(url_for('login'))
        
        user_id = authenticate_user(email, password)
        if user_id:
            session['user_id'] = user_id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Log out user."""
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))

# ─────────────────────────────────────────────────────────────────
# ROUTES: AUTHENTICATED
# ─────────────────────────────────────────────────────────────────

@app.route('/complete_profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """Complete user profile with health/vehicle/property data."""
    user_id = session['user_id']
    
    if request.method == 'POST':
        # CSRF validation
        if not validate_csrf_token(request.form.get('csrf_token', '')):
            flash('Security error. Please try again.', 'error')
            return redirect(url_for('complete_profile'))
        
        try:
            # Physical & Health
            gender = request.form.get('gender', 'M')
            height = float(request.form.get('height', 170))
            weight = float(request.form.get('weight', 70))
            bmi = weight / ((height / 100) ** 2)
            smoking = int(request.form.get('smoking', 0))
            alcohol = int(request.form.get('alcohol', 0))
            exercise_freq = request.form.get('exercise_freq', 'occasional')
            medical_history = request.form.get('medical_history', 'none')
            
            # Employment & Family
            employment_type = request.form.get('employment_type', 'salaried')
            dependents = int(request.form.get('dependents', 0))
            family_diseases = int(request.form.get('family_diseases', 0))
            
            # Property
            owns_house = int(request.form.get('owns_house', 0))
            property_type = request.form.get('property_type', 'none')
            property_value = float(request.form.get('property_value', 0))
            
            # Vehicles
            two_wheelers = int(request.form.get('two_wheelers', 0))
            three_wheelers = int(request.form.get('three_wheelers', 0))
            four_wheelers = int(request.form.get('four_wheelers', 0))
            
            # Driving
            driving_history = request.form.get('driving_history', 'clean')
            
            # Validation
            if not (1 <= height <= 250 and 20 <= weight <= 300):
                flash('Height/weight out of valid range.', 'error')
                return redirect(url_for('complete_profile'))
            
            if dependents < 0 or (two_wheelers + three_wheelers + four_wheelers) < 0:
                flash('Invalid dependents or vehicle count.', 'error')
                return redirect(url_for('complete_profile'))
            
            # Save profile
            save_profile(
                user_id, gender, employment_type, height, weight, bmi,
                smoking, alcohol, exercise_freq, medical_history, dependents,
                family_diseases, owns_house, property_type, property_value,
                two_wheelers, three_wheelers, four_wheelers, driving_history
            )
            
            flash('Profile completed successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        except (ValueError, KeyError) as e:
            flash(f'Error saving profile: {e}', 'error')
            return redirect(url_for('complete_profile'))
    
    profile = profile_tuple_to_dict(get_profile(user_id))
    context = {'profile': profile}
    return render_template('complete_profile.html', **context)

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard with risk score and coverage info."""
    user_id = session['user_id']
    user = get_user(user_id)
    profile = profile_tuple_to_dict(get_profile(user_id))
    
    if not user or not profile:
        flash('Profile incomplete. Please complete your profile.', 'error')
        return redirect(url_for('complete_profile'))
    
    vehicles_total = profile['two_wheelers'] + profile['three_wheelers'] + profile['four_wheelers']

    # Build user data dict
    user_data = {
        'age': user[2],
        'income': user[3],
        'smoking': profile['smoking'],
        'alcohol': profile['alcohol'],
        'bmi': profile['bmi'],
        'exercise_freq': profile['exercise_freq'],
        'exercise_freq_code': {'none': 0, 'occasional': 1, 'regular': 2}.get(profile['exercise_freq'], 1),
        'medical_history_score': 1 if profile['medical_history'] != 'none' else 0,
        'owns_house': profile['owns_house'],
        'property_value_norm': (profile['property_value'] / 10000000) if profile['property_value'] else 0,
        'vehicles_total': vehicles_total,
        'driving_score': {'major': 0, 'minor': 1, 'clean': 2}.get(profile['driving_history'], 2),
        'dependents': profile['dependents'],
        'family_risk_score': 1 if profile['family_diseases'] else 0,
        'employment_type': profile['employment_type'],
        'employment_score': {'unemployed': 0, 'self-employed': 1, 'salaried': 2, 'retired': 3}.get(profile['employment_type'], 2),
        'driving_history': profile['driving_history'],
    }
    
    # Get limits for all insurance types
    limits = {}
    for ins_type in ['life', 'health', 'vehicle', 'property']:
        limits[ins_type] = calculate_coverage_limits(user_data, ins_type)
    
    risk_score = limits['life']['risk_score']
    
    # Risk factors for chart
    risk_factors = {
        'health_risk': profile['medical_history'] != 'none',
        'financial_stability': profile['employment_type'] != 'unemployed',
        'vehicle_risk': vehicles_total > 0,
        'lifestyle': profile['smoking'] + profile['alcohol'],  # smoking + alcohol
        'dependents_burden': profile['dependents'],
    }
    
    # Factor impacts
    factor_impacts = [
        {'label': 'Age', 'impact': float(min(20, max(0, (user[2] - 25) * 0.5)))},
        {'label': 'BMI', 'impact': float(max(0, (profile['bmi'] - 25) * 2))},
        {'label': 'Smoking', 'impact': float(profile['smoking'] * 15)},
        {'label': 'Drinking', 'impact': float(profile['alcohol'] * 5)},
        {'label': 'Property Ownership', 'impact': float(-profile['owns_house'] * 8)},
        {'label': 'Employment Stability', 'impact': float(-5 if profile['employment_type'] in ('salaried', 'retired') else 0)},
    ]

    # Precompute chart data (avoid complex Jinja expressions)
    financial_score = max(0.0, min(40.0, 100.0 - (float(user[3]) / 50000.0)))
    exercise_impact = {"none": 0.0, "occasional": -5.0, "regular": -10.0}.get(profile['exercise_freq'], -5.0)
    risk_chart_values = [
        25.0 if profile['medical_history'] != 'none' else 5.0,
        financial_score,
        float((profile['smoking'] + profile['alcohol']) * 15),
        float(profile['family_diseases'] * 20),
        float(vehicles_total * 10),
    ]
    factors_chart_labels = ['Age', 'BMI', 'Smoking', 'Property', 'Exercise']
    factors_chart_values = [
        float(max(0, (user[2] - 30) * 0.5)),
        float(max(0, profile['bmi'] - 25) * 1.5),
        float(profile['smoking'] * 15),
        float(-profile['owns_house'] * 8),
        float(exercise_impact),
    ]
    
    context = {
        'user': user,
        'profile': profile,
        'risk_score': risk_score,
        'limits': limits,
        'risk_factors': risk_factors,
        'factor_impacts': factor_impacts,
        'vehicles_total': vehicles_total,
        'risk_chart_values': risk_chart_values,
        'factors_chart_labels': factors_chart_labels,
        'factors_chart_values': factors_chart_values,
    }
    
    return render_template('dashboard.html', **context)

@app.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    """Apply for insurance."""
    user_id = session['user_id']
    user = get_user(user_id)
    profile = get_profile(user_id)
    
    if not profile:
        flash('Please complete your profile first.', 'error')
        return redirect(url_for('complete_profile'))
    
    if request.method == 'POST':
        # CSRF validation
        if not validate_csrf_token(request.form.get('csrf_token', '')):
            flash('Security error. Please try again.', 'error')
            return redirect(url_for('apply'))
        
        try:
            insurance_type = request.form.get('insurance_type', 'life')
            requested_amount = float(request.form.get('requested_amount', 1000000))
            duration_years = int(request.form.get('duration_years', 5))
            
            if requested_amount <= 0 or not (1 <= duration_years <= 30):
                flash('Invalid amount or duration.', 'error')
                return redirect(url_for('apply'))
            
            result = evaluate_application(user_id, insurance_type, requested_amount, duration_years)
            session['last_application'] = result['app_id']
            
            flash(f"Application {result['status'].upper()}!", 'success' if result['status'] == 'approved' else 'error')
            return redirect(url_for('report'))
        
        except (ValueError, KeyError) as e:
            flash(f'Error processing application: {e}', 'error')
            return redirect(url_for('apply'))
    
    context = {'user': user, 'profile': profile}
    return render_template('apply.html', **context)

@app.route('/report')
@login_required
def report():
    """View last application report."""
    app_id = session.get('last_application')
    if not app_id:
        flash('No application to display.', 'error')
        return redirect(url_for('dashboard'))
    
    application = get_application_by_id(app_id)
    return render_template('report.html', application=application)

@app.route('/history')
@login_required
def history():
    """View application history."""
    user_id = session['user_id']
    applications = get_applications(user_id)
    return render_template('history.html', applications=applications)

# ─────────────────────────────────────────────────────────────────
# API: DYNAMIC DATA (JSON)
# ─────────────────────────────────────────────────────────────────

@app.route('/api/limits')
@login_required
def api_limits():
    """Get coverage limits for insurance type."""
    user_id = session['user_id']
    insurance_type = request.args.get('type', 'life')
    
    user = get_user(user_id)
    profile = profile_tuple_to_dict(get_profile(user_id))
    
    if not (user and profile):
        return jsonify({'error': 'Profile incomplete'}), 400
    
    vehicles_total = profile['two_wheelers'] + profile['three_wheelers'] + profile['four_wheelers']
    user_data = {
        'age': user[2],
        'income': user[3],
        'smoking': profile['smoking'],
        'alcohol': profile['alcohol'],
        'bmi': profile['bmi'],
        'exercise_freq': profile['exercise_freq'],
        'exercise_freq_code': {'none': 0, 'occasional': 1, 'regular': 2}.get(profile['exercise_freq'], 1),
        'medical_history_score': 1 if profile['medical_history'] != 'none' else 0,
        'owns_house': profile['owns_house'],
        'property_value_norm': (profile['property_value'] / 10000000) if profile['property_value'] else 0,
        'vehicles_total': vehicles_total,
        'driving_score': {'major': 0, 'minor': 1, 'clean': 2}.get(profile['driving_history'], 2),
        'dependents': profile['dependents'],
        'family_risk_score': 1 if profile['family_diseases'] else 0,
        'employment_type': profile['employment_type'],
        'employment_score': {'unemployed': 0, 'self-employed': 1, 'salaried': 2, 'retired': 3}.get(profile['employment_type'], 2),
        'driving_history': profile['driving_history'],
    }
    
    limits = calculate_coverage_limits(user_data, insurance_type)
    return jsonify({
        'min_coverage': limits['min_coverage'],
        'max_coverage': limits['max_coverage'],
        'risk_score': limits['risk_score'],
        'eligibility_pct': limits['eligibility_pct'],
        'explanation': limits['explanation'],
    })

@app.route('/api/dashboard_data')
@login_required
def api_dashboard_data():
    """Get full dashboard data."""
    user_id = session['user_id']
    user = get_user(user_id)
    profile = profile_tuple_to_dict(get_profile(user_id))
    
    if not (user and profile):
        return jsonify({'error': 'Profile incomplete'}), 400
    
    vehicles_total = profile['two_wheelers'] + profile['three_wheelers'] + profile['four_wheelers']
    user_data = {
        'age': user[2],
        'income': user[3],
        'smoking': profile['smoking'],
        'alcohol': profile['alcohol'],
        'bmi': profile['bmi'],
        'exercise_freq': profile['exercise_freq'],
        'exercise_freq_code': {'none': 0, 'occasional': 1, 'regular': 2}.get(profile['exercise_freq'], 1),
        'medical_history_score': 1 if profile['medical_history'] != 'none' else 0,
        'owns_house': profile['owns_house'],
        'property_value_norm': (profile['property_value'] / 10000000) if profile['property_value'] else 0,
        'vehicles_total': vehicles_total,
        'driving_score': {'major': 0, 'minor': 1, 'clean': 2}.get(profile['driving_history'], 2),
        'dependents': profile['dependents'],
        'family_risk_score': 1 if profile['family_diseases'] else 0,
        'employment_type': profile['employment_type'],
        'employment_score': {'unemployed': 0, 'self-employed': 1, 'salaried': 2, 'retired': 3}.get(profile['employment_type'], 2),
        'driving_history': profile['driving_history'],
    }
    
    risk_score = calculate_risk_score(user_data)
    factors = []
    if profile['smoking']:
        factors.append({'label': 'Smoker', 'impact': 'negative'})
    if profile['bmi'] > 30:
        factors.append({'label': 'High BMI', 'impact': 'negative'})
    if profile['owns_house']:
        factors.append({'label': 'Property Owner', 'impact': 'positive'})
    
    limits_by_type = {}
    for ins_type in ['life', 'health', 'vehicle', 'property']:
        limits_by_type[ins_type] = calculate_coverage_limits(user_data, ins_type)
    
    return jsonify({
        'risk_score': risk_score,
        'factors': factors,
        'coverage_limits_by_type': limits_by_type,
        'profile_complete': True,
    })

# ─────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('home.html'), 404

@app.errorhandler(500)
def server_error(e):
    flash('Internal server error.', 'error')
    # Use a normal redirect (302). Returning a redirect body with HTTP 500
    # often shows a "Redirecting..." page instead of navigating.
    return redirect(url_for('home'))

# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Ensure models directory exists
    os.makedirs('models', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Train model if not exists
    if not os.path.exists('models/risk_model.pkl'):
        print("Training ML model...")
        from models.train_model import train
        train()
    
    # Load model
    print("Loading ML model...")
    load_model()
    
    # Initialize database
    print("Initializing database...")
    init_db()
    
    print("SecureLifeAI starting on http://localhost:5000")
    app.run(debug=False, port=5000, host='localhost')
