import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

def test_gemini():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key_here':
        print("ERROR: GEMINI_API_KEY is not set.")
        return

    print("Testing Gemini LLM Strategy Generation...")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-3.1-pro-preview')
        
        prompt = """
        You are RazorOps AI, an expert Growth Agent for a fitness company 'FitFuel India'.
        I need a win-back campaign for the 'Premium' segment. We are targeting 5 high-churn-risk users.
        Output ONLY a valid JSON object with no markdown formatting.
        Format:
        {
          "segment": "Premium",
          "offer_type": "discount",
          "discount_percentage": <int>,
          "expected_recovery_inr": <float>,
          "discount_cost_inr": <float>,
          "net_gain_inr": <float>,
          "campaign_title": "<string>"
        }
        Assume average LTV is 15000 INR per user. Be realistic with numbers.
        """
        
        response = model.generate_content(prompt)
        print("\nSUCCESS! Gemini API is working. Raw output:")
        print(response.text)
    except Exception as e:
        print(f"\nFAILED: {str(e)}")

if __name__ == '__main__':
    test_gemini()
