import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'insurance.db'

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            age INTEGER,
            income REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE REFERENCES users(id),
            gender TEXT,
            employment_type TEXT,
            height REAL,
            weight REAL,
            bmi REAL,
            smoking INTEGER,
            alcohol INTEGER,
            exercise_freq TEXT,
            medical_history TEXT,
            dependents INTEGER,
            family_diseases INTEGER,
            owns_house INTEGER,
            property_type TEXT,
            property_value REAL,
            two_wheelers INTEGER,
            three_wheelers INTEGER,
            four_wheelers INTEGER,
            driving_history TEXT
        )
    ''')
    
    # Applications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            insurance_type TEXT,
            requested_amount REAL,
            approved_amount REAL,
            duration_years INTEGER,
            status TEXT,
            risk_score REAL,
            premium REAL,
            ai_explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────────
# USER FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def register_user(name, email, password, age, income):
    """
    Register a new user.
    Returns user_id on success, None on failure (duplicate email).
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, age, income)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, password_hash, age, income))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        return user_id
    except sqlite3.IntegrityError:
        # Email already exists
        return None

def authenticate_user(email, password):
    """
    Authenticate user with email and password.
    Returns user_id on success, None on failure.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, password_hash FROM users WHERE email = ?', (email,))
    result = cursor.fetchone()
    conn.close()
    
    if result and check_password_hash(result['password_hash'], password):
        return result['id']
    return None

def get_user(user_id):
    """Get user by ID. Returns tuple: (id, name, age, income, email, created_at)."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, age, income, email, created_at FROM users WHERE id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return tuple(result) if result else None

def get_user_email(user_id):
    """Get user email by ID."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

# ─────────────────────────────────────────────────────────────────
# PROFILE FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def save_profile(user_id, gender, employment_type, height, weight, bmi,
                 smoking, alcohol, exercise_freq, medical_history, dependents,
                 family_diseases, owns_house, property_type, property_value,
                 two_wheelers, three_wheelers, four_wheelers, driving_history):
    """Save or update user profile."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if profile exists
    cursor.execute('SELECT id FROM profiles WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        # Update
        cursor.execute('''
            UPDATE profiles SET
                gender = ?, employment_type = ?, height = ?, weight = ?, bmi = ?,
                smoking = ?, alcohol = ?, exercise_freq = ?, medical_history = ?,
                dependents = ?, family_diseases = ?, owns_house = ?, property_type = ?,
                property_value = ?, two_wheelers = ?, three_wheelers = ?,
                four_wheelers = ?, driving_history = ?
            WHERE user_id = ?
        ''', (gender, employment_type, height, weight, bmi,
              smoking, alcohol, exercise_freq, medical_history,
              dependents, family_diseases, owns_house, property_type,
              property_value, two_wheelers, three_wheelers,
              four_wheelers, driving_history, user_id))
    else:
        # Insert
        cursor.execute('''
            INSERT INTO profiles (
                user_id, gender, employment_type, height, weight, bmi,
                smoking, alcohol, exercise_freq, medical_history, dependents,
                family_diseases, owns_house, property_type, property_value,
                two_wheelers, three_wheelers, four_wheelers, driving_history
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, gender, employment_type, height, weight, bmi,
              smoking, alcohol, exercise_freq, medical_history, dependents,
              family_diseases, owns_house, property_type, property_value,
              two_wheelers, three_wheelers, four_wheelers, driving_history))
    
    conn.commit()
    conn.close()

def get_profile(user_id):
    """
    Get user profile by user_id.
    Returns tuple: (id, user_id, gender, employment_type, height, weight, bmi,
                    smoking, alcohol, exercise_freq, medical_history, dependents,
                    family_diseases, owns_house, property_type, property_value,
                    two_wheelers, three_wheelers, four_wheelers, driving_history)
    Returns None if not found.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, user_id, gender, employment_type, height, weight, bmi,
               smoking, alcohol, exercise_freq, medical_history, dependents,
               family_diseases, owns_house, property_type, property_value,
               two_wheelers, three_wheelers, four_wheelers, driving_history
        FROM profiles WHERE user_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return tuple(result) if result else None

# ─────────────────────────────────────────────────────────────────
# APPLICATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def save_application(user_id, insurance_type, requested_amount, approved_amount,
                     duration_years, status, risk_score, premium, ai_explanation):
    """
    Save insurance application.
    Returns application_id.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO applications (
            user_id, insurance_type, requested_amount, approved_amount,
            duration_years, status, risk_score, premium, ai_explanation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, insurance_type, requested_amount, approved_amount,
          duration_years, status, risk_score, premium, ai_explanation))
    
    conn.commit()
    app_id = cursor.lastrowid
    conn.close()
    
    return app_id

def get_application_by_id(app_id):
    """
    Get application by ID.
    Returns dict with all fields or None.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, user_id, insurance_type, requested_amount, approved_amount,
               duration_years, status, risk_score, premium, ai_explanation,
               created_at
        FROM applications WHERE id = ?
    ''', (app_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'id': result[0],
            'user_id': result[1],
            'insurance_type': result[2],
            'requested_amount': result[3],
            'approved_amount': result[4],
            'duration_years': result[5],
            'status': result[6],
            'risk_score': result[7],
            'premium': result[8],
            'ai_explanation': result[9],
            'created_at': result[10],
        }
    return None

def get_applications(user_id):
    """
    Get all applications for a user.
    Returns list of dicts.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, user_id, insurance_type, requested_amount, approved_amount,
               duration_years, status, risk_score, premium, ai_explanation,
               created_at
        FROM applications WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    applications = []
    for row in results:
        applications.append({
            'id': row[0],
            'user_id': row[1],
            'insurance_type': row[2],
            'requested_amount': row[3],
            'approved_amount': row[4],
            'duration_years': row[5],
            'status': row[6],
            'risk_score': row[7],
            'premium': row[8],
            'ai_explanation': row[9],
            'created_at': row[10],
        })
    
    return applications

def get_latest_application(user_id):
    """Get latest application for a user."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, user_id, insurance_type, requested_amount, approved_amount,
               duration_years, status, risk_score, premium, ai_explanation,
               created_at
        FROM applications WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'id': result[0],
            'user_id': result[1],
            'insurance_type': result[2],
            'requested_amount': result[3],
            'approved_amount': result[4],
            'duration_years': result[5],
            'status': result[6],
            'risk_score': result[7],
            'premium': result[8],
            'ai_explanation': result[9],
            'created_at': result[10],
        }
    return None
