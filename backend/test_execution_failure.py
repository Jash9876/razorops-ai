import os
import sqlite3
import uuid
from fastapi.testclient import TestClient
from main import app, DB_PATH
import razorpay_client
from unittest.mock import patch

client = TestClient(app)

def test_partial_execution():
    print("--- Running Partial Execution Test ---")
    
    # 1. Setup a dummy APPROVED campaign with 3 targets
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    camp_id = f"camp_partial_test_{uuid.uuid4().hex[:4]}"
    now = "2026-01-01 10:00:00"
    
    cursor.execute('''
        INSERT INTO campaigns (id, segment_name, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (camp_id, "Test Segment", "APPROVED", now, now))
    
    # Insert 3 customers
    cids = ["cust_test_A", "cust_test_B", "cust_test_C"]
    for cid in cids:
        cursor.execute("INSERT OR IGNORE INTO customers (id, name, email) VALUES (?, ?, ?)", (cid, f"Name {cid}", f"{cid}@test.com"))
        
    # Insert 3 targets
    target_ids = []
    for i, cid in enumerate(cids):
        tid = f"ct_test_{i}_{camp_id}"
        target_ids.append(tid)
        cursor.execute('''
            INSERT INTO campaign_targets (id, campaign_id, customer_id, recommended_action, final_amount_paise, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (tid, camp_id, cid, 'DISCOUNT', 100000, 'PENDING'))
        
    conn.commit()
    conn.close()
    
    # 2. Patch razorpay_client to fail on the second target
    original_create = razorpay_client.create_payment_link
    
    call_count = 0
    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Deliberate Razorpay API Failure")
        return {"id": f"plink_mock_{uuid.uuid4().hex}"}
        
    print("Executing campaign (should fail on target 2)...")
    with patch('main.create_payment_link', side_effect=mock_create):
        try:
            client.post(f"/api/campaigns/{camp_id}/execute", headers={"x-merchant-id": "merchant_123"})
        except RuntimeError:
            print("Caught deliberate runtime error from execution.")
            
    # 3. Verify DB State: Target 1 LINK_GENERATED, Target 2 PENDING, Target 3 PENDING or FAILED
    # Wait, my main.py doesn't catch exceptions from create_payment_link, it bubbles up, stopping execution!
    # Let's check DB.
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM campaign_targets WHERE campaign_id = ? ORDER BY id", (camp_id,))
    statuses = [r[0] for r in cursor.fetchall()]
    print(f"Target statuses after crash: {statuses}")
    
    assert statuses[0] == 'LINK_GENERATED', "Target 1 should be generated"
    assert statuses[1] == 'PENDING', "Target 2 should be untouched"
    assert statuses[2] == 'PENDING', "Target 3 should be untouched"
    
    # 4. Retry Execution: Target 2 and 3 should succeed, Target 1 should be skipped.
    print("Retrying execution without failure...")
    def mock_create_success(*args, **kwargs):
        return {"id": f"plink_mock_retry_{uuid.uuid4().hex}"}
        
    with patch('main.create_payment_link', side_effect=mock_create_success):
        resp = client.post(f"/api/campaigns/{camp_id}/execute", headers={"x-merchant-id": "merchant_123"})
        assert resp.status_code == 200
        
    cursor.execute("SELECT status FROM campaign_targets WHERE campaign_id = ? ORDER BY id", (camp_id,))
    statuses2 = [r[0] for r in cursor.fetchall()]
    print(f"Target statuses after retry: {statuses2}")
    
    assert statuses2 == ['LINK_GENERATED', 'LINK_GENERATED', 'LINK_GENERATED'], "All targets should now be generated"
    
    # Verify we only generated 3 links total
    cursor.execute("SELECT COUNT(*) FROM recovery_outcomes WHERE campaign_target_id IN (?, ?, ?)", target_ids)
    count = cursor.fetchone()[0]
    assert count == 3, "Should exactly map to 3 recovery outcomes without duplicates."
    
    print("All Partial Execution Tests Passed.")
    conn.close()

if __name__ == "__main__":
    test_partial_execution()
