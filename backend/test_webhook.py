import sqlite3
import os
import requests
from agent.tools import get_campaign_history

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'fitfuel.db')

def test_webhook_and_learning():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT payment_link_id, campaign_target_id FROM recovery_outcomes WHERE status = 'PENDING' LIMIT 1")
    res = cursor.fetchone()
    
    if not res:
        print("No pending links to test.")
        conn.close()
        return
        
    plink_id, target_id = res
    
    cursor.execute("SELECT final_amount_paise FROM campaign_targets WHERE id = ?", (target_id,))
    final_amount = cursor.fetchone()[0]
    conn.close()
    
    print(f"Testing webhook for link {plink_id} with amount {final_amount} paise...")
    
    # Hit webhook
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {
                "entity": {
                    "id": plink_id,
                    "amount_paid": final_amount
                }
            }
        }
    }
    
    resp = client.post("/api/webhooks/razorpay", json=payload)
    print("Webhook Response:", resp.json())
    
    # Test Learning Loop
    print("Testing get_campaign_history...")
    history = get_campaign_history()
    print("Agent Learn Output:")
    print(history)

if __name__ == "__main__":
    test_webhook_and_learning()
