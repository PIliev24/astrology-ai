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
    link_conversation_to_charts,
    get_conversation_history,
    update_conversation,
    get_or_create_user_subscription,
    get_user_usage,
    increment_user_message_count,
    reset_user_usage,
)
from utils.token_monitor import default_monitor
from supabase import create_client
from dotenv import load_dotenv
import os
from models.ai import (
    ChatMessageRequest,
    ChatMessageResponse,
    ErrorResponse,
    ConnectionResponse,
    StreamDeltaResponse,
    StreamEndResponse,
    ToolCallMetadata,
)
from models.database import ChatConversationCreate, ChatMessageCreate, ChatConversationUpdate
from models.subscription import PlanType
from services.usage_tracker import (
    can_send_message,
    get_effective_plan,
    get_remaining_free_messages,
    get_time_until_reset,
    is_paid_plan,
    should_reset_daily_usage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])
load_dotenv()

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
        logger.info("WebSocket authenticated: %s", user.id)
        
        return {
            "id": user.id,
            "email": user.email,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("WebSocket authentication failed: %s", str(e))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        ) from e


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
                
                # Check subscription and usage limits
                try:
                    # Get user's subscription and determine effective plan
                    subscription = get_or_create_user_subscription(user_id)
                    plan_type = get_effective_plan(subscription)

                    # Get user's current usage (for free tier tracking)
                    usage = get_user_usage(user_id)

                    # Reset free tier usage window if elapsed
                    if should_reset_daily_usage(usage):
                        usage = reset_user_usage(user_id)

                    # Check if user can send message
                    if not can_send_message(subscription, usage):
                        time_until_reset = get_time_until_reset(usage)
                        hours_until_reset = int(time_until_reset.total_seconds() / 3600)

                        error_response = ErrorResponse(
                            type="error",
                            error="purchase_required",
                            message=f"Message limit reached. Free tier allows 1 message per 48 hours. "
                                   f"Reset in {hours_until_reset} hours. Purchase a message pack or unlimited pass for more access.",
                        )
                        await websocket.send_json(error_response.model_dump(mode='json'))
                        logger.info("User %s exceeded free message limit", user_id)
                        continue

                except HTTPException:
                    raise
                except Exception as e:
                    logger.error("Error checking subscription limits for user %s: %s", user_id, str(e))
                    error_response = ErrorResponse(
                        type="error",
                        error="subscription_check_failed",
                        message="Failed to verify subscription limits. Please try again.",
                    )
                    await websocket.send_json(error_response.model_dump(mode='json'))
                    continue
                
                # Helper function to generate title from user message
                def generate_title_from_message(content: str, max_length: int = 100) -> str:
                    """Generate conversation title from user message, truncated if needed."""
                    title = content.strip()
                    if len(title) > max_length:
                        title = title[:max_length].rstrip() + "..."
                    return title
                
                # Get or create conversation
                # is_new_conversation = False
                if not current_conversation_id:
                    if message_request.conversation_id:
                        # Try to load existing conversation
                        try:
                            conversation = get_conversation_by_id(
                                user_id,
                                str(message_request.conversation_id),
                            )
                            current_conversation_id = conversation.id
                            # If conversation exists but has no title, check if this is the first message
                            if not conversation.title:
                                # Check if there are any existing messages
                                existing_messages = get_conversation_history(str(current_conversation_id), limit=1)
                                # Only set title if this is the first message (no existing messages)
                                if not existing_messages:
                                    title = generate_title_from_message(message_request.content)
                                    update_conversation(
                                        user_id,
                                        str(current_conversation_id),
                                        ChatConversationUpdate(title=title),
                                    )
                        except HTTPException:
                            # Conversation not found, create new one
                            # Use first user message as title (truncated to 100 chars)
                            title = generate_title_from_message(message_request.content)
                            new_conversation = save_conversation(
                                user_id,
                                ChatConversationCreate(title=title),
                            )
                            current_conversation_id = new_conversation.id
                            # is_new_conversation = True
                    else:
                        # Create new conversation
                        # Use first user message as title (truncated to 100 chars)
                        title = generate_title_from_message(message_request.content)
                        new_conversation = save_conversation(
                            user_id,
                            ChatConversationCreate(title=title),
                        )
                        current_conversation_id = new_conversation.id
                        # is_new_conversation = True
                        
                        # Send conversation created message
                        conversation_response = ChatMessageResponse(
                            type="conversation_created",
                            role="assistant",
                            content="",
                            conversation_id=current_conversation_id,
                        )
                        await websocket.send_json(conversation_response.model_dump(mode='json'))
                
                # Link conversation to birth charts if chart_references are provided
                if message_request.chart_references and len(message_request.chart_references) > 0:
                    try:
                        link_conversation_to_charts(
                            user_id,
                            str(current_conversation_id),
                            message_request.chart_references,
                        )
                    except Exception as e:
                        logger.warning("Failed to link conversation to charts: %s", str(e))
                        # Don't fail the request if linking fails
                
                # Save messages for all paid plans (credits, unlimited, lifetime)
                should_save_messages = is_paid_plan(plan_type)
                
                if should_save_messages:
                    save_message(
                        ChatMessageCreate(
                            conversation_id=current_conversation_id,
                            role="user",
                            content=message_request.content,
                            metadata={
                                "chart_references": message_request.chart_references or [],
                            } if message_request.chart_references else None,
                        ),
                    )
                
                # Prepare user input - append chart_references info if present
                # Note: Conversation history is handled automatically by the agents library
                # We don't manually pass it to reduce token usage
                user_input = message_request.content
                if message_request.chart_references and len(message_request.chart_references) > 0:
                    chart_refs_str = ", ".join(message_request.chart_references)
                    if len(message_request.chart_references) == 1:
                        user_input += f"\n\n[Note: Chart ID {chart_refs_str} is referenced. Use get_user_birth_chart(chart_ids=['{chart_refs_str}']) to fetch it.]"
                    else:
                        user_input += f"\n\n[Note: Chart IDs {chart_refs_str} are referenced. Use get_user_birth_chart(chart_ids={message_request.chart_references}) to fetch them.]"
                
                # Check token usage before running agent
                within_limit, token_count, message = default_monitor.check_limit(user_input)
                if not within_limit:
                    error_msg = default_monitor.get_user_friendly_error(token_count)
                    await websocket.send_json(ErrorResponse(
                        error="request_too_large",
                        message=error_msg
                    ).model_dump())
                    continue
                elif message:
                    logger.info("Token usage warning: %s", message)
                
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

                                # Send delta immediately to client
                                await websocket.send_json(
                                    StreamDeltaResponse(
                                        content=delta,
                                        conversation_id=current_conversation_id,
                                    ).model_dump(mode="json")
                                )
                        
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
                    
                    # Check token usage on response
                    within_limit, token_count, message = default_monitor.check_limit(final_output)
                    if not within_limit:
                        logger.warning("Response exceeded token limit: %s", token_count)
                        # Truncate response if needed
                        final_output = default_monitor.truncate_content(
                            final_output, 
                            default_monitor.limit - 10000
                        )
                        final_output += "\n\n[Response truncated due to size limits. Please ask more specific questions.]"
                    elif message:
                        logger.info("Response token usage warning: %s", message)
                    
                    # Save assistant message to database for paid plans
                    if should_save_messages:
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
                    
                    # Deduct usage after successful response
                    try:
                        if plan_type == PlanType.CREDITS:
                            from services.database import deduct_message_credit
                            deduct_message_credit(user_id)
                            logger.debug("Deducted 1 credit for user %s", user_id)
                        elif plan_type == PlanType.FREE:
                            increment_user_message_count(user_id)
                            logger.debug("Incremented free message count for user %s", user_id)
                        # LIFETIME and UNLIMITED: no deduction needed
                    except Exception as e:
                        logger.error("Failed to track usage for user %s: %s", user_id, str(e))
                    
                    # Send stream end signal
                    await websocket.send_json(
                        StreamEndResponse(
                            conversation_id=current_conversation_id,
                            tool_calls=tool_calls_metadata if tool_calls_metadata else None,
                            chart_references=message_request.chart_references,
                        ).model_dump(mode="json")
                    )
                
                except Exception as e:
                    logger.error("Error running agent: %s", str(e))
                    error_response = ErrorResponse(
                        type="error",
                        error=f"Failed to process message: {str(e)}",
                    )
                    await websocket.send_json(error_response.model_dump(mode='json'))
            
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected for user %s", user_id)
                break
            
            except json.JSONDecodeError:
                error_response = ErrorResponse(
                    type="error",
                    error="Invalid JSON format",
                )
                await websocket.send_json(error_response.model_dump())
            
            except Exception as e:
                logger.error("Error in WebSocket message loop: %s", str(e))
                error_response = ErrorResponse(
                    type="error",
                    error=f"Unexpected error: {str(e)}",
                )
                await websocket.send_json(error_response.model_dump())
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    
    except Exception as e:
        logger.error("WebSocket error: %s", str(e))
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass

