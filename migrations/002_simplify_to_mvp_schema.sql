-- Migration: Simplify to MVP Schema
-- Description: Removes unused tables (user_aspects, user_relationships) for MVP, keeps only birth charts and chat functionality

-- Drop unused tables (they will be recreated if needed in future)
-- Note: This will CASCADE delete all related data
DROP TABLE IF EXISTS user_aspects CASCADE;
DROP TABLE IF EXISTS user_relationships CASCADE;

-- Ensure user_birth_charts table exists with proper structure
-- (Already created in 001, but ensuring chart_data is JSONB for RapidAPI responses)
-- The chart_data JSONB field can store any RapidAPI response format

-- Verify index exists on user_birth_charts.user_id
-- (Already created in 001, but ensuring it exists)
CREATE INDEX IF NOT EXISTS idx_user_birth_charts_user_id ON user_birth_charts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_birth_charts_created_at ON user_birth_charts(created_at);

-- Note: user_birth_charts, chat_conversations, and chat_messages tables
-- are kept as they are needed for the MVP functionality

