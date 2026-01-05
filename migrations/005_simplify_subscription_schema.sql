-- Migration: Simplify subscription schema
-- Remove: current_period_start, cancel_at, canceled_at, billing_status
-- Add: is_active boolean
-- Keep: current_period_end (preserved during cancellation)

-- Step 1: Add is_active column with default value
ALTER TABLE user_subscriptions 
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- Step 2: Make is_active NOT NULL after data migration
ALTER TABLE user_subscriptions
ALTER COLUMN is_active SET NOT NULL;

-- Step 3: Drop columns that are no longer needed
ALTER TABLE user_subscriptions
DROP COLUMN IF EXISTS current_period_start,
DROP COLUMN IF EXISTS cancel_at,
DROP COLUMN IF EXISTS canceled_at,
DROP COLUMN IF EXISTS billing_status;
