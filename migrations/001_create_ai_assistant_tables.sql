-- Migration: Create tables for AI Astrology Assistant
-- Description: Creates normalized tables for storing user birth charts, aspects, relationships, and chat conversations

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: user_birth_charts
-- Stores user's birth chart data
CREATE TABLE IF NOT EXISTS user_birth_charts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    birth_data JSONB NOT NULL,
    chart_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: user_aspects
-- Stores natal and synastry aspects for user charts
CREATE TABLE IF NOT EXISTS user_aspects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    birth_chart_id UUID NOT NULL REFERENCES user_birth_charts(id) ON DELETE CASCADE,
    aspect_type TEXT NOT NULL CHECK (aspect_type IN ('natal', 'synastry')),
    aspect_data JSONB NOT NULL,
    subject2_id UUID REFERENCES user_birth_charts(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: user_relationships
-- Stores relationship compatibility data between two charts
CREATE TABLE IF NOT EXISTS user_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    subject1_id UUID NOT NULL REFERENCES user_birth_charts(id) ON DELETE CASCADE,
    subject2_id UUID NOT NULL REFERENCES user_birth_charts(id) ON DELETE CASCADE,
    compatibility_score FLOAT,
    relationship_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_relationship_pair UNIQUE (subject1_id, subject2_id)
);

-- Table: chat_conversations
-- Stores chat conversation metadata
CREATE TABLE IF NOT EXISTS chat_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: chat_messages
-- Stores individual messages in conversations
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_user_birth_charts_user_id ON user_birth_charts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_birth_charts_created_at ON user_birth_charts(created_at);

CREATE INDEX IF NOT EXISTS idx_user_aspects_user_id ON user_aspects(user_id);
CREATE INDEX IF NOT EXISTS idx_user_aspects_birth_chart_id ON user_aspects(birth_chart_id);
CREATE INDEX IF NOT EXISTS idx_user_aspects_aspect_type ON user_aspects(aspect_type);

CREATE INDEX IF NOT EXISTS idx_user_relationships_user_id ON user_relationships(user_id);
CREATE INDEX IF NOT EXISTS idx_user_relationships_subject1_id ON user_relationships(subject1_id);
CREATE INDEX IF NOT EXISTS idx_user_relationships_subject2_id ON user_relationships(subject2_id);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_id ON chat_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated_at ON chat_conversations(updated_at);

CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_user_birth_charts_updated_at
    BEFORE UPDATE ON user_birth_charts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_conversations_updated_at
    BEFORE UPDATE ON chat_conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE user_birth_charts ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_aspects ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Create RLS policies: Users can only access their own data
CREATE POLICY "Users can view their own birth charts"
    ON user_birth_charts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own birth charts"
    ON user_birth_charts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own birth charts"
    ON user_birth_charts FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own birth charts"
    ON user_birth_charts FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view their own aspects"
    ON user_aspects FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own aspects"
    ON user_aspects FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own aspects"
    ON user_aspects FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view their own relationships"
    ON user_relationships FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own relationships"
    ON user_relationships FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own relationships"
    ON user_relationships FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view their own conversations"
    ON chat_conversations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own conversations"
    ON chat_conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own conversations"
    ON chat_conversations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own conversations"
    ON chat_conversations FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view messages in their conversations"
    ON chat_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM chat_conversations
            WHERE chat_conversations.id = chat_messages.conversation_id
            AND chat_conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages in their conversations"
    ON chat_messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM chat_conversations
            WHERE chat_conversations.id = chat_messages.conversation_id
            AND chat_conversations.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete messages in their conversations"
    ON chat_messages FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM chat_conversations
            WHERE chat_conversations.id = chat_messages.conversation_id
            AND chat_conversations.user_id = auth.uid()
        )
    );

