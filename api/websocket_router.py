"""
WebSocket Router for AI Astrology Assistant Chat
Handles real-time chat communication with AI agents via WebSocket
"""

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status, Query
from supabase import Client

from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent

from ai_agents.orchestrator_agent import orchestrator, OrchestratorContext
from middleware.auth import supabase_client
from services.database import (
    save_conversation,
    get_conversation_by_id,
    save_message,
    get_conversation_history,
)
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
    if not supabase_client:
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
        await websocket.send_json(connection_response.model_dump())
        
        # Create agent context
        context = OrchestratorContext(
            user_id=user_id,
            supabase=supabase_client,
        )
        
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
                    await websocket.send_json(error_response.model_dump())
                    continue
                
                # Save user message to database
                if not current_conversation_id:
                    if message_request.conversation_id:
                        # Try to load existing conversation
                        try:
                            conversation = get_conversation_by_id(
                                supabase_client,
                                user_id,
                                str(message_request.conversation_id),
                            )
                            current_conversation_id = conversation.id
                        except HTTPException:
                            # Conversation not found, create new one
                            new_conversation = save_conversation(
                                supabase_client,
                                user_id,
                                ChatConversationCreate(title=None),
                            )
                            current_conversation_id = new_conversation.id
                    else:
                        # Create new conversation
                        new_conversation = save_conversation(
                            supabase_client,
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
                        await websocket.send_json(conversation_response.model_dump())
                
                # Save user message
                user_message = save_message(
                    supabase_client,
                    ChatMessageCreate(
                        conversation_id=current_conversation_id,
                        role="user",
                        content=message_request.content,
                        metadata={
                            "chart_references": message_request.chart_references or [],
                        } if message_request.chart_references else None,
                    ),
                )
                
                # Get conversation history for context (last 10 messages)
                history = get_conversation_history(
                    supabase_client,
                    str(current_conversation_id),
                    limit=10,
                )
                
                # Build conversation history for agent
                # The agent will use this context automatically
                conversation_context = ""
                for msg in history[-5:]:  # Last 5 messages for context
                    conversation_context += f"{msg.role}: {msg.content}\n"
                
                # Prepare user input with context
                user_input = message_request.content
                if conversation_context:
                    # Add context to help agent understand conversation flow
                    user_input = f"[Previous conversation context]\n{conversation_context}\n[Current question]\n{user_input}"
                
                # Track tool calls for metadata
                tool_calls_metadata: list[ToolCallMetadata] = []
                
                # Run agent with streaming
                try:
                    result = Runner.run_streamed(
                        orchestrator,
                        input=user_input,
                        context=context,
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
                                tool_calls_metadata.append(
                                    ToolCallMetadata(
                                        tool_name=event.item.tool_name or "unknown",
                                        tool_input=event.item.input if hasattr(event.item, 'input') else None,
                                        tool_output=None,  # Will be updated when tool completes
                                        success=True,
                                    )
                                )
                            elif event.item.type == "tool_call_output_item":
                                # Update last tool call with output
                                if tool_calls_metadata:
                                    tool_calls_metadata[-1].tool_output = str(event.item.output)[:500]  # Truncate long outputs
                    
                    # Get final output
                    final_output = result.final_output or assistant_response_content
                    
                    # Save assistant message to database
                    assistant_message = save_message(
                        supabase_client,
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
                    await websocket.send_json(response.model_dump())
                
                except Exception as e:
                    logger.error(f"Error running agent: {str(e)}")
                    error_response = ErrorResponse(
                        type="error",
                        error=f"Failed to process message: {str(e)}",
                    )
                    await websocket.send_json(error_response.model_dump())
            
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

