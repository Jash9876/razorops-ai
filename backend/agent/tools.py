import sqlite3
import os
import uuid
import json
from datetime import datetime, timedelta

DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, 'database', 'fitfuel.db')

def _execute_query(query, params=(), fetch_one=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchone() if fetch_one else cursor.fetchall()
    conn.close()
    return dict(result) if result and fetch_one else [dict(row) for row in result]

def get_failed_payments(merchant_id: str, days: int = 7) -> dict:
    """Returns count, total volume, primary error codes, and concrete customer IDs for failed payments in a time window."""
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    query = """
        SELECT 
            pa.id as attempt_id,
            pa.customer_id,
            pa.error_code,
            t.amount_in_paise
        FROM payment_attempts pa
        JOIN transactions t ON pa.transaction_id = t.id
        JOIN customers c ON pa.customer_id = c.id
        WHERE pa.status = 'failed' AND pa.created_at >= ? AND c.merchant_id = ?
    """
    results = _execute_query(query, (since, merchant_id))
    
    total_failures = len(results)
    total_amount = sum(r['amount_in_paise'] or 0 for r in results)
    
    error_distribution = {}
    customer_ids = list(dict.fromkeys(r['customer_id'] for r in results if r['customer_id']))
    
    if total_failures > 0:
        counts = {}
        for r in results:
            err = r['error_code'] or 'unknown'
            counts[err] = counts.get(err, 0) + 1
        for err, count in counts.items():
            error_distribution[err] = round(count / total_failures, 2)
            
    return {
        "failed_attempts": total_failures,
        "amount_at_risk_inr": total_amount / 100.0,
        "error_distribution": error_distribution,
        "target_customer_ids": customer_ids
    }

def get_segment_analysis(merchant_id: str, segment_criteria: dict) -> dict:
    """
    Returns LTV distribution, average churn risk, and concrete customer IDs for affected customers.
    """
    error_code = segment_criteria.get("payment_failure")
    churn_risk_min = segment_criteria.get("churn_risk_min", 0.0)
    
    if error_code:
        query = """
            SELECT 
                c.id, p.predicted_ltv, p.churn_risk
            FROM customers c
            JOIN predictions p ON c.id = p.customer_id
            JOIN payment_attempts pa ON c.id = pa.customer_id
            WHERE pa.status = 'failed' AND pa.error_code = ? AND p.churn_risk >= ? AND c.merchant_id = ?
            GROUP BY c.id
        """
        customers = _execute_query(query, (error_code, churn_risk_min, merchant_id))
    else:
        query = """
            SELECT 
                c.id, p.predicted_ltv, p.churn_risk
            FROM customers c
            JOIN predictions p ON c.id = p.customer_id
            WHERE p.churn_risk >= ? AND c.merchant_id = ?
        """
        customers = _execute_query(query, (churn_risk_min, merchant_id))
    
    if not customers:
        return {"customer_count": 0, "customer_ids": []}
        
    avg_churn = sum(c['churn_risk'] for c in customers) / len(customers)
    
    high_ltv = sum(1 for c in customers if c['predicted_ltv'] > 10000)
    med_ltv = sum(1 for c in customers if 5000 <= c['predicted_ltv'] <= 10000)
    low_ltv = sum(1 for c in customers if c['predicted_ltv'] < 5000)
    
    return {
        "customer_count": len(customers),
        "average_churn_risk": round(avg_churn, 2),
        "ltv_distribution": {
            "high_ltv_over_10k": high_ltv,
            "medium_ltv_5k_to_10k": med_ltv,
            "low_ltv_under_5k": low_ltv
        },
        "customer_ids": [c['id'] for c in customers]
    }

def get_customer_context(merchant_id: str, customer_id: str) -> dict:
    """Deep dive into a specific customer's risk and value."""
    query = """
        SELECT 
            c.name, p.predicted_ltv, p.churn_risk, p.opportunity_score
        FROM customers c
        JOIN predictions p ON c.id = p.customer_id
        WHERE c.id = ? AND c.merchant_id = ?
    """
    customer = _execute_query(query, (customer_id, merchant_id), fetch_one=True)
    if not customer:
        return {"error": "Customer not found"}
        
    failures = _execute_query("SELECT error_code, created_at FROM payment_attempts WHERE customer_id = ? AND status = 'failed' ORDER BY created_at DESC LIMIT 3", (customer_id,))
    
    return {
        "customer": customer,
        "recent_failures": failures
    }

def get_campaign_history(merchant_id: str, segment_type: str = "failed_renewals") -> dict:
    """
    Returns historical recovery rates for previous incentives (The "Learn" feedback loop).
    Since we might not have a lot of data initially, it aggregates past campaigns.
    """
    # Fetch historical completed campaigns and their targets
    query = """
        SELECT 
            ct.recommended_action,
            ct.discount_percentage,
            COUNT(ct.id) as total_targets,
            SUM(CASE WHEN r.status = 'PAID' THEN 1 ELSE 0 END) as successful_recoveries,
            SUM(r.amount_recovered_paise) as total_revenue_paise
        FROM campaign_targets ct
        JOIN campaigns camp ON ct.campaign_id = camp.id
        LEFT JOIN recovery_outcomes r ON ct.id = r.campaign_target_id
        WHERE camp.status = 'COMPLETED' AND camp.merchant_id = ?
        GROUP BY ct.recommended_action, ct.discount_percentage
    """
    history = _execute_query(query, (merchant_id,))
    
    # If no history yet, return honest insufficient data so the agent relies on its platform prior
    if not history:
        return {
            "historical_conversion_rates": {},
            "sample_size": 0,
            "confidence": "INSUFFICIENT_DATA",
            "note": "No merchant campaign history available yet. Use platform baseline priors."
        }
        
    results = {}
    for h in history:
        action = h['recommended_action']
        discount = h['discount_percentage']
        key = f"{action}_{discount}_percent" if action == 'DISCOUNT' else action
        conversion = h['successful_recoveries'] / h['total_targets'] if h['total_targets'] > 0 else 0
        revenue = (h['total_revenue_paise'] or 0) / 100.0
        results[key] = {
            "conversion_rate": round(conversion, 2),
            "actual_revenue_recovered_inr": round(revenue, 2)
        }
        
    return {
        "historical_conversion_rates": results,
        "note": "Based on actual local campaign outcomes."
    }

def submit_campaign_proposal(merchant_id: str, action: str, discount: int, targets: list, campaign_name: str = "High-LTV Failed Payments") -> dict:
    """
    Submits a campaign proposal as a DRAFT.
    Requires concrete customer IDs belonging to this merchant.
    Rejects symbolic group strings or empty target resolutions.
    """
    if not targets or not isinstance(targets, list):
        return {"status": "ERROR", "message": "Proposal rejected: targets must be a non-empty list of concrete customer IDs."}
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    target_records = []
    seen_customers = set()
    
    for cid in targets:
        if not isinstance(cid, str) or cid.startswith("failed_") or cid.startswith("high_") or cid == "all":
            continue
            
        if cid in seen_customers:
            continue
            
        # Find their last transaction to determine original amount AND validate merchant ownership
        cursor.execute('''
            SELECT t.amount_in_paise 
            FROM customers c
            JOIN transactions t ON t.customer_id = c.id
            WHERE c.id = ? AND c.merchant_id = ?
            ORDER BY t.created_at DESC LIMIT 1
        ''', (cid, merchant_id))
        res = cursor.fetchone()
        
        if not res:
            continue
            
        seen_customers.add(cid)
        original_amount = res[0]
        discount_amount = int(original_amount * (discount / 100.0))
        final_amount = original_amount - discount_amount
        
        target_id = f"ct_{uuid.uuid4().hex[:8]}"
        target_records.append((
            target_id, cid, action, original_amount, discount, discount_amount, final_amount, 'PENDING'
        ))
        
    if not target_records:
        conn.close()
        return {
            "status": "ERROR",
            "message": "Proposal rejected: None of the provided targets resolved to valid customers for this merchant. You must provide concrete customer IDs (e.g. cust_...)."
        }
        
    campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        INSERT INTO campaigns (id, merchant_id, segment_name, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (campaign_id, merchant_id, campaign_name, "DRAFT", now, now))
    
    db_target_rows = [
        (t[0], campaign_id, t[1], t[2], t[3], t[4], t[5], t[6], t[7])
        for t in target_records
    ]
    
    cursor.executemany('''
        INSERT INTO campaign_targets (id, campaign_id, customer_id, recommended_action, original_amount_paise, discount_percentage, discount_amount_paise, final_amount_paise, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', db_target_rows)
    
    conn.commit()
    conn.close()
    
    return {
        "status": "DRAFT_CREATED",
        "campaign_id": campaign_id,
        "resolved_targets_count": len(target_records),
        "message": f"Proposal successfully submitted with {len(target_records)} targets to Policy Engine for validation. You have NO further execution permissions."
    }
