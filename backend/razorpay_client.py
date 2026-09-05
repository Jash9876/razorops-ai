import requests
import os
from dotenv import load_dotenv

BASE_URL = "https://api.razorpay.com/v1"
MERCHANT_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.merchant')
ROOT_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

def _get_auth():
    if os.path.exists(MERCHANT_ENV_FILE):
        load_dotenv(MERCHANT_ENV_FILE, override=True)
    key_id = os.getenv('RAZORPAY_KEY_ID')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET')
    
    # Fallback to root .env if .env.merchant has dummy/missing values
    if not key_id or not key_secret or key_id == 'rz':
        if os.path.exists(ROOT_ENV_FILE):
            load_dotenv(ROOT_ENV_FILE, override=True)
            key_id = os.getenv('RAZORPAY_KEY_ID')
            key_secret = os.getenv('RAZORPAY_KEY_SECRET')

    if not key_id or not key_secret or key_id == 'rz':
        raise ValueError("Missing real RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET in environment. Mock execution is strictly disabled.")
    return (key_id, key_secret)

def create_payment_link(customer_name, customer_email, customer_phone, amount_in_inr, description):
    """
    Creates a Razorpay Payment Link.
    Amount should be in INR (we will multiply by 100 to get paise for the API).
    """
    auth = _get_auth()
    url = f"{BASE_URL}/payment_links"
    
    amount_in_paise = int(amount_in_inr * 100)
    
    payload = {
        "amount": amount_in_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description,
        "customer": {
            "name": customer_name,
            "email": customer_email,
            "contact": customer_phone
        },
        "notify": {
            "sms": True,
            "email": True
        },
        "reminder_enable": True,
        # Real callback URL must be handled securely
        "callback_method": "get"
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            auth=auth,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        error_msg = f"Razorpay API Error: {e}"
        if e.response is not None:
            error_msg += f"\nResponse: {e.response.text}"
        raise RuntimeError(error_msg)

def fetch_all_payments():
    _require_auth()
    url = f"{BASE_URL}/payments"
    try:
        response = requests.get(url, auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        response.raise_for_status()
        return response.json().get('items', [])
    except Exception as e:
        raise RuntimeError(f"Error fetching payments: {e}")

def fetch_all_customers():
    _require_auth()
    url = f"{BASE_URL}/customers"
    try:
        response = requests.get(url, auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        response.raise_for_status()
        return response.json().get('items', [])
    except Exception as e:
        raise RuntimeError(f"Error fetching customers: {e}")

def fetch_all_subscriptions():
    _require_auth()
    url = f"{BASE_URL}/subscriptions"
    try:
        response = requests.get(url, auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        response.raise_for_status()
        return response.json().get('items', [])
    except Exception as e:
        raise RuntimeError(f"Error fetching subscriptions: {e}")
