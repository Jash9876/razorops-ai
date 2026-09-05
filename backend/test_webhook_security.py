import hmac
import hashlib
import json
import os
import sqlite3
from fastapi.testclient import TestClient

# Mock environment setup
os.environ['RAZORPAY_WEBHOOK_SECRET'] = 'test_secret_123'
from main import app, DB_PATH

client = TestClient(app)

def _get_db_status(plink_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status, amount_recovered_paise FROM recovery_outcomes WHERE payment_link_id = ?", (plink_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def test_webhook_security():
    print("--- Running Webhook Security Tests ---")
    
    # Setup test data
    plink_id = "plink_test_security_1"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO recovery_outcomes (id, campaign_target_id, payment_link_id, amount_recovered_paise, status)
        VALUES (?, ?, ?, ?, ?)
    ''', ("ro_test_1", "ct_test_1", plink_id, 0, "PENDING"))
    conn.commit()
    conn.close()
    
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": plink_id,
                    "amount_paid": 50000
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode()
    
    # Test 1: Missing Signature -> Rejected
    print("Test 1: Missing Signature")
    resp = client.post("/api/webhooks/razorpay", content=raw_body, headers={})
    assert resp.status_code == 400
    assert "Missing signature" in resp.json()['detail']
    
    # Test 2: Invalid Signature -> Rejected
    print("Test 2: Invalid Signature")
    resp = client.post("/api/webhooks/razorpay", content=raw_body, headers={'x-razorpay-signature': 'bad_signature'})
    assert resp.status_code == 400
    assert "Invalid signature" in resp.json()['detail']
    
    # Test 3: Valid Signature -> Accepted
    print("Test 3: Valid Signature")
    valid_signature = hmac.new('test_secret_123'.encode(), raw_body, hashlib.sha256).hexdigest()
    resp = client.post("/api/webhooks/razorpay", content=raw_body, headers={'x-razorpay-signature': valid_signature})
    assert resp.status_code == 200
    status, amount = _get_db_status(plink_id)
    assert status == 'PAID'
    assert amount == 50000
    
    # Test 4: Duplicate Event -> No double recovery (Idempotent)
    print("Test 4: Duplicate Event")
    payload['payload']['payment_link']['entity']['amount_paid'] = 99999
    raw_body_duplicate = json.dumps(payload).encode()
    valid_signature_duplicate = hmac.new('test_secret_123'.encode(), raw_body_duplicate, hashlib.sha256).hexdigest()
    
    resp = client.post("/api/webhooks/razorpay", content=raw_body_duplicate, headers={'x-razorpay-signature': valid_signature_duplicate})
    assert resp.status_code == 200 # Webhook should accept it idempotently
    status, amount = _get_db_status(plink_id)
    assert amount == 50000 # Must NOT update to 99999
    assert amount != 99999
    
    print("All Webhook Security Tests Passed.")
    
    # Cleanup
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recovery_outcomes WHERE id = 'ro_test_1'")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    test_webhook_security()
