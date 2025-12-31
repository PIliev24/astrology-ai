-- Migration: Add conversation-birth chart relations
-- Description: Creates junction table for many-to-many relationship between conversations and birth charts

-- Table: conversation_birth_charts
-- Junction table linking conversations to birth charts (many-to-many relationship)
CREATE TABLE IF NOT EXISTS conversation_birth_charts (
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    birth_chart_id UUID NOT NULL REFERENCES user_birth_charts(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (conversation_id, birth_chart_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_conversation_birth_charts_conversation_id ON conversation_birth_charts(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversation_birth_charts_birth_chart_id ON conversation_birth_charts(birth_chart_id);
CREATE INDEX IF NOT EXISTS idx_conversation_birth_charts_created_at ON conversation_birth_charts(created_at);

-- Enable Row Level Security (RLS)
ALTER TABLE conversation_birth_charts ENABLE ROW LEVEL SECURITY;

-- Create RLS policies: Users can only access links for their own conversations and charts
CREATE POLICY "Users can view links for their own conversations"
    ON conversation_birth_charts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM chat_conversations
            WHERE chat_conversations.id = conversation_birth_charts.conversation_id
            AND chat_conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert links for their own conversations"
    ON conversation_birth_charts FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM chat_conversations
            WHERE chat_conversations.id = conversation_birth_charts.conversation_id
            AND chat_conversations.user_id = auth.uid()
        )
        AND EXISTS (
            SELECT 1 FROM user_birth_charts
            WHERE user_birth_charts.id = conversation_birth_charts.birth_chart_id
            AND user_birth_charts.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete links for their own conversations"
    ON conversation_birth_charts FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM chat_conversations
            WHERE chat_conversations.id = conversation_birth_charts.conversation_id
            AND chat_conversations.user_id = auth.uid()
        )
    );

