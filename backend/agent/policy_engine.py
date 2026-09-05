import sqlite3
import os
import json
from datetime import datetime

DB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(DB_DIR, 'database', 'fitfuel.db')

def _execute_query(query, params=(), commit=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    if commit:
        conn.commit()
        result = cursor.lastrowid
    else:
        result = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return result

# Platform baseline priors (Cold-start defaults)
BASELINE_CONVERSION = {
    'RETRY': 0.18,
    'NO_INCENTIVE': 0.18,
    'PAYMENT_LINK': 0.20,
    'DISCOUNT': 0.30, # assuming generic discount baseline
    'REACTIVATION': 0.25
}

def evaluate_draft_campaigns():
    """
    Finds all DRAFT campaigns.
    Calculates expected financial outcomes for the proposed targets.
    Enforces the monthly discount budget.
    Transitions valid campaigns to VALIDATED.
    """
    print("[Policy Engine] Scanning for DRAFT campaigns...")
    drafts = _execute_query("SELECT * FROM campaigns WHERE status = 'DRAFT'")
    if not drafts:
        print("[Policy Engine] No DRAFT campaigns found.")
        return
        
    for draft in drafts:
        campaign_id = draft['id']
        merchant_id = draft['merchant_id']
        targets = _execute_query("SELECT * FROM campaign_targets WHERE campaign_id = ?", (campaign_id,))
        
        expected_gross_paise = 0
        expected_discount_cost_paise = 0
        baseline_recovery_paise = 0
        
        for t in targets:
            action = t['recommended_action']
            discount_pct = t['discount_percentage'] or 0
            original_amount = t['original_amount_paise']
            
            # Compute discount amount
            discount_amount = int(original_amount * (discount_pct / 100.0))
            final_amount = original_amount - discount_amount
            
            # Use historical baseline conversion rate based on action
            conversion_rate = BASELINE_CONVERSION.get(action, 0.18)
            # Give a small conversion boost for higher discounts
            if action == 'DISCOUNT':
                conversion_rate += (discount_pct / 100.0) * 0.5
                
            expected_gross_paise += original_amount * conversion_rate
            expected_discount_cost_paise += discount_amount * conversion_rate
            
            # Compare against a "Do nothing but Retry" baseline
            baseline_recovery_paise += original_amount * BASELINE_CONVERSION['RETRY']
            
            # Update target record with math
            _execute_query('''
                UPDATE campaign_targets 
                SET discount_amount_paise = ?, final_amount_paise = ?
                WHERE id = ?
            ''', (discount_amount, final_amount, t['id']), commit=True)
            
        sys_expected_gross_inr = expected_gross_paise / 100.0
        sys_expected_cost_inr = expected_discount_cost_paise / 100.0
        sys_expected_net_inr = sys_expected_gross_inr - sys_expected_cost_inr
        baseline_comparison_inr = baseline_recovery_paise / 100.0
        
        print(f"[Policy Engine] Campaign {campaign_id}:")
        print(f"  - Expected Gross: INR {sys_expected_gross_inr:.2f}")
        print(f"  - Expected Cost: INR {sys_expected_cost_inr:.2f}")
        print(f"  - Baseline: INR {baseline_comparison_inr:.2f}")
        
        # Fetch budget constraint
        config = _execute_query("SELECT monthly_recovery_budget_inr FROM merchant_config WHERE id = ?", (merchant_id,))
        budget = config[0]['monthly_recovery_budget_inr'] if config else 25000.0
        
        # Calculate already committed budget for this month
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        committed_query = """
            SELECT SUM(sys_expected_cost_inr) as committed 
            FROM campaigns 
            WHERE merchant_id = ? 
            AND status IN ('VALIDATED', 'APPROVED', 'EXECUTING', 'ACTIVE', 'PARTIAL_FAILURE', 'COMPLETED')
            AND created_at >= ?
        """
        committed_res = _execute_query(committed_query, (merchant_id, current_month_start))
        committed_budget = committed_res[0]['committed'] if committed_res and committed_res[0]['committed'] else 0.0
        
        # Generate policy_result JSON
        max_discount_allowed = 15
        max_campaign_size = 100
        min_roi = 2.0
        
        # Max discount in targets
        max_requested_discount = max((t['discount_percentage'] or 0) for t in targets) if targets else 0
        actual_roi = sys_expected_net_inr / sys_expected_cost_inr if sys_expected_cost_inr > 0 else 999.0
        
        total_projected_cost = committed_budget + sys_expected_cost_inr
        budget_pass = total_projected_cost <= budget
        discount_pass = max_requested_discount <= max_discount_allowed
        size_pass = 1 <= len(targets) <= max_campaign_size
        roi_pass = (actual_roi >= min_roi or sys_expected_cost_inr == 0) and len(targets) > 0
        
        overall_pass = budget_pass and discount_pass and size_pass and roi_pass
        
        policy_result = {
            "passed": overall_pass,
            "checks": [
                {
                    "name": "Monthly Budget",
                    "passed": budget_pass,
                    "actual": total_projected_cost,
                    "limit": budget,
                    "display": f"₹{total_projected_cost:,.0f} / ₹{budget:,.0f}"
                },
                {
                    "name": "Discount",
                    "passed": discount_pass,
                    "actual": max_requested_discount,
                    "limit": max_discount_allowed,
                    "display": f"{max_requested_discount}% / {max_discount_allowed}%"
                },
                {
                    "name": "Campaign Size",
                    "passed": size_pass,
                    "actual": len(targets),
                    "limit": max_campaign_size,
                    "display": f"{len(targets)} / {max_campaign_size}"
                },
                {
                    "name": "ROI",
                    "passed": roi_pass,
                    "actual": actual_roi,
                    "limit": min_roi,
                    "display": f"{actual_roi:.1f}× / {min_roi:.1f}×" if sys_expected_cost_inr > 0 else "∞ / 2.0×"
                }
            ]
        }
        
        new_status = 'VALIDATED' if overall_pass else 'REJECTED'
        
        # Pass Validation (or rejection)
        _execute_query('''
            UPDATE campaigns 
            SET status = ?,
                sys_expected_gross_inr = ?,
                sys_expected_cost_inr = ?,
                sys_expected_net_inr = ?,
                baseline_comparison_inr = ?,
                policy_result_json = ?,
                updated_at = ?
            WHERE id = ?
        ''', (new_status, sys_expected_gross_inr, sys_expected_cost_inr, sys_expected_net_inr, baseline_comparison_inr, json.dumps(policy_result), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), campaign_id), commit=True)
        print(f"[Policy Engine] Campaign {campaign_id} {new_status}.")

if __name__ == '__main__':
    evaluate_draft_campaigns()
