import os
import sqlite3
import datetime
from razorpay_client import fetch_all_payments, fetch_all_customers, fetch_all_subscriptions
from database.generate_data import generate_data

DB_PATH = os.path.join(os.path.dirname(__file__), 'fitfuel.db')

def _execute_with_conn(query, params=(), commit=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    if commit:
        conn.commit()
    result = cursor.fetchall()
    conn.close()
    return result

def check_has_real_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM customers WHERE id NOT LIKE '%-%'")
    real_customers = cursor.fetchone()[0]
    conn.close()
    return real_customers > 0

def sync_razorpay_data():
    """
    Sync Worker Job:
    Pulls live data from Razorpay and inserts it into the DB based on the new schema.
    If no real data exists across Razorpay and local, it seeds the bootstrap dataset.
    """
    print("[Worker] Starting Razorpay Data Sync...")
    
    live_customers = fetch_all_customers()
    live_payments = fetch_all_payments()
    live_subscriptions = fetch_all_subscriptions()
    
    print(f"[Worker] Fetched {len(live_customers)} customers, {len(live_payments)} payments, and {len(live_subscriptions)} subscriptions from Razorpay.")
    
    if not live_customers and not live_payments and not live_subscriptions:
        if not check_has_real_data():
            print("[Worker] No live data found and no local data. Seeding bootstrap dataset for V1 cold start...")
            generate_data()
            return {"status": "success", "synced_records": 0, "message": "Seeded bootstrap dataset."}
        else:
            print("[Worker] No new live data found from Razorpay.")
            return {"status": "success", "synced_records": 0, "message": "No new data to sync."}

    # Inject live data into DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_records = 0
    
    # 1. Sync Customers
    for c in live_customers:
        cursor.execute("SELECT id FROM customers WHERE id=?", (c['id'],))
        if cursor.fetchone(): continue
        
        created_at = datetime.datetime.fromtimestamp(c['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO customers (id, name, email, phone, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (c['id'], c.get('name', 'Live User'), c.get('email', ''), c.get('contact', ''), created_at))
        new_records += 1
        
    # 2. Sync Subscriptions
    for s in live_subscriptions:
        cursor.execute("SELECT id FROM subscriptions WHERE id=?", (s['id'],))
        if cursor.fetchone(): continue
        
        cid = s.get('customer_id')
        if not cid: continue
        
        plan_id = s.get('plan_id', 'plan_default')
        status = s.get('status', 'active')
        created_at = datetime.datetime.fromtimestamp(s['created_at']).strftime('%Y-%m-%d %H:%M:%S')
            
        cursor.execute('''
            INSERT INTO subscriptions (id, customer_id, plan_id, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (s['id'], cid, plan_id, status, created_at))
        new_records += 1

    # 3. Sync Payments (transactions and payment_attempts)
    for p in live_payments:
        cursor.execute("SELECT id FROM transactions WHERE id=?", (p['id'],))
        if cursor.fetchone(): continue
        
        amt_paise = p['amount']
        dt = datetime.datetime.fromtimestamp(p['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        status = 'success' if p['status'] == 'captured' else 'failed'
        
        cid = p.get('customer_id')
        if not cid: continue
            
        # transactions: id, customer_id, amount_in_paise, status, created_at
        cursor.execute('''
            INSERT INTO transactions (id, customer_id, amount_in_paise, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (p['id'], cid, amt_paise, status, dt))
        new_records += 1

        # payment_attempts: id, transaction_id, customer_id, status, error_code, created_at
        if status == 'failed':
            att_id = f"att_{p['id']}"
            cursor.execute('''
                INSERT INTO payment_attempts (id, transaction_id, customer_id, status, error_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (att_id, p['id'], cid, 'failed', p.get('error_code', 'unknown'), dt))

    conn.commit()
    conn.close()
    
    print(f"[Worker] Sync complete. Inserted {new_records} new records.")
    return {"status": "success", "synced_records": new_records, "message": "Live Razorpay data synced successfully!"}

if __name__ == '__main__':
    sync_razorpay_data()
