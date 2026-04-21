"""
ML Model Training Script
Generates synthetic insurance dataset and trains RandomForest model
"""

import os
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

# Feature names (must match order in app.py build_feature_vector)
FEATURES = [
    'age',
    'income',
    'bmi',
    'smoking',
    'alcohol',
    'exercise_freq',
    'medical_history_score',
    'dependents',
    'owns_house',
    'property_value_norm',
    'vehicles_total',
    'driving_score',
    'employment_score',
    'family_risk_score',
]

def generate_synthetic_dataset(n_samples=500):
    """
    Generate synthetic insurance dataset.
    Returns DataFrame with features and target (risk_score).
    """
    np.random.seed(42)
    
    data = {
        'age': np.random.randint(18, 80, n_samples),
        'income': np.random.uniform(200000, 5000000, n_samples),
        'bmi': np.random.uniform(18, 40, n_samples),
        'smoking': np.random.binomial(1, 0.25, n_samples),
        'alcohol': np.random.binomial(1, 0.35, n_samples),
        'exercise_freq': np.random.randint(0, 3, n_samples),  # 0=none, 1=occasional, 2=regular
        'medical_history_score': np.random.binomial(1, 0.15, n_samples),
        'dependents': np.random.randint(0, 5, n_samples),
        'owns_house': np.random.binomial(1, 0.60, n_samples),
        'property_value_norm': np.random.uniform(0, 1, n_samples),
        'vehicles_total': np.random.randint(0, 4, n_samples),
        'driving_score': np.random.randint(0, 3, n_samples),  # 0=major, 1=minor, 2=clean
        'employment_score': np.random.randint(0, 4, n_samples),  # 0=unemp, 1=self, 2=salaried, 3=retired
        'family_risk_score': np.random.binomial(1, 0.20, n_samples),
    }
    
    df = pd.DataFrame(data)
    
    # Calculate risk score using domain logic
    risk_scores = []
    for idx, row in df.iterrows():
        base = 30
        base += (row['age'] - 30) * 0.3
        base += max(0, row['bmi'] - 25) * 1.2
        base += row['smoking'] * 18
        base += row['alcohol'] * 6
        base -= row['exercise_freq'] * 5
        base += row['medical_history_score'] * 8
        base += row['family_risk_score'] * 4
        base -= row['employment_score'] * 3
        base += (row['vehicles_total'] - row['driving_score'] * 2) * 2
        base -= row['owns_house'] * 5
        
        # Add noise
        noise = np.random.normal(0, 4)
        base += noise
        
        # Clamp to 5-95
        risk_score = max(5, min(95, base))
        risk_scores.append(risk_score)
    
    df['risk_score'] = risk_scores
    
    return df

def train():
    """Train model and save artifacts."""
    print("Generating synthetic dataset...")
    df = generate_synthetic_dataset(n_samples=500)
    
    # Save dataset
    os.makedirs('data', exist_ok=True)
    df.to_csv('data/insurance_dataset.csv', index=False)
    print(f"  Saved: data/insurance_dataset.csv ({len(df)} rows)")
    
    # Prepare features and target
    X = df[FEATURES]
    y = df['risk_score']
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Build pipeline
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('model', RandomForestRegressor(
            n_estimators=200,
            random_state=42,
            n_jobs=-1,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
        ))
    ])
    
    # Train
    print("Training RandomForest model...")
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    y_pred = pipeline.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    print(f"Model trained. RMSE: {rmse:.2f}")
    
    # Save artifacts
    os.makedirs('models', exist_ok=True)
    
    # Save full pipeline (includes scaler)
    joblib.dump(pipeline, 'models/risk_model.pkl')
    print(f"  Saved: models/risk_model.pkl")
    
    # Save scaler separately (for compatibility)
    joblib.dump(pipeline.named_steps['scaler'], 'models/scaler.pkl')
    print(f"  Saved: models/scaler.pkl")
    
    # Save features list
    with open('models/features.json', 'w') as f:
        json.dump(FEATURES, f, indent=2)
    print(f"  Saved: models/features.json")
    
    print("✓ Training complete!")

if __name__ == '__main__':
    train()
