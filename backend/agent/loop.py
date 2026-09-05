import os
import json
import logging
from google import genai
from google.genai import types
from datetime import datetime
from agent.tools import (
    get_failed_payments,
    get_segment_analysis,
    get_customer_context,
    get_campaign_history,
    submit_campaign_proposal
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tools will be bound inside run_agent_loop

SYSTEM_INSTRUCTION = """
You are RazorOps AI, an autonomous revenue recovery agent.
Your objective is to investigate revenue loss and propose recovery campaigns.

You MUST follow this workflow dynamically using your tools:
1. Detect & Investigate: Call `get_failed_payments` to retrieve the failed attempts and target customer IDs (`target_customer_ids`). You can also call `get_segment_analysis` to check churn risk and value.
2. Review History: Check `get_campaign_history` for what has historically worked.
3. Formulate Strategy: Based on evidence, decide on the best intervention action and discount.
4. Propose: Call `submit_campaign_proposal` with your decision.

CRITICAL TARGET REQUIREMENT:
- The `targets` parameter in `submit_campaign_proposal` MUST be a list of concrete customer ID strings (e.g. `["cust_inline_pay_TX6THPXwWbdlrx", ...]`) retrieved directly from `get_failed_payments` or `get_segment_analysis`.
- You MUST NEVER pass generic or symbolic strings such as "failed_payment_customers", "high_ltv_customers", or "all". Any proposal with symbolic strings will be rejected.

Valid actions for proposals are: RETRY, NO_INCENTIVE, DISCOUNT, PAYMENT_LINK, REACTIVATION.

You have no execution permissions. Your proposal will be submitted as a DRAFT.
Base your decisions strictly on the tool evidence.
"""

def run_agent_loop(merchant_id: str, merchant_goal: str):
    logger.info(f"Starting agent loop for merchant {merchant_id} with goal: {merchant_goal}")
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
        
    client = genai.Client(api_key=api_key)
    
    # Securely bind merchant_id to tools
    def get_failed_payments(days: int = 7) -> dict:
        """Returns count, total volume, primary error codes, and concrete target_customer_ids for failed payments."""
        import agent.tools as t
        return t.get_failed_payments(merchant_id, days)

    def get_segment_analysis(segment_criteria: dict) -> dict:
        """Returns LTV distribution, average churn risk, and customer_ids for affected customers."""
        import agent.tools as t
        return t.get_segment_analysis(merchant_id, segment_criteria)

    def get_customer_context(customer_id: str) -> dict:
        """Deep dive into a specific customer's risk and value."""
        import agent.tools as t
        return t.get_customer_context(merchant_id, customer_id)

    def get_campaign_history(segment_type: str = "failed_renewals") -> dict:
        """Returns historical recovery rates for previous incentives."""
        import agent.tools as t
        return t.get_campaign_history(merchant_id, segment_type)

    def submit_campaign_proposal(action: str, discount: int, targets: list, campaign_name: str = "High-LTV Failed Payments") -> dict:
        """Submits a campaign proposal as a DRAFT. targets must be a list of concrete customer ID strings (e.g. ['cust_...']). Symbolic labels are strictly prohibited."""
        import agent.tools as t
        return t.submit_campaign_proposal(merchant_id, action, discount, targets, campaign_name)

    TOOL_FUNCTIONS = {
        "get_failed_payments": get_failed_payments,
        "get_segment_analysis": get_segment_analysis,
        "get_customer_context": get_customer_context,
        "get_campaign_history": get_campaign_history,
        "submit_campaign_proposal": submit_campaign_proposal
    }
    
    # Initialize the chat session with tools
    tool_list = list(TOOL_FUNCTIONS.values())
    
    # Tell the agent its context
    system_prompt = SYSTEM_INSTRUCTION + f"\nYou are acting on behalf of merchant: {merchant_id}."
    
    # Candidate models in order of resilience/availability
    candidate_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
    chat = None
    response = None
    last_err = None

    for model_name in candidate_models:
        try:
            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    system_instruction=system_prompt,
                    tools=tool_list,
                    temperature=0.1
                )
            )
            response = chat.send_message(merchant_goal)
            logger.info(f"Agent successfully initialized with model: {model_name}")
            break
        except Exception as e:
            logger.warning(f"Failed to initialize chat with model {model_name}: {e}")
            last_err = e
            continue

    # Evidence track to be saved later with the draft
    evidence_track = []

    if response is None:
        raise last_err


    
    # The agent might call a tool or respond immediately
    MAX_TURNS = 10
    turns = 0
    
    while turns < MAX_TURNS:
        turns += 1
        
        # Check if the model wants to call functions
        if response.function_calls:
            function_responses = []
            
            for function_call in response.function_calls:
                name = function_call.name
                args = function_call.args
                logger.info(f"[Agent Tool Call] {name}({args})")
                
                # Execute the tool
                if name in TOOL_FUNCTIONS:
                    try:
                        result = TOOL_FUNCTIONS[name](**args)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"Tool {name} not found"}
                    
                logger.info(f"[Agent Tool Result] {name} -> {result}")
                
                # Record the evidence
                evidence_track.append({
                    "tool": name,
                    "inputs": args,
                    "outputs": result,
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                function_responses.append(
                    types.Part.from_function_response(
                        name=name,
                        response={"result": result}
                    )
                )
                
                if name == "submit_campaign_proposal":
                    logger.info("Agent has submitted a proposal. Concluding agent loop.")
                    if isinstance(result, dict) and "campaign_id" in result:
                        _attach_evidence(result["campaign_id"], evidence_track)
                    return result, evidence_track
                    
            # Send all function responses back in one turn with automatic rate-limit backoff
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = chat.send_message(function_responses)
                    break
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str:
                        wait_seconds = 20 * (attempt + 1)
                        logger.warning(f"Rate limit / transient error encountered: {e}. Retrying in {wait_seconds}s (attempt {attempt+1}/{max_retries})...")
                        time.sleep(wait_seconds)
                    else:
                        raise e

        else:
            # Model responded with text, no tools
            logger.info(f"[Agent Message] {response.text}")
            # If the model didn't submit a proposal but stopped calling tools, it might be stuck or just explaining.
            # We will exit the loop.
            return {"status": "AGENT_MESSAGE", "message": response.text}, evidence_track

    logger.warning("Agent loop reached maximum turns.")
    return {"status": "MAX_TURNS_REACHED"}, evidence_track

def _attach_evidence(campaign_id: str, evidence_track: list):
    import sqlite3
    DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(DB_DIR, 'database', 'fitfuel.db')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE campaigns 
        SET agent_evidence = ?, updated_at = ?
        WHERE id = ?
    ''', (json.dumps(evidence_track), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), campaign_id))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Test the agent loop
    print("Testing RazorOps Agent Loop...")
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    result, track = run_agent_loop("merchant_acme_001", "Recover revenue from recent failed subscription payments.")
    print("Final Result:", result)
