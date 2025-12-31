"""
Conversation Router
Handles conversation management endpoints (list, get, delete, get by chart)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from uuid import UUID
from typing import List

from models.database import ConversationWithMessages, ChatConversation, ChartWithConversations
from services.database import (
    get_user_conversations,
    get_conversation_with_messages,
    delete_conversation,
    get_chart_with_conversations,
)
from middleware.auth import get_current_user

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get(
    "",
    response_model=List[ChatConversation],
    summary="List user's conversations",
    description="Get all conversations for the authenticated user, optionally including linked birth chart IDs"
)
async def list_conversations(
    include_charts: bool = False,
    limit: int = None,
    user: dict = Depends(get_current_user),
):
    """
    Get all conversations for the authenticated user.
    
    Args:
        include_charts: If True, include birth_chart_ids in response
        limit: Optional limit on number of results
        user: Current authenticated user
    
    Returns:
        List[ChatConversation]: List of user's conversations
    """
    try:
        conversations = get_user_conversations(
            user["id"],
            limit=limit,
            include_chart_ids=include_charts,
        )
        return conversations
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(e)}"
        )


@router.get(
    "/{conversation_id}",
    response_model=ConversationWithMessages,
    summary="Get conversation by ID",
    description="Get a specific conversation with its messages by ID"
)
async def get_conversation(
    conversation_id: UUID,
    message_limit: int = None,
    user: dict = Depends(get_current_user),
):
    """
    Get a specific conversation by ID with its messages.
    
    Args:
        conversation_id: Conversation ID
        message_limit: Optional limit on number of messages to return
        user: Current authenticated user
    
    Returns:
        ConversationWithMessages: Conversation with its messages
    """
    try:
        conversation = get_conversation_with_messages(
            user["id"],
            str(conversation_id),
            message_limit=message_limit,
        )
        return conversation
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(e)}"
        )


@router.get(
    "/by-chart/{chart_id}",
    response_model=ChartWithConversations,
    summary="Get birth chart with conversations",
    description="Get a birth chart with all its linked conversations"
)
async def get_chart_with_conversations_endpoint(
    chart_id: UUID,
    conversation_limit: int = None,
    user: dict = Depends(get_current_user),
):
    """
    Get a birth chart with all its linked conversations.
    
    Args:
        chart_id: Birth chart ID
        conversation_limit: Optional limit on number of conversations to return
        user: Current authenticated user
    
    Returns:
        ChartWithConversations: Birth chart with its linked conversations
    """
    try:
        chart_with_conversations = get_chart_with_conversations(
            user["id"],
            str(chart_id),
            conversation_limit=conversation_limit,
        )
        return chart_with_conversations
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chart with conversations: {str(e)}"
        )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
    description="Delete a conversation and all its messages (cascades to chart links)"
)
async def delete_conversation_endpoint(
    conversation_id: UUID,
    user: dict = Depends(get_current_user),
):
    """
    Delete a conversation by ID.
    This will also delete all messages and chart links via CASCADE.
    
    Args:
        conversation_id: Conversation ID to delete
        user: Current authenticated user
    """
    try:
        delete_conversation(user["id"], str(conversation_id))
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(e)}"
        )

