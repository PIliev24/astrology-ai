-- Migration: Switch from monthly subscriptions to usage-based purchases
-- Adds message_credits and unlimited_until columns to user_subscriptions
-- Updates existing paid subscribers to lifetime unlimited access

-- Add new columns for usage-based model
ALTER TABLE user_subscriptions
  ADD COLUMN IF NOT EXISTS message_credits INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS unlimited_until TIMESTAMPTZ DEFAULT NULL;

-- Give existing paid subscribers lifetime unlimited access
UPDATE user_subscriptions
SET unlimited_until = '2099-12-31T23:59:59Z',
    status = 'lifetime'
WHERE status IN ('basic', 'pro') AND is_active = true;
