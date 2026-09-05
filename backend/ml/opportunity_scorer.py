import sqlite3
import pandas as pd
import numpy as np
import os
import joblib
from datetime import datetime

DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, 'database', 'fitfuel.db')
MODEL_DIR = os.path.join(DB_DIR, 'ml', 'models')

def load_models_and_data(merchant_id=None):
    conn = sqlite3.connect(DB_PATH)
    
    where_clause = ""
    params = ()
    if merchant_id:
        where_clause = "WHERE c.merchant_id = ?"
        params = (merchant_id,)
        
    query = f"""
    SELECT 
        c.id as customer_id,
        c.name,
        c.created_at as signup_date,
        COUNT(t.id) as frequency,
        SUM(CASE WHEN t.status = 'success' THEN t.amount_in_paise / 100.0 ELSE 0 END) as total_spend,
        MAX(t.created_at) as last_purchase_date,
        SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_txns,
        (SELECT status FROM subscriptions WHERE customer_id = c.id LIMIT 1) as sub_status
    FROM customers c
    LEFT JOIN transactions t ON c.id = t.customer_id
    {where_clause}
    GROUP BY c.id
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Reload feature engineering logic to apply models
    today = pd.to_datetime('today').normalize()
    df['signup_date'] = pd.to_datetime(df['signup_date'])
    df['last_purchase_date'] = pd.to_datetime(df['last_purchase_date']).dt.normalize()
    
    df['days_since_signup'] = (today - df['signup_date']).dt.days
    df['recency'] = (today - df['last_purchase_date']).dt.days
    df['aov'] = np.where(df['frequency'] > 0, df['total_spend'] / df['frequency'], 0)
    df['sub_status'] = df['sub_status'].fillna('none')
    
    # Load Models
    churn_model = joblib.load(os.path.join(MODEL_DIR, 'churn_model.pkl'))
    ltv_model = joblib.load(os.path.join(MODEL_DIR, 'ltv_model.pkl'))
    
    return df, churn_model, ltv_model

def get_explainability(row):
    reasons = []
    if row['recency'] > 30:
        reasons.append(f"No purchase in {row['recency']} days")
    
    if row['sub_status'] in ['past_due', 'cancelled']:
        reasons.append(f"Subscription is {row['sub_status']}")
        
    if row['failed_txns'] > 0:
        reasons.append(f"{row['failed_txns']} failed transaction(s) recently")
        
    if row['frequency'] < 3 and row['days_since_signup'] > 90:
        reasons.append("Low engagement (low purchase frequency)")
        
    if not reasons:
        reasons.append("General inactivity patterns matching churned cohorts")
        
    return reasons

def generate_predictions(merchant_id=None):
    print(f"[ML Engine] Generating predictions and opportunity scores... (Merchant: {merchant_id or 'ALL'})")
    df, churn_model, ltv_model = load_models_and_data(merchant_id)
    
    features = ['days_since_signup', 'recency', 'frequency', 'total_spend', 'aov']
    churn_features = ['days_since_signup', 'frequency', 'total_spend', 'aov', 'failed_txns']
    
    # Impute missing features and ensure numeric types for xgboost
    all_features = list(set(features + churn_features))
    df[all_features] = df[all_features].fillna(0).astype(float)
    
    df['churn_risk'] = churn_model.predict_proba(df[churn_features])[:, 1]
    df['predicted_ltv'] = ltv_model.predict(df[features])
    
    df['opportunity_score'] = df['churn_risk'] * df['predicted_ltv']
    
    # Save predictions back to DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    predictions_data = []
    for _, row in df.iterrows():
        predictions_data.append((
            row['customer_id'],
            float(row['churn_risk']),
            float(row['predicted_ltv']),
            float(row['opportunity_score']),
            now
        ))
        
    cursor.executemany('''
        INSERT INTO predictions (customer_id, churn_risk, predicted_ltv, opportunity_score, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(customer_id) DO UPDATE SET
            churn_risk = excluded.churn_risk,
            predicted_ltv = excluded.predicted_ltv,
            opportunity_score = excluded.opportunity_score,
            updated_at = excluded.updated_at
    ''', predictions_data)
    
    conn.commit()
    conn.close()
    
    print(f"[ML Engine] Predictions updated for {len(predictions_data)} customers.")
    return df

if __name__ == '__main__':
    generate_predictions()
