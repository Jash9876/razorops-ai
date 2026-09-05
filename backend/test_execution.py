import sqlite3
import os
import requests

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'fitfuel.db')

def test_pipeline():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM campaigns WHERE status = 'VALIDATED' LIMIT 1")
    res = cursor.fetchone()
    conn.close()
    
    if not res:
        print("No VALIDATED campaigns found.")
        return
        
    camp_id = res[0]
    print(f"Found VALIDATED campaign {camp_id}. Testing Approval API...")
    
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    
    resp = client.post(f"/api/campaigns/{camp_id}/approve", headers={"x-merchant-id": "merchant_123"})
    print("Approve Response:", resp.json())
    
    print(f"Testing Execution API...")
    resp = client.post(f"/api/campaigns/{camp_id}/execute", headers={"x-merchant-id": "merchant_123"})
    print("Execute Response:", resp.json())

if __name__ == "__main__":
    test_pipeline()
