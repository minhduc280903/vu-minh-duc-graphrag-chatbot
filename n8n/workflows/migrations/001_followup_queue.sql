-- Follow-up Queue Table for Drip Campaign
-- Run this migration to enable the follow-up workflow

CREATE TABLE IF NOT EXISTS followup_queue (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    page_id VARCHAR(50) NOT NULL,
    platform VARCHAR(20) DEFAULT 'messenger',
    
    -- Customer info
    customer_name VARCHAR(100),
    phone_number VARCHAR(20),
    
    -- Tracking
    first_interaction TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_interaction TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_followup TIMESTAMP WITH TIME ZONE,
    followup_count INTEGER DEFAULT 0,
    
    -- Consent
    opt_in_marketing BOOLEAN DEFAULT FALSE,
    notification_token VARCHAR(255),  -- For Marketing Messages API
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_converted BOOLEAN DEFAULT FALSE,
    
    -- Meta
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, page_id)
);

-- Index for efficient daily queries
CREATE INDEX IF NOT EXISTS idx_followup_stale 
ON followup_queue(last_interaction, followup_count, is_active) 
WHERE is_active = TRUE AND followup_count < 3;

-- Index for user lookup
CREATE INDEX IF NOT EXISTS idx_followup_user 
ON followup_queue(user_id, page_id);

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_followup_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for auto-update timestamp
DROP TRIGGER IF EXISTS followup_queue_updated ON followup_queue;
CREATE TRIGGER followup_queue_updated
    BEFORE UPDATE ON followup_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_followup_timestamp();

-- Sample insert (for testing)
-- INSERT INTO followup_queue (user_id, page_id, customer_name, opt_in_marketing)
-- VALUES ('123456789', 'page_001', 'Minh', TRUE);
