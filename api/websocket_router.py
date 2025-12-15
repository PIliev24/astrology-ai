"""
WebSocket Router for AI Astrology Assistant Chat
Handles real-time chat communication with AI agents via WebSocket
"""

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status, Query

from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent

from ai_agents.astrology_specialist_agent import astrology_specialist, AgentContext
from services.database import (
    save_conversation,
    get_conversation_by_id,
    save_message,
)
from supabase import create_client
import os
from models.ai import (
    ChatMessageRequest,
    ChatMessageResponse,
    ErrorResponse,
    ConnectionResponse,
    ToolCallMetadata,
)
from models.database import ChatConversationCreate, ChatMessageCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


async def authenticate_websocket(websocket: WebSocket, token: Optional[str] = None) -> dict:
    """
    Authenticate WebSocket connection using JWT token from query params.
    
    Args:
        websocket: WebSocket connection
        token: JWT token from query parameter
    
    Returns:
        dict: User information from verified token
    
    Raises:
        HTTPException: If authentication fails
    """
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
    
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not configured"
        )
    
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token"
        )
    
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
        user_response = supabase_client.auth.get_user(token)
        
        if not user_response or not user_response.user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        user = user_response.user
        logger.info(f"WebSocket authenticated: {user.id}")
        
        return {
            "id": user.id,
            "email": user.email,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {str(e)}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.websocket("/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT authentication token"),
):
    """
    WebSocket endpoint for AI astrology assistant chat.
    
    Authenticates user, maintains conversation context, and streams AI responses.
    
    Message format (client -> server):
    {
        "type": "message",
        "content": "What does my sun sign mean?",
        "conversation_id": "uuid" | null,
        "chart_references": ["chart_id_1"]
    }
    
    Response format (server -> client):
    {
        "type": "message" | "error" | "conversation_created",
        "role": "user" | "assistant",
        "content": "Response text",
        "conversation_id": "uuid",
        "tool_calls": [...],
        "chart_references": [...]
    }
    """
    await websocket.accept()
    
    try:
        # Authenticate user
        user = await authenticate_websocket(websocket, token)
        user_id = user["id"]
        
        # Send connection confirmation
        connection_response = ConnectionResponse(
            type="connected",
            message="Connected to astrology assistant",
            user_id=user_id,
        )
        await websocket.send_json(connection_response.model_dump(mode='json'))
        
        # Current conversation ID (may be None for new conversations)
        current_conversation_id: Optional[UUID] = None
        
        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                
                # Validate message format
                try:
                    message_request = ChatMessageRequest(**data)
                except Exception as e:
                    error_response = ErrorResponse(
                        type="error",
                        error=f"Invalid message format: {str(e)}",
                    )
                    await websocket.send_json(error_response.model_dump(mode='json'))
                    continue
                
                # Save user message to database
                if not current_conversation_id:
                    if message_request.conversation_id:
                        # Try to load existing conversation
                        try:
                            conversation = get_conversation_by_id(
                                user_id,
                                str(message_request.conversation_id),
                            )
                            current_conversation_id = conversation.id
                        except HTTPException:
                            # Conversation not found, create new one
                            new_conversation = save_conversation(
                                user_id,
                                ChatConversationCreate(title=None),
                            )
                            current_conversation_id = new_conversation.id
                    else:
                        # Create new conversation
                        new_conversation = save_conversation(
                            user_id,
                            ChatConversationCreate(title=None),
                        )
                        current_conversation_id = new_conversation.id
                        
                        # Send conversation created message
                        conversation_response = ChatMessageResponse(
                            type="conversation_created",
                            role="assistant",
                            content="",
                            conversation_id=current_conversation_id,
                        )
                        await websocket.send_json(conversation_response.model_dump(mode='json'))
                
                # Prepare user input - append chart_references info if present
                # Note: Conversation history is handled automatically by the agents library
                # We don't manually pass it to reduce token usage
                user_input = message_request.content
                if message_request.chart_references and len(message_request.chart_references) > 0:
                    chart_refs_str = ", ".join(message_request.chart_references)
                    if len(message_request.chart_references) == 1:
                        user_input += f"\n\n[Note: Chart ID {chart_refs_str} is referenced in this conversation. Use get_user_birth_chart with chart_id='{chart_refs_str}' or chart_ids=['{chart_refs_str}'] to fetch it.]"
                    else:
                        user_input += f"\n\n[Note: Chart IDs {chart_refs_str} are referenced. Use get_user_birth_chart with chart_ids={message_request.chart_references} to fetch them.]"
                
                # Track tool calls for metadata
                tool_calls_metadata: list[ToolCallMetadata] = []
                
                # Create MINIMAL agent context - only user_id to reduce token usage
                agent_context = AgentContext(user_id=user_id)
                
                # Run agent with streaming and context
                try:
                    result = Runner.run_streamed(
                        astrology_specialist,
                        input=user_input,
                        context=agent_context,
                    )
                    
                    # Stream response
                    assistant_response_content = ""
                    async for event in result.stream_events():
                        # Handle text delta events for streaming
                        if event.type == "raw_response_event":
                            if isinstance(event.data, ResponseTextDeltaEvent):
                                delta = event.data.delta
                                assistant_response_content += delta
                                
                                # Send incremental updates (optional - can be disabled for less frequent updates)
                                # For now, we'll send the full response at the end
                                pass
                        
                        # Track tool calls
                        elif event.type == "run_item_stream_event":
                            if event.item.type == "tool_call_item":
                                # Safely extract tool name - check multiple possible attribute names
                                tool_name = "unknown"
                                if hasattr(event.item, 'tool_name'):
                                    tool_name = event.item.tool_name
                                elif hasattr(event.item, 'name'):
                                    tool_name = event.item.name
                                elif hasattr(event.item, 'function_name'):
                                    tool_name = event.item.function_name
                                
                                tool_input = None
                                if hasattr(event.item, 'input'):
                                    tool_input = event.item.input
                                elif hasattr(event.item, 'arguments'):
                                    tool_input = event.item.arguments
                                
                                tool_calls_metadata.append(
                                    ToolCallMetadata(
                                        tool_name=tool_name or "unknown",
                                        tool_input=tool_input,
                                        tool_output=None,  # Will be updated when tool completes
                                        success=True,
                                    )
                                )
                            elif event.item.type == "tool_call_output_item":
                                # Update last tool call with output
                                if tool_calls_metadata:
                                    output = None
                                    if hasattr(event.item, 'output'):
                                        output = event.item.output
                                    elif hasattr(event.item, 'result'):
                                        output = event.item.result
                                    if output is not None:
                                        tool_calls_metadata[-1].tool_output = str(output)[:500]  # Truncate long outputs
                    
                    # Get final output
                    final_output = result.final_output or assistant_response_content
                    
                    # Save assistant message to database
                    save_message(
                        ChatMessageCreate(
                            conversation_id=current_conversation_id,
                            role="assistant",
                            content=final_output,
                            metadata={
                                "tool_calls": [
                                    {
                                        "tool_name": tc.tool_name,
                                        "success": tc.success,
                                    }
                                    for tc in tool_calls_metadata
                                ],
                                "chart_references": message_request.chart_references or [],
                            } if tool_calls_metadata or message_request.chart_references else None,
                        ),
                    )
                    
                    # Send final response
                    response = ChatMessageResponse(
                        type="message",
                        role="assistant",
                        content=final_output,
                        conversation_id=current_conversation_id,
                        tool_calls=tool_calls_metadata if tool_calls_metadata else None,
                        chart_references=message_request.chart_references,
                    )
                    await websocket.send_json(response.model_dump(mode='json'))
                
                except Exception as e:
                    logger.error(f"Error running agent: {str(e)}")
                    error_response = ErrorResponse(
                        type="error",
                        error=f"Failed to process message: {str(e)}",
                    )
                    await websocket.send_json(error_response.model_dump(mode='json'))
            
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for user {user_id}")
                break
            
            except json.JSONDecodeError:
                error_response = ErrorResponse(
                    type="error",
                    error="Invalid JSON format",
                )
                await websocket.send_json(error_response.model_dump())
            
            except Exception as e:
                logger.error(f"Error in WebSocket message loop: {str(e)}")
                error_response = ErrorResponse(
                    type="error",
                    error=f"Unexpected error: {str(e)}",
                )
                await websocket.send_json(error_response.model_dump())
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass

