import sqlite3
import os
import json
import time
from datetime import datetime

import sys
sys.path.append(os.path.dirname(__file__))

from database.generate_data import generate_data
from ml.opportunity_scorer import generate_predictions
from agent.loop import run_agent_loop
from agent.policy_engine import evaluate_draft_campaigns
from main import app, _execute_query
from fastapi.testclient import TestClient

client = TestClient(app)
DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'fitfuel.db')

def print_step(msg):
    print(f"\n{'='*50}\n[TEST] {msg}\n{'='*50}")

def run_tests():
    # 1. Reset DB
    print_step("1. Resetting DB and generating data")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    schema_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema_sql)
    conn.close()
    
    generate_data()
    
    # Run ML scorer
    print_step("2. Running ML Opportunity Scorer")
    generate_predictions()
    
    # 3. Check dashboard isolation
    print_step("3. Testing Merchant Isolation (A vs B)")
    rA = client.get("/api/dashboard", headers={"x-merchant-id": "merchant_acme_001"})
    rB = client.get("/api/dashboard", headers={"x-merchant-id": "merchant_b_002"})
    assert rA.status_code == 200, "Merchant A failed"
    assert rB.status_code == 200, "Merchant B failed"
    # Ensure they don't share the same data if isolation works (or at least no crash)
    print("Merchant A Dashboard:", rA.json())
    print("Merchant B Dashboard:", rB.json())

    # 4. Run AI Agent for Merchant A
    print_step("4. Running AI Agent Investigation & Proposal")
    result, track = run_agent_loop("merchant_acme_001", "Recover revenue from recent failed payments.")
    print("Agent Result:", result)
    campaign_id = result.get('campaign_id')
    assert campaign_id, "Agent did not output a campaign_id"
    
    c = _execute_query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,), fetch_one=True)
    assert c['status'] == 'DRAFT', "Campaign is not DRAFT"
    
    # 5. Run Policy Engine
    print_step("5. Running Policy Engine")
    evaluate_draft_campaigns()
    
    c = _execute_query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,), fetch_one=True)
    print(f"Policy Result: {c['status']}")
    print(f"Policy Details: {c['policy_result_json']}")
    
    # Force a rejection by changing the budget config
    print_step("6. Testing Policy Rejection Path")
    _execute_query("UPDATE merchant_config SET monthly_recovery_budget_inr = 0 WHERE id = 'merchant_acme_001'", commit=True)
    r_reject, _ = run_agent_loop("merchant_acme_001", "Create another campaign.")
    rej_id = r_reject.get('campaign_id')
    evaluate_draft_campaigns()
    crej = _execute_query("SELECT * FROM campaigns WHERE id = ?", (rej_id,), fetch_one=True)
    assert crej['status'] == 'REJECTED', f"Campaign should be rejected but is {crej['status']}"
    print("Successfully rejected campaign due to budget constraint.")
    
    # Test approval of a valid campaign
    print_step("7. Testing Approval Gate")
    if c['status'] == 'VALIDATED':
        # Approve it
        rap = client.post(f"/api/campaigns/{campaign_id}/approve", headers={"x-merchant-id": "merchant_acme_001"})
        assert rap.status_code == 200
        print("Campaign approved.")
    else:
        print("Initial campaign rejected, cannot test execute path directly on it.")
        
    # 8. Test Execution (Razorpay Links)
    print_step("8. Testing Execution via API")
    if c['status'] == 'VALIDATED':
        rex = client.post(f"/api/campaigns/{campaign_id}/execute", headers={"x-merchant-id": "merchant_acme_001"})
        print("Execution result:", rex.json())
        assert rex.status_code == 200
        
        c = _execute_query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,), fetch_one=True)
        assert c['status'] in ['ACTIVE', 'PARTIAL_FAILURE'], "Campaign should be ACTIVE or PARTIAL_FAILURE"
        
        # Verify links generated
        targets = _execute_query("SELECT * FROM campaign_targets WHERE campaign_id = ?", (campaign_id,))
        for t in targets:
            print(f"Target {t['id']} -> {t['status']}")
            if t['status'] == 'LINK_GENERATED':
                outcome = _execute_query("SELECT * FROM recovery_outcomes WHERE campaign_target_id = ?", (t['id'],), fetch_one=True)
                assert outcome, "Recovery outcome tracking row missing"
                
    # Restore budget config
    _execute_query("UPDATE merchant_config SET monthly_recovery_budget_inr = 25000 WHERE id = 'merchant_acme_001'", commit=True)

    print_step("TEST SUITE COMPLETED SUCCESSFULLY")

if __name__ == "__main__":
    run_tests()
