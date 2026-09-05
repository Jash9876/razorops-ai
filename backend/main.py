import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

import hmac
import hashlib
import json

# Local imports
from razorpay_client import create_payment_link
from database.sync_service import sync_razorpay_data
from database.generate_data import generate_data
from database.init_db import init_db

load_dotenv()

RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET')

app = FastAPI(title="RazorOps AI V1 API")

@app.on_event("startup")
def on_startup():
    DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'fitfuel.db')
    if not os.path.exists(DB_PATH):
        init_db()
        generate_data()
        try:
            from ml.opportunity_scorer import generate_predictions
            generate_predictions()
        except Exception as e:
            print("Predictions generation on startup notice:", e)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'fitfuel.db')


def _execute_query(query, params=(), commit=False, fetch_one=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    if commit:
        conn.commit()
        result = cursor.lastrowid
    else:
        result = cursor.fetchone() if fetch_one else cursor.fetchall()
        result = dict(result) if result and fetch_one else ([dict(row) for row in result] if result else [])
    conn.close()
    return result

class ConnectRequest(BaseModel):
    key_id: str
    key_secret: str
    environment: str = "Test"

MERCHANT_ENV_FILE = os.path.join(os.path.dirname(__file__), '.env.merchant')

@app.post("/api/connect")
def connect_razorpay(req: ConnectRequest):
    # Store credentials server-side only in .env.merchant
    with open(MERCHANT_ENV_FILE, 'w') as f:
        f.write(f"RAZORPAY_KEY_ID={req.key_id}\n")
        f.write(f"RAZORPAY_KEY_SECRET={req.key_secret}\n")
    return {"status": "success", "merchant_id": "merchant_live_123", "message": "Credentials saved securely."}

@app.post("/api/sync-data")
def sync_data(request: Request):
    try:
        merchant_id = request.headers.get('x-merchant-id', 'merchant_live_123')
        result = sync_razorpay_data(merchant_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/demo/seed")
def seed_demo_data():
    try:
        # Wipe the database and reseed
        DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'fitfuel.db')
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        
        schema_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(schema_sql)
        conn.close()
        
        generate_data()
        
        from ml.opportunity_scorer import generate_predictions
        generate_predictions()
        
        return {"status": "success", "message": "Demo data seeded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard")
def get_dashboard_metrics(request: Request):
    merchant_id = request.headers.get('x-merchant-id')
    if not merchant_id: raise HTTPException(status_code=401, detail="Missing x-merchant-id header")
    
    # At-Risk Customer LTV
    risk = _execute_query("SELECT SUM(p.predicted_ltv) as r FROM predictions p JOIN customers c ON p.customer_id = c.id WHERE (p.churn_risk >= 0.5 OR p.opportunity_score > 0) AND c.merchant_id = ?", (merchant_id,), fetch_one=True)
    revenue_at_risk_inr = (risk['r'] or 0)
    
    # Expected net recovery from currently active interventions
    rec = _execute_query("SELECT SUM(sys_expected_net_inr) as e FROM campaigns WHERE merchant_id = ? AND status IN ('EXECUTING', 'ACTIVE')", (merchant_id,), fetch_one=True)
    expected_recovery_inr = (rec['e'] or 0)
    
    # Customers needing intervention
    cust = _execute_query("SELECT COUNT(*) as c FROM predictions p JOIN customers c ON p.customer_id = c.id WHERE (p.churn_risk >= 0.5 OR p.opportunity_score > 0) AND c.merchant_id = ?", (merchant_id,), fetch_one=True)
    customers_intervention = (cust['c'] or 0)
    
    return {
        "revenue_at_risk_inr": revenue_at_risk_inr,
        "expected_recovery_inr": expected_recovery_inr,
        "customers_intervention": customers_intervention
    }

@app.post("/api/agent/trigger")
def trigger_agent(request: Request):
    """Trigger the Gemini-powered investigative recovery agent for the merchant."""
    merchant_id = request.headers.get('x-merchant-id')
    if not merchant_id:
        raise HTTPException(status_code=401, detail="Missing x-merchant-id header")
    
    try:
        from agent.loop import run_agent_loop
        from agent.policy_engine import evaluate_draft_campaigns
        
        proposal, track = run_agent_loop(merchant_id, "Investigate failed payments and formulate optimal recovery strategy.")
        
        # Run deterministic policy validation on the newly produced DRAFT
        evaluate_draft_campaigns()
        
        campaign_id = proposal.get("campaign_id") if isinstance(proposal, dict) else None
        
        campaign = None
        if campaign_id:
            campaign = _execute_query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,), fetch_one=True)
            
        return {
            "status": "success",
            "campaign_id": campaign_id,
            "campaign": campaign,
            "evidence_track": track,
            "proposal": proposal
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/campaigns")
def get_campaigns(request: Request):
    """Get all campaigns for the inbox/dashboard."""
    merchant_id = request.headers.get('x-merchant-id')
    if not merchant_id: raise HTTPException(status_code=401)
    return _execute_query("SELECT * FROM campaigns WHERE merchant_id = ? ORDER BY created_at DESC", (merchant_id,))

@app.get("/api/campaigns/{campaign_id}")
def get_campaign_details(campaign_id: str, request: Request):
    merchant_id = request.headers.get('x-merchant-id')
    if not merchant_id: raise HTTPException(status_code=401)
    campaign = _execute_query("SELECT * FROM campaigns WHERE id = ? AND merchant_id = ?", (campaign_id, merchant_id), fetch_one=True)
    if not campaign:
        raise HTTPException(status_code=404)
    return campaign

@app.get("/api/campaigns/{campaign_id}/targets")
def get_campaign_targets(campaign_id: str, request: Request):
    merchant_id = request.headers.get('x-merchant-id')
    if not merchant_id: raise HTTPException(status_code=401)
    return _execute_query('''
        SELECT t.*, c.name, c.email, ro.status as recovery_status, ro.amount_recovered_paise
        FROM campaign_targets t
        JOIN customers c ON t.customer_id = c.id
        LEFT JOIN recovery_outcomes ro ON t.id = ro.campaign_target_id
        JOIN campaigns camp ON t.campaign_id = camp.id
        WHERE t.campaign_id = ? AND camp.merchant_id = ?
    ''', (campaign_id, merchant_id))

@app.post("/api/campaigns/{campaign_id}/approve")
def approve_campaign(campaign_id: str, request: Request):
    """Merchant explicitly approves a VALIDATED campaign."""
    merchant_id = request.headers.get('x-merchant-id')
    if not merchant_id:
        raise HTTPException(status_code=401, detail="Missing x-merchant-id header")
        
    campaign = _execute_query("SELECT status FROM campaigns WHERE id = ? AND merchant_id = ?", (campaign_id, merchant_id), fetch_one=True)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    if campaign['status'] != 'VALIDATED':
        raise HTTPException(status_code=400, detail="Only VALIDATED campaigns can be approved")
        
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _execute_query("UPDATE campaigns SET status = 'APPROVED', updated_at = ? WHERE id = ?", (now, campaign_id), commit=True)
    return {"status": "success", "message": "Campaign approved for execution."}

@app.post("/api/campaigns/{campaign_id}/execute")
def execute_campaign(campaign_id: str, request: Request):
    """
    Execution Worker Endpoint.
    Reads APPROVED (or interrupted EXECUTING) campaign, generates real payment links for targets, and tracks in recovery_outcomes.
    """
    merchant_id = request.headers.get('x-merchant-id')
    if not merchant_id:
        raise HTTPException(status_code=401, detail="Missing x-merchant-id header")
        
    campaign = _execute_query("SELECT * FROM campaigns WHERE id = ? AND merchant_id = ?", (campaign_id, merchant_id), fetch_one=True)
    if not campaign or campaign['status'] not in ['APPROVED', 'EXECUTING', 'PARTIAL_FAILURE']:
        raise HTTPException(status_code=400, detail="Campaign must be APPROVED, EXECUTING, or PARTIAL_FAILURE to execute")
        
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _execute_query("UPDATE campaigns SET status = 'EXECUTING', updated_at = ? WHERE id = ?", (now, campaign_id), commit=True)
    
    targets = _execute_query("SELECT * FROM campaign_targets WHERE campaign_id = ?", (campaign_id,))
    
    links_created = 0
    failed_targets = 0
    for t in targets:
        # Idempotency check: don't create duplicate links for targets that already have one
        if t['status'] in ['LINK_GENERATED', 'PAID']:
            continue
            
        # Atomic claim to prevent concurrent execution
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE campaign_targets SET status = 'PROCESSING' WHERE id = ? AND status IN ('PENDING', 'FAILED_TO_GENERATE')", (t['id'],))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_affected == 0:
            continue
            
        # Get customer details for link creation
        cust = _execute_query("SELECT name, email, phone FROM customers WHERE id = ? AND merchant_id = ?", (t['customer_id'], merchant_id), fetch_one=True)
        if not cust: 
            _execute_query("UPDATE campaign_targets SET status = 'FAILED_TO_GENERATE' WHERE id = ?", (t['id'],), commit=True)
            failed_targets += 1
            continue
        
        final_amount_inr = t['final_amount_paise'] / 100.0
        
        try:
            # Real Razorpay API call
            link_data = create_payment_link(
                customer_name=cust['name'] or "Customer",
                customer_email=cust['email'] or "no-reply@example.com",
                customer_phone=cust['phone'] or "9999999999",
                amount_in_inr=final_amount_inr,
                description=f"RazorOps Recovery: {t['recommended_action']}"
            )
            
            if link_data and 'id' in link_data:
                plink_id = link_data['id']
                # Create recovery outcome tracking row
                outcome_id = f"ro_{plink_id}"
                _execute_query('''
                    INSERT INTO recovery_outcomes (id, campaign_target_id, payment_link_id, amount_recovered_paise, status)
                    VALUES (?, ?, ?, 0, 'PENDING')
                ''', (outcome_id, t['id'], plink_id), commit=True)
                
                # Update target status
                _execute_query("UPDATE campaign_targets SET status = 'LINK_GENERATED' WHERE id = ?", (t['id'],), commit=True)
                links_created += 1
            else:
                _execute_query("UPDATE campaign_targets SET status = 'FAILED_TO_GENERATE' WHERE id = ?", (t['id'],), commit=True)
                failed_targets += 1
        except Exception as e:
            print(f"[Execute Error] Target {t['id']}: {e}")
            _execute_query("UPDATE campaign_targets SET status = 'FAILED_TO_GENERATE' WHERE id = ?", (t['id'],), commit=True)
            failed_targets += 1
                
    final_status = 'ACTIVE' if failed_targets == 0 else 'PARTIAL_FAILURE'
    _execute_query("UPDATE campaigns SET status = ?, updated_at = ? WHERE id = ?", (final_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), campaign_id), commit=True)
    
    return {"status": "success", "links_created": links_created, "failed": failed_targets, "final_status": final_status}

