import pandas as pd
from opportunity_scorer import load_models_and_data

def validate():
    print("--- ML Validation ---")
    df, churn_model, ltv_model = load_models_and_data()
    
    features = ['days_since_signup', 'recency', 'frequency', 'total_spend', 'aov']
    # Remember churn_model was trained without recency now
    churn_features = ['days_since_signup', 'frequency', 'total_spend', 'aov', 'failed_txns']
    
    df['churn_risk'] = churn_model.predict_proba(df[churn_features])[:, 1]
    df['predicted_ltv'] = ltv_model.predict(df[features])
    df['opportunity_score'] = df['churn_risk'] * df['predicted_ltv']
    
    print("\n1. Churn Risk Distribution:")
    print(df['churn_risk'].describe(percentiles=[.25, .5, .75, .90, .95]))
    
    print("\n2. Predicted LTV Distribution:")
    print(df['predicted_ltv'].describe())
    
    print("\n3. Opportunity Score Distribution:")
    print(df['opportunity_score'].describe())

if __name__ == "__main__":
    validate()
