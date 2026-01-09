"""
Pydantic models for AI/chat WebSocket communication
"""

from uuid import UUID
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Request model for incoming WebSocket chat messages"""
    
    type: Literal["message"] = Field("message", description="Message type")
    content: str = Field(..., description="Message content from user")
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID (null for new conversation)")
    chart_references: Optional[List[str]] = Field(
        None, 
        description="Optional list of chart IDs to include in context"
    )


class ToolCallMetadata(BaseModel):
    """Metadata about tool calls made by the agent"""
    
    tool_name: str = Field(..., description="Name of the tool that was called")
    tool_input: Optional[Dict[str, Any]] = Field(None, description="Input parameters to the tool")
    tool_output: Optional[str] = Field(None, description="Output from the tool (may be truncated)")
    success: bool = Field(..., description="Whether the tool call was successful")


class ChatMessageResponse(BaseModel):
    """Response model for outgoing WebSocket chat messages"""
    
    type: Literal["message", "error", "conversation_created"] = Field(
        ..., 
        description="Message type"
    )
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID")
    tool_calls: Optional[List[ToolCallMetadata]] = Field(
        None, 
        description="Metadata about tools used to generate the response"
    )
    chart_references: Optional[List[str]] = Field(
        None,
        description="Chart IDs referenced in this message"
    )


class ConversationResponse(BaseModel):
    """Response model for conversation metadata"""
    
    id: UUID = Field(..., description="Conversation ID")
    title: Optional[str] = Field(None, description="Conversation title")
    created_at: str = Field(..., description="Creation timestamp (ISO format)")
    updated_at: str = Field(..., description="Last update timestamp (ISO format)")
    message_count: Optional[int] = Field(None, description="Number of messages in conversation")


class ConversationListResponse(BaseModel):
    """Response model for listing user conversations"""
    
    conversations: List[ConversationResponse] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")


class ErrorResponse(BaseModel):
    """Error response model for WebSocket errors"""
    
    type: Literal["error"] = Field("error", description="Message type")
    error: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")


class ConnectionResponse(BaseModel):
    """Response model for WebSocket connection establishment"""
    
    type: Literal["connected"] = Field("connected", description="Message type")
    message: str = Field(..., description="Connection confirmation message")
    user_id: str = Field(..., description="Authenticated user ID")

