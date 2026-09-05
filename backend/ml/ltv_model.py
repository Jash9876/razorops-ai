import sqlite3
import pandas as pd
import numpy as np
import os
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib
from datetime import datetime

DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, 'database', 'fitfuel.db')
MODEL_DIR = os.path.join(DB_DIR, 'ml', 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

def load_and_prep_data():
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        c.id as customer_id,
        c.signup_date,
        COUNT(t.id) as frequency,
        SUM(CASE WHEN t.status = 'success' THEN t.amount ELSE 0 END) as total_spend,
        MAX(t.transaction_date) as last_purchase_date
    FROM customers c
    LEFT JOIN transactions t ON c.id = t.customer_id
    GROUP BY c.id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    today = pd.to_datetime(datetime.now().date())
    df['signup_date'] = pd.to_datetime(df['signup_date'])
    df['last_purchase_date'] = pd.to_datetime(df['last_purchase_date']).dt.normalize()
    
    df['days_since_signup'] = (today - df['signup_date']).dt.days
    df['recency'] = (today - df['last_purchase_date']).dt.days
    df['aov'] = np.where(df['frequency'] > 0, df['total_spend'] / df['frequency'], 0)
    
    # Create a proxy for 'expected future spend' (LTV target)
    # In reality, this would be derived from a longitudinal dataset.
    # We will simulate a realistic target: High frequency + High AOV + Low recency = High LTV
    base_multiplier = np.where(df['recency'] <= 30, 1.5, 
                        np.where(df['recency'] <= 90, 0.8, 0.2))
    
    noise = np.random.normal(1.0, 0.2, size=len(df))
    df['target_future_spend'] = df['aov'] * (df['frequency'] / (df['days_since_signup']/30 + 1)) * 12 * base_multiplier * noise
    df['target_future_spend'] = df['target_future_spend'].clip(lower=0)
    
    return df

def train_ltv_model():
    print("Loading data for LTV model...")
    df = load_and_prep_data()
    
    features = ['days_since_signup', 'recency', 'frequency', 'total_spend', 'aov']
    X = df[features]
    y = df['target_future_spend']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost Regressor for LTV...")
    model = xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42)
    model.fit(X_train, y_train)
    
    preds = model.predict(X_test)
    print(f"RMSE: {np.sqrt(mean_squared_error(y_test, preds)):.2f}")
    print(f"R2 Score: {r2_score(y_test, preds):.4f}")
    
    # Save the model
    model_path = os.path.join(MODEL_DIR, 'ltv_model.pkl')
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")
    
    return df

if __name__ == '__main__':
    train_ltv_model()