@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    """
    Idempotent webhook to close the loop on payment outcomes.
    Verifies the Razorpay signature using HMAC-SHA256.
    """
    webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET')
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="RAZORPAY_WEBHOOK_SECRET not configured")
        
    raw_body = await request.body()
    signature = request.headers.get('x-razorpay-signature')
    
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
        
    expected_signature = hmac.new(
        webhook_secret.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    payload = json.loads(raw_body)
    event = payload.get('event')
    
    if event == 'payment_link.paid':
        plink = payload.get('payload', {}).get('payment_link', {}).get('entity', {})
        plink_id = plink.get('id')
        amount_paid = plink.get('amount_paid', 0)
        
        if plink_id:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Look up the recovery outcome
            outcome = _execute_query("SELECT id, campaign_target_id, status FROM recovery_outcomes WHERE payment_link_id = ?", (plink_id,), fetch_one=True)
            
            if outcome and outcome['status'] != 'PAID':
                _execute_query('''
                    UPDATE recovery_outcomes 
                    SET status = 'PAID', amount_recovered_paise = ?, paid_at = ?
                    WHERE payment_link_id = ?
                ''', (amount_paid, now, plink_id), commit=True)
                
                # Update target record to PAID
                if outcome.get('campaign_target_id'):
                    _execute_query("UPDATE campaign_targets SET status = 'PAID' WHERE id = ?", (outcome['campaign_target_id'],), commit=True)
                    
                    # Check if all targets for this campaign are now concluded (PAID, EXPIRED, FAILED)
                    target = _execute_query("SELECT campaign_id FROM campaign_targets WHERE id = ?", (outcome['campaign_target_id'],), fetch_one=True)
                    if target and target.get('campaign_id'):
                        cid = target['campaign_id']
                        pending_count = _execute_query("SELECT COUNT(*) as count FROM campaign_targets WHERE campaign_id = ? AND status IN ('PENDING', 'PROCESSING', 'LINK_GENERATED')", (cid,), fetch_one=True)
                        if pending_count and pending_count['count'] == 0:
                            _execute_query("UPDATE campaigns SET status = 'COMPLETED', updated_at = ? WHERE id = ?", (now, cid), commit=True)
                            print(f"[Webhook] All targets concluded. Campaign {cid} marked as COMPLETED.")
                    
                print(f"[Webhook] Recorded recovery of {amount_paid/100} INR for link {plink_id}")


    elif event == 'payment_link.expired':
        plink = payload.get('payload', {}).get('payment_link', {}).get('entity', {})
        plink_id = plink.get('id')
        
        if plink_id:
            outcome = _execute_query("SELECT id, status FROM recovery_outcomes WHERE payment_link_id = ?", (plink_id,), fetch_one=True)
            if outcome and outcome['status'] not in ['PAID', 'EXPIRED']:
                _execute_query("UPDATE recovery_outcomes SET status = 'EXPIRED' WHERE payment_link_id = ?", (plink_id,), commit=True)
                print(f"[Webhook] Recorded expiration for link {plink_id}")

    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
