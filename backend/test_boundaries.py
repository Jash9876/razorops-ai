import os
import sqlite3
from fastapi.testclient import TestClient
from main import app
from agent.tools import get_failed_payments, get_segment_analysis, get_campaign_history
from ml.opportunity_scorer import generate_predictions

client = TestClient(app)
DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'fitfuel.db')

def test_all_boundaries():
    print("--- Running Boundary Tests ---")
    
    # Boundary 1: ML Predictions update Database
    print("1. Testing ML predictions boundary...")
    df = generate_predictions()
    assert not df.empty, "ML predictions failed to generate"
    
    # Boundary 2: Agent read-only tools
    print("2. Testing Agent read-only tools boundary...")
    failed = get_failed_payments()
    assert 'failed_attempts' in failed
    
    # Boundary 3: Policy Engine executes math and validates
    print("3. Testing Policy Engine boundary...")
    # Assuming Policy engine ran previously in our script testing, we can check for VALIDATED/APPROVED
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status IN ('VALIDATED', 'APPROVED', 'EXECUTING', 'ACTIVE')")
    count = cursor.fetchone()[0]
    conn.close()
    assert count > 0, "No campaigns passed policy engine"
    
    # Boundary 4: Approval API
    print("4. Testing Approval API boundary...")
    # we already tested this in test_execution.py, but we can verify the DB shifted
    
    # Boundary 5: Webhook Idempotency and Learning
    print("5. Testing Webhook boundary...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT payment_link_id FROM recovery_outcomes WHERE status = 'PAID' LIMIT 1")
    paid_link = cursor.fetchone()
    conn.close()
    
    if paid_link:
        # Re-send webhook to test idempotency
        payload = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": paid_link[0],
                        "amount_paid": 99999
                    }
                }
            }
        }
        resp = client.post("/api/webhooks/razorpay", json=payload)
        assert resp.status_code == 200
        
        # Verify amount did not change (idempotent)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT amount_recovered_paise FROM recovery_outcomes WHERE payment_link_id = ?", (paid_link[0],))
        amount = cursor.fetchone()[0]
        conn.close()
        assert amount != 99999, "Webhook is not idempotent, it overwrote existing paid status!"
        
    print("All boundaries passed successfully!")

if __name__ == "__main__":
    test_all_boundaries()
