import sqlite3
import pandas as pd
import numpy as np
import os
from datetime import datetime
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, 'database', 'fitfuel.db')
MODEL_DIR = os.path.join(DB_DIR, 'ml', 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

def load_data():
    conn = sqlite3.connect(DB_PATH)
    
    # Query to build features
    query = """
    SELECT 
        c.id as customer_id,
        c.signup_date,
        c.segment,
        COUNT(t.id) as frequency,
        SUM(CASE WHEN t.status = 'success' THEN t.amount ELSE 0 END) as total_spend,
        MAX(t.transaction_date) as last_purchase_date,
        SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_txns
    FROM customers c
    LEFT JOIN transactions t ON c.id = t.customer_id
    GROUP BY c.id
    """
    df = pd.read_sql_query(query, conn)
    
    # Add subscription info
    sub_query = "SELECT customer_id, status as sub_status FROM subscriptions"
    sub_df = pd.read_sql_query(sub_query, conn)
    
    df = pd.merge(df, sub_df, on='customer_id', how='left')
    conn.close()
    
    return df

def engineer_features(df):
    today = pd.to_datetime(datetime.now().date())
    
    # Date parsing
    df['signup_date'] = pd.to_datetime(df['signup_date'])
    df['last_purchase_date'] = pd.to_datetime(df['last_purchase_date']).dt.normalize()
    
    # Features
    df['days_since_signup'] = (today - df['signup_date']).dt.days
    df['recency'] = (today - df['last_purchase_date']).dt.days
    df['aov'] = np.where(df['frequency'] > 0, df['total_spend'] / df['frequency'], 0)
    
    # Handle missing subscriptions
    df['sub_status'] = df['sub_status'].fillna('none')
    
    # Target Labeling for Training
    # Define 'churned' as recency > 60 days. Define 'loyal' as recency <= 30 days.
    # We will only train on users with > 30 days since signup to avoid new user noise.
    train_df = df[df['days_since_signup'] > 30].copy()
    train_df['is_churn'] = np.where(train_df['recency'] > 60, 1, 0)
    
    return train_df, df

def train_churn_model():
    print("Loading and preparing data...")
    raw_df = load_data()
    train_df, full_df = engineer_features(raw_df)
    
    # Features for model (excluding recency to prevent target leakage)
    features = ['days_since_signup', 'frequency', 'total_spend', 'aov', 'failed_txns']
    
    X = train_df[features]
    y = train_df['is_churn']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost Churn Model...")
    model = xgb.XGBClassifier(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42)
    model.fit(X_train, y_train)
    
    preds = model.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, preds):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, preds))
    
    # Predict probabilities for everyone
    full_df['churn_probability'] = model.predict_proba(full_df[features])[:, 1]
    
    # Save the model
    model_path = os.path.join(MODEL_DIR, 'churn_model.pkl')
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")
    
    return full_df

if __name__ == '__main__':
    train_churn_model()
