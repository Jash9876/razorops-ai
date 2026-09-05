-- Core Domain
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,           -- Razorpay Customer ID
    merchant_id TEXT,
    name TEXT,
    email TEXT,
    phone TEXT,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,           -- Razorpay Sub ID
    customer_id TEXT REFERENCES customers(id),
    plan_id TEXT,
    status TEXT,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,           -- Razorpay Payment ID
    customer_id TEXT REFERENCES customers(id),
    amount_in_paise INTEGER,
    status TEXT,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payment_attempts (
    id TEXT PRIMARY KEY,
    transaction_id TEXT REFERENCES transactions(id),
    customer_id TEXT REFERENCES customers(id),
    status TEXT,                   -- 'failed', 'success'
    error_code TEXT,
    created_at TIMESTAMP
);

-- ML Predictions
CREATE TABLE IF NOT EXISTS predictions (
    customer_id TEXT REFERENCES customers(id) PRIMARY KEY,
    churn_risk REAL,
    predicted_ltv REAL,
    opportunity_score REAL,
    updated_at TIMESTAMP
);

-- Agent & Campaign Management
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    merchant_id TEXT,
    segment_name TEXT,
    status TEXT,                   -- DRAFT, VALIDATED, APPROVED, EXECUTING, ACTIVE, COMPLETED
    agent_evidence TEXT,           -- Observable inputs/outputs used by the agent
    policy_result_json TEXT,       -- Detailed policy checks result
    sys_expected_gross_inr REAL,
    sys_expected_cost_inr REAL,
    sys_expected_net_inr REAL,
    baseline_comparison_inr REAL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_targets (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    customer_id TEXT REFERENCES customers(id),
    recommended_action TEXT,       -- RETRY, NO_INCENTIVE, DISCOUNT, PAYMENT_LINK, REACTIVATION
    original_amount_paise INTEGER,
    discount_percentage INTEGER,
    discount_amount_paise INTEGER,
    final_amount_paise INTEGER,
    status TEXT                    -- PENDING, LINK_GENERATED, FAILED_TO_GENERATE, EXCLUDED
);

CREATE TABLE IF NOT EXISTS recovery_outcomes (
    id TEXT PRIMARY KEY,
    campaign_target_id TEXT REFERENCES campaign_targets(id),
    payment_link_id TEXT,          -- Razorpay Link ID
    amount_recovered_paise INTEGER,
    status TEXT,                   -- PENDING, PAID, EXPIRED
    paid_at TIMESTAMP
);

-- Config
CREATE TABLE IF NOT EXISTS merchant_config (
    id TEXT PRIMARY KEY,
    monthly_recovery_budget_inr REAL
);
