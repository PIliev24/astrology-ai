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


class UserAspect(BaseModel):
    """Model for user aspect data stored in database"""
    
    id: UUID = Field(..., description="Aspect ID")
    user_id: UUID = Field(..., description="User ID (foreign key to auth.users)")
    birth_chart_id: UUID = Field(..., description="Birth chart ID (foreign key to user_birth_charts)")
    aspect_type: Literal["natal", "synastry"] = Field(..., description="Type of aspect")
    aspect_data: Dict[str, Any] = Field(..., description="Aspect calculations")
    subject2_id: Optional[UUID] = Field(None, description="Second subject ID for synastry aspects")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {"from_attributes": True}


class UserAspectCreate(BaseModel):
    """Model for creating new aspect data"""
    
    birth_chart_id: UUID = Field(..., description="Birth chart ID")
    aspect_type: Literal["natal", "synastry"] = Field(..., description="Type of aspect")
    aspect_data: Dict[str, Any] = Field(..., description="Aspect calculations")
    subject2_id: Optional[UUID] = Field(None, description="Second subject ID for synastry aspects")


class UserRelationship(BaseModel):
    """Model for user relationship data stored in database"""
    
    id: UUID = Field(..., description="Relationship ID")
    user_id: UUID = Field(..., description="User ID (foreign key to auth.users)")
    subject1_id: UUID = Field(..., description="First subject ID (foreign key to user_birth_charts)")
    subject2_id: UUID = Field(..., description="Second subject ID (foreign key to user_birth_charts)")
    compatibility_score: Optional[float] = Field(None, description="Compatibility score (0-100)")
    relationship_data: Dict[str, Any] = Field(..., description="Full relationship analysis data")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {"from_attributes": True}


class UserRelationshipCreate(BaseModel):
    """Model for creating new relationship data"""
    
    subject1_id: UUID = Field(..., description="First subject ID")
    subject2_id: UUID = Field(..., description="Second subject ID")
    compatibility_score: Optional[float] = Field(None, description="Compatibility score (0-100)")
    relationship_data: Dict[str, Any] = Field(..., description="Full relationship analysis data")


class ChatConversation(BaseModel):
    """Model for chat conversation metadata"""
    
    id: UUID = Field(..., description="Conversation ID")
    user_id: UUID = Field(..., description="User ID (foreign key to auth.users)")
    title: Optional[str] = Field(None, description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
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

