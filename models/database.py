"""
Pydantic models for database entities
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


class UserBirthChart(BaseModel):
    """Model for user birth chart data stored in database"""
    
    id: UUID = Field(..., description="Birth chart ID")
    user_id: UUID = Field(..., description="User ID (foreign key to auth.users)")
    name: str = Field(..., description="Person's name")
    birth_data: Dict[str, Any] = Field(..., description="Full birth data (year, month, day, hour, minute, location)")
    chart_data: Dict[str, Any] = Field(..., description="Calculated chart data (planets, houses)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    model_config = {"from_attributes": True}


class UserBirthChartCreate(BaseModel):
    """Model for creating a new birth chart"""
    
    name: str = Field(..., description="Person's name")
    birth_data: Dict[str, Any] = Field(..., description="Full birth data")
    chart_data: Dict[str, Any] = Field(..., description="Calculated chart data")


class UserBirthChartUpdate(BaseModel):
    """Model for updating an existing birth chart"""
    
    name: Optional[str] = Field(None, description="Person's name")
    birth_data: Optional[Dict[str, Any]] = Field(None, description="Full birth data")
    chart_data: Optional[Dict[str, Any]] = Field(None, description="Calculated chart data")




class ChatConversation(BaseModel):
    """Model for chat conversation metadata"""
    
    id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="User ID (foreign key to auth.users)")
    title: Optional[str] = Field(None, description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    birth_chart_ids: Optional[list[UUID]] = Field(None, description="List of linked birth chart IDs (optional, for listing)")
    
    model_config = {"from_attributes": True}


class ChatConversationCreate(BaseModel):
    """Model for creating a new conversation"""
    
    title: Optional[str] = Field(None, description="Conversation title")


class ChatConversationUpdate(BaseModel):
    """Model for updating conversation metadata"""
    
    title: Optional[str] = Field(None, description="Conversation title")


class ChatMessage(BaseModel):
    """Model for chat message data"""
    
    id: UUID = Field(..., description="Message ID")
    conversation_id: UUID = Field(..., description="Conversation ID (foreign key to chat_conversations)")
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (tool calls, chart references, etc.)")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    """Model for creating a new chat message"""
    
    conversation_id: UUID = Field(..., description="Conversation ID")
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChatMessageResponse(BaseModel):
    """Response model for chat messages with conversation context"""
    
    message: ChatMessage = Field(..., description="Message data")
    conversation: Optional[ChatConversation] = Field(None, description="Conversation metadata")


class ConversationWithMessages(BaseModel):
    """Model for conversation with its messages"""
    
    conversation: ChatConversation = Field(..., description="Conversation metadata")
    messages: list[ChatMessage] = Field(..., description="List of messages in the conversation")


class ConversationBirthChart(BaseModel):
    """Model for conversation-birth chart junction table"""
    
    conversation_id: UUID = Field(..., description="Conversation ID")
    birth_chart_id: UUID = Field(..., description="Birth chart ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {"from_attributes": True}


class ConversationWithCharts(BaseModel):
    """Model for conversation with its linked birth charts"""
    
    conversation: ChatConversation = Field(..., description="Conversation metadata")
    birth_chart_ids: list[UUID] = Field(default_factory=list, description="List of linked birth chart IDs")


class ChartWithConversations(BaseModel):
    """Model for birth chart with its linked conversations"""
    
    chart: UserBirthChart = Field(..., description="Birth chart data")
    conversations: list[ChatConversation] = Field(default_factory=list, description="List of conversations linked to this chart")
