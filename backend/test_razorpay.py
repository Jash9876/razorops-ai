import os
from dotenv import load_dotenv
from razorpay_client import create_payment_link

load_dotenv()

def test_link_creation():
    key_id = os.getenv('RAZORPAY_KEY_ID')
    
    if not key_id or key_id == 'your_test_key_id_here':
        print("ERROR: Please provide a valid RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in the .env file.")
        return
        
    print(f"Testing Razorpay Payment Link creation with Key ID: {key_id[:8]}...")
    
    response = create_payment_link(
        customer_name="Test Judge",
        customer_email="judge@razorpay.com",
        customer_phone="9876543210",
        amount_in_inr=500.0,
        description="RazorOps AI Win-Back Campaign - Test Link"
    )
    
    if response and 'id' in response:
        print("\nSUCCESS! Payment link created.")
        print(f"Link ID: {response['id']}")
        print(f"URL: {response['short_url']}")
        print(f"Status: {response['status']}")
    else:
        print("\nFAILED to create payment link. See errors above.")

if __name__ == '__main__':
    test_link_creation()
