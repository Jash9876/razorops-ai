import os
import sqlite3
import datetime
import razorpay
from dotenv import load_dotenv

DB_PATH = os.path.join(os.path.dirname(__file__), 'fitfuel.db')
MERCHANT_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.merchant')

def get_razorpay_client():
    key_id = None
    key_secret = None

    if os.path.exists(MERCHANT_ENV_FILE):
        load_dotenv(MERCHANT_ENV_FILE, override=True)
        key_id = os.getenv('RAZORPAY_KEY_ID')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET')
    
    if not key_id or not key_secret:
        key_id = os.environ.get('RAZORPAY_KEY_ID')
        key_secret = os.environ.get('RAZORPAY_KEY_SECRET')

    if not key_id or not key_secret:
        raise ValueError("Merchant credentials not found. Please configure RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
        
    return razorpay.Client(auth=(key_id, key_secret))


def fetch_all_paginated(api_method):
    options = {'count': 100, 'skip': 0}
    all_items = []
    while True:
        resp = api_method(options)
        items = resp.get('items', [])
        all_items.extend(items)
        if len(items) < 100:
            break
        options['skip'] += 100
    return all_items

def sync_razorpay_data(merchant_id: str):
    """
    Sync Worker Job:
    Pulls live data from Razorpay and upserts it into the DB for the connected merchant.
    Normalizes data into the canonical schema.
    """
    print(f"[Worker] Starting Razorpay Data Sync for {merchant_id}...")
    client = get_razorpay_client()
    
    sync_status = {"customers": "success", "subscriptions": "success", "payments": "success"}
    
    # 1. Fetch live data
    live_customers = []
    try:
        live_customers = fetch_all_paginated(client.customer.all)
    except Exception as e:
        print(f"Failed to fetch customers: {e}")
        sync_status["customers"] = "failed"

    live_subscriptions = []
    try:
        live_subscriptions = fetch_all_paginated(client.subscription.all)
    except Exception as e:
        print(f"Failed to fetch subscriptions: {e}")
        sync_status["subscriptions"] = "failed"
        
    live_payments = []
    try:
        live_payments = fetch_all_paginated(client.payment.all)
    except Exception as e:
        print(f"Failed to fetch payments: {e}")
        sync_status["payments"] = "failed"
        # Payments are the critical source for RazorOps.
        raise RuntimeError("Failed to fetch payments. Critical data missing, aborting sync.") from e

    print(f"[Worker] Fetched {len(live_customers)} customers, {len(live_payments)} payments, and {len(live_subscriptions)} subscriptions from Razorpay.")
    
    # 2. Normalize & Upsert
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    new_records = 0
    updated_records = 0
    
    # Customers
    for c in live_customers:
        created_at = datetime.datetime.fromtimestamp(c['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        name = c.get('name') or 'Live User'
        email = c.get('email') or ''
        phone = c.get('contact') or ''
        
        cursor.execute("SELECT id FROM customers WHERE id=? AND merchant_id=?", (c['id'], merchant_id))
        if cursor.fetchone():
            cursor.execute('''
                UPDATE customers SET name=?, email=?, phone=? WHERE id=? AND merchant_id=?
            ''', (name, email, phone, c['id'], merchant_id))
            updated_records += 1
        else:
            cursor.execute('''
                INSERT INTO customers (id, merchant_id, name, email, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (c['id'], merchant_id, name, email, phone, created_at))
            new_records += 1

    # Ensure customers for payments exist even if not in the customer list
    for p in live_payments:
        cid = p.get('customer_id')
        if not cid:
            cid = f"cust_inline_{p['id']}"
            p['customer_id'] = cid # patch it
            
        cursor.execute("SELECT id FROM customers WHERE id=? AND merchant_id=?", (cid, merchant_id))
        if not cursor.fetchone():
            dt = datetime.datetime.fromtimestamp(p['created_at']).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO customers (id, merchant_id, name, email, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (cid, merchant_id, p.get('email', 'Inline Customer'), p.get('email', ''), p.get('contact', ''), dt))
            new_records += 1

    # Payments (transactions and payment_attempts)
    for p in live_payments:
        cid = p['customer_id']
        amt_paise = p['amount']
        dt = datetime.datetime.fromtimestamp(p['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        status = 'success' if p['status'] == 'captured' else 'failed'
        
        # Verify the customer belongs to this merchant (we just created/upserted them above)
        
        cursor.execute("SELECT id FROM transactions WHERE id=?", (p['id'],))
        if cursor.fetchone():
            cursor.execute("UPDATE transactions SET status=? WHERE id=?", (status, p['id']))
            updated_records += 1
        else:
            cursor.execute('''
                INSERT INTO transactions (id, customer_id, amount_in_paise, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (p['id'], cid, amt_paise, status, dt))
            new_records += 1

        if status == 'failed':
            att_id = f"att_{p['id']}"
            cursor.execute("SELECT id FROM payment_attempts WHERE id=?", (att_id,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO payment_attempts (id, transaction_id, customer_id, status, error_code, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (att_id, p['id'], cid, 'failed', p.get('error_code', 'unknown'), dt))
                new_records += 1
                
    # Subscriptions
    for s in live_subscriptions:
        cid = s.get('customer_id')
        if not cid: continue
        
        plan_id = s.get('plan_id', 'plan_default')
        status = s.get('status', 'active')
        created_at = datetime.datetime.fromtimestamp(s['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("SELECT id FROM subscriptions WHERE id=?", (s['id'],))
        if cursor.fetchone():
            cursor.execute("UPDATE subscriptions SET status=? WHERE id=?", (status, s['id']))
            updated_records += 1
        else:
            cursor.execute('''
                INSERT INTO subscriptions (id, customer_id, plan_id, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (s['id'], cid, plan_id, status, created_at))
            new_records += 1

    conn.commit()
    conn.close()
    
    print(f"[Worker] Sync complete. Inserted {new_records} new records, updated {updated_records} records.")
    
    # After sync, run ML opportunity scorer on the new data
    try:
        import sys
        ml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        if ml_path not in sys.path:
            sys.path.append(ml_path)
            
        from ml.opportunity_scorer import generate_predictions
        print(f"[Worker] Running ML Opportunity Scorer on synchronized data for {merchant_id}...")
        generate_predictions(merchant_id)
    except Exception as e:
        print(f"[Worker] ML Scorer error: {e}")

    return {
        "status": "success" if sync_status["customers"] == "success" and sync_status["subscriptions"] == "success" else "partial",
        "sync_status": sync_status,
        "synced_records": new_records, 
        "updated_records": updated_records, 
        "message": "Live Razorpay data synced!"
    }

if __name__ == '__main__':
    # Test script locally
    sync_razorpay_data("merchant_live_123")
