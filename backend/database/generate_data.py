import sqlite3
import os
import random
from datetime import datetime, timedelta
import uuid
from faker import Faker

fake = Faker('en_IN')
Faker.seed(42)
random.seed(42)

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'fitfuel.db')

NUM_CUSTOMERS = 1000

def generate_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data
    cursor.executescript('''
        DELETE FROM payment_attempts;
        DELETE FROM subscriptions;
        DELETE FROM transactions;
        DELETE FROM customers;
        DELETE FROM merchant_config;
    ''')

    # Setup initial merchant config
    cursor.execute("INSERT INTO merchant_config (id, monthly_recovery_budget_inr) VALUES (?, ?)", ("merchant_acme_001", 25000.0))
    cursor.execute("INSERT INTO merchant_config (id, monthly_recovery_budget_inr) VALUES (?, ?)", ("merchant_b_002", 25000.0))

    print(f"Generating {NUM_CUSTOMERS} customers...")
    
    customers = []
    transactions = []
    subscriptions = []
    payment_attempts = []

    today = datetime.now()
    two_years_ago = today - timedelta(days=730)

    for _ in range(NUM_CUSTOMERS):
        cust_id = str(uuid.uuid4())
        name = fake.name()
        email = fake.email()
        phone = fake.phone_number()
        
        churn_profile = random.choices(['loyal', 'at_risk', 'churned', 'new'], weights=[0.4, 0.3, 0.2, 0.1])[0]
        
        if churn_profile == 'loyal':
            signup_date = fake.date_between_dates(date_start=two_years_ago, date_end=today - timedelta(days=180))
            last_purchase_days_ago = random.randint(1, 30)
            freq = random.randint(12, 24)
            segment = 'Premium' if random.random() > 0.5 else 'Basic'
        elif churn_profile == 'at_risk':
            signup_date = fake.date_between_dates(date_start=two_years_ago, date_end=today - timedelta(days=90))
            last_purchase_days_ago = random.randint(31, 60)
            freq = random.randint(4, 10)
            segment = 'Basic'
        elif churn_profile == 'churned':
            signup_date = fake.date_between_dates(date_start=two_years_ago, date_end=today - timedelta(days=180))
            last_purchase_days_ago = random.randint(61, 200)
            freq = random.randint(2, 6)
            segment = 'Basic'
        else: # new
            signup_date = fake.date_between_dates(date_start=today - timedelta(days=30), date_end=today)
            last_purchase_days_ago = random.randint(1, 15)
            freq = random.randint(1, 2)
            segment = 'New'

        merchant_id = random.choice(['merchant_acme_001', 'merchant_b_002'])
        customers.append((cust_id, merchant_id, name, email, phone, signup_date.strftime('%Y-%m-%d %H:%M:%S')))

        last_purchase_date = today - timedelta(days=last_purchase_days_ago)
        
        if freq > 1:
            days_active = (last_purchase_date.date() - signup_date).days
            if days_active <= 0: days_active = 1
            interval = max(1, days_active // (freq - 1))
        else:
            interval = 0
            
        for i in range(freq):
            txn_id = str(uuid.uuid4())
            amount = random.choice([999.0, 1499.0, 1999.0, 4999.0])
            if segment == 'Premium': amount *= 2
            amount = round(amount * random.uniform(0.9, 1.1), 2)
            amount_in_paise = int(amount * 100)
            
            txn_date = last_purchase_date - timedelta(days=interval * i)
            if txn_date.date() < signup_date:
                txn_date = datetime.combine(signup_date, datetime.min.time()) + timedelta(days=1)
                
            status = 'success'
            if churn_profile == 'at_risk' and i == 0:
                status = 'failed'
            elif random.random() < 0.05:
                status = 'failed'
                
            transactions.append((txn_id, cust_id, amount_in_paise, status, txn_date.strftime('%Y-%m-%d %H:%M:%S')))
            
            attempt_id = str(uuid.uuid4())
            error_code = random.choices(['insufficient_funds', 'expired_card', 'upi_failure'], weights=[0.6, 0.25, 0.15])[0] if status == 'failed' else None
            # payment_attempts: id, transaction_id, customer_id, status, error_code, created_at
            payment_attempts.append((attempt_id, txn_id, cust_id, status, error_code, txn_date.strftime('%Y-%m-%d %H:%M:%S')))
            
            if status == 'failed' and random.random() < 0.5:
                retry_id = str(uuid.uuid4())
                retry_date = txn_date + timedelta(hours=random.randint(1, 24))
                retry_status = 'success' if random.random() < 0.7 else 'failed'
                retry_error = None if retry_status == 'success' else random.choices(['insufficient_funds', 'expired_card', 'upi_failure'], weights=[0.6, 0.25, 0.15])[0]
                payment_attempts.append((retry_id, txn_id, cust_id, retry_status, retry_error, retry_date.strftime('%Y-%m-%d %H:%M:%S')))
                if retry_status == 'success':
                    transactions[-1] = (txn_id, cust_id, amount_in_paise, 'success', txn_date.strftime('%Y-%m-%d %H:%M:%S'))

        if random.random() < 0.6: 
            sub_id = str(uuid.uuid4())
            plan_id = 'plan_pro' if segment == 'Premium' else 'plan_basic'
            
            if churn_profile == 'loyal' or churn_profile == 'new':
                sub_status = 'active'
            elif churn_profile == 'at_risk':
                sub_status = random.choice(['active', 'past_due'])
            else:
                sub_status = 'cancelled'
                
            # subscriptions: id, customer_id, plan_id, status, created_at
            sub_date = signup_date + timedelta(days=1)
            subscriptions.append((sub_id, cust_id, plan_id, sub_status, sub_date.strftime('%Y-%m-%d %H:%M:%S')))

    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customers)
    cursor.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)", transactions)
    cursor.executemany("INSERT INTO payment_attempts VALUES (?, ?, ?, ?, ?, ?)", payment_attempts)
    cursor.executemany("INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?)", subscriptions)

    conn.commit()
    conn.close()
    
    print(f"Inserted {len(customers)} customers, {len(transactions)} transactions, {len(subscriptions)} subscriptions, {len(payment_attempts)} payment attempts.")

if __name__ == '__main__':
    generate_data()
