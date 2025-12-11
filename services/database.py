"""
Database service layer for Supabase operations
Handles all CRUD operations for user birth charts, aspects, relationships, and conversations
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

from supabase import Client
from fastapi import HTTPException, status

from models.database import (
    UserBirthChart,
    UserBirthChartCreate,
    UserBirthChartUpdate,
    UserAspect,
    UserAspectCreate,
    UserRelationship,
    UserRelationshipCreate,
    ChatConversation,
    ChatConversationCreate,
    ChatConversationUpdate,
    ChatMessage,
    ChatMessageCreate,
    ConversationWithMessages,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Birth Chart Operations
# ============================================================================

def save_birth_chart(
    supabase: Client,
    user_id: str,
    chart_data: UserBirthChartCreate,
) -> UserBirthChart:
    """
    Save a birth chart to the database.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        chart_data: Birth chart data to save
    
    Returns:
        UserBirthChart: Saved birth chart with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        data = {
            "user_id": user_id,
            "name": chart_data.name,
            "birth_data": chart_data.birth_data,
            "chart_data": chart_data.chart_data,
        }
        
        response = supabase.table("user_birth_charts").insert(data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save birth chart"
            )
        
        return UserBirthChart(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving birth chart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save birth chart: {str(e)}"
        )


def get_user_birth_charts(
    supabase: Client,
    user_id: str,
    limit: Optional[int] = None,
) -> List[UserBirthChart]:
    """
    Get all birth charts for a user.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        limit: Optional limit on number of results
    
    Returns:
        List[UserBirthChart]: List of user's birth charts
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        query = supabase.table("user_birth_charts").select("*").eq("user_id", user_id).order("created_at", desc=True)
        
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        return [UserBirthChart(**item) for item in response.data]
    
    except Exception as e:
        logger.error(f"Error fetching user birth charts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth charts: {str(e)}"
        )


def get_birth_chart_by_id(
    supabase: Client,
    user_id: str,
    chart_id: str,
) -> UserBirthChart:
    """
    Get a specific birth chart by ID.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
    
    Returns:
        UserBirthChart: Birth chart data
    
    Raises:
        HTTPException: If chart not found or database operation fails
    """
    try:
        response = (
            supabase.table("user_birth_charts")
            .select("*")
            .eq("id", chart_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Birth chart not found"
            )
        
        return UserBirthChart(**response.data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching birth chart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth chart: {str(e)}"
        )


def update_birth_chart(
    supabase: Client,
    user_id: str,
    chart_id: str,
    update_data: UserBirthChartUpdate,
) -> UserBirthChart:
    """
    Update an existing birth chart.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
        update_data: Fields to update
    
    Returns:
        UserBirthChart: Updated birth chart
    
    Raises:
        HTTPException: If chart not found or update fails
    """
    try:
        # Build update dict from non-None fields
        update_dict = {}
        if update_data.name is not None:
            update_dict["name"] = update_data.name
        if update_data.birth_data is not None:
            update_dict["birth_data"] = update_data.birth_data
        if update_data.chart_data is not None:
            update_dict["chart_data"] = update_data.chart_data
        
        if not update_dict:
            # No fields to update, return existing chart
            return get_birth_chart_by_id(supabase, user_id, chart_id)
        
        response = (
            supabase.table("user_birth_charts")
            .update(update_dict)
            .eq("id", chart_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Birth chart not found"
            )
        
        return UserBirthChart(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating birth chart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update birth chart: {str(e)}"
        )


def delete_birth_chart(
    supabase: Client,
    user_id: str,
    chart_id: str,
) -> None:
    """
    Delete a birth chart.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
    
    Raises:
        HTTPException: If deletion fails
    """
    try:
        response = (
            supabase.table("user_birth_charts")
            .delete()
            .eq("id", chart_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        # Note: Supabase delete doesn't return data, so we can't verify if it existed
        logger.info(f"Birth chart {chart_id} deleted for user {user_id}")
    
    except Exception as e:
        logger.error(f"Error deleting birth chart: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete birth chart: {str(e)}"
        )


# ============================================================================
# Aspect Operations
# ============================================================================

def save_aspects(
    supabase: Client,
    user_id: str,
    aspect_data: UserAspectCreate,
) -> UserAspect:
    """
    Save aspect data to the database.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        aspect_data: Aspect data to save
    
    Returns:
        UserAspect: Saved aspect with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        data = {
            "user_id": user_id,
            "birth_chart_id": str(aspect_data.birth_chart_id),
            "aspect_type": aspect_data.aspect_type,
            "aspect_data": aspect_data.aspect_data,
        }
        
        if aspect_data.subject2_id:
            data["subject2_id"] = str(aspect_data.subject2_id)
        
        response = supabase.table("user_aspects").insert(data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save aspects"
            )
        
        return UserAspect(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving aspects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save aspects: {str(e)}"
        )


def get_user_aspects(
    supabase: Client,
    user_id: str,
    chart_id: Optional[str] = None,
    aspect_type: Optional[str] = None,
) -> List[UserAspect]:
    """
    Get aspects for a user, optionally filtered by chart or type.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        chart_id: Optional birth chart ID to filter by
        aspect_type: Optional aspect type filter ('natal' or 'synastry')
    
    Returns:
        List[UserAspect]: List of aspects
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        query = supabase.table("user_aspects").select("*").eq("user_id", user_id)
        
        if chart_id:
            query = query.eq("birth_chart_id", chart_id)
        
        if aspect_type:
            query = query.eq("aspect_type", aspect_type)
        
        query = query.order("created_at", desc=True)
        
        response = query.execute()
        
        return [UserAspect(**item) for item in response.data]
    
    except Exception as e:
        logger.error(f"Error fetching aspects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch aspects: {str(e)}"
        )


# ============================================================================
# Relationship Operations
# ============================================================================

def save_relationship(
    supabase: Client,
    user_id: str,
    relationship_data: UserRelationshipCreate,
) -> UserRelationship:
    """
    Save relationship data to the database.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        relationship_data: Relationship data to save
    
    Returns:
        UserRelationship: Saved relationship with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        data = {
            "user_id": user_id,
            "subject1_id": str(relationship_data.subject1_id),
            "subject2_id": str(relationship_data.subject2_id),
            "relationship_data": relationship_data.relationship_data,
        }
        
        if relationship_data.compatibility_score is not None:
            data["compatibility_score"] = relationship_data.compatibility_score
        
        response = supabase.table("user_relationships").insert(data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save relationship"
            )
        
        return UserRelationship(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving relationship: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save relationship: {str(e)}"
        )


def get_user_relationships(
    supabase: Client,
    user_id: str,
    chart_id: Optional[str] = None,
) -> List[UserRelationship]:
    """
    Get relationships for a user, optionally filtered by chart.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        chart_id: Optional chart ID to filter by (returns relationships where chart is subject1 or subject2)
    
    Returns:
        List[UserRelationship]: List of relationships
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        query = supabase.table("user_relationships").select("*").eq("user_id", user_id)
        
        if chart_id:
            query = query.or_(f"subject1_id.eq.{chart_id},subject2_id.eq.{chart_id}")
        
        query = query.order("created_at", desc=True)
        
        response = query.execute()
        
        return [UserRelationship(**item) for item in response.data]
    
    except Exception as e:
        logger.error(f"Error fetching relationships: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch relationships: {str(e)}"
        )


# ============================================================================
# Conversation Operations
# ============================================================================

def save_conversation(
    supabase: Client,
    user_id: str,
    conversation_data: ChatConversationCreate,
) -> ChatConversation:
    """
    Create a new conversation.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        conversation_data: Conversation data to create
    
    Returns:
        ChatConversation: Created conversation with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        data = {
            "user_id": user_id,
        }
        
        if conversation_data.title:
            data["title"] = conversation_data.title
        
        response = supabase.table("chat_conversations").insert(data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create conversation"
            )
        
        return ChatConversation(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}"
        )


def get_user_conversations(
    supabase: Client,
    user_id: str,
    limit: Optional[int] = None,
) -> List[ChatConversation]:
    """
    Get all conversations for a user.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        limit: Optional limit on number of results
    
    Returns:
        List[ChatConversation]: List of user's conversations
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        query = supabase.table("chat_conversations").select("*").eq("user_id", user_id).order("updated_at", desc=True)
        
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        return [ChatConversation(**item) for item in response.data]
    
    except Exception as e:
        logger.error(f"Error fetching conversations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(e)}"
        )


def get_conversation_by_id(
    supabase: Client,
    user_id: str,
    conversation_id: str,
) -> ChatConversation:
    """
    Get a specific conversation by ID.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
    
    Returns:
        ChatConversation: Conversation data
    
    Raises:
        HTTPException: If conversation not found or database operation fails
    """
    try:
        response = (
            supabase.table("chat_conversations")
            .select("*")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return ChatConversation(**response.data)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(e)}"
        )


def update_conversation(
    supabase: Client,
    user_id: str,
    conversation_id: str,
    update_data: ChatConversationUpdate,
) -> ChatConversation:
    """
    Update conversation metadata.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
        update_data: Fields to update
    
    Returns:
        ChatConversation: Updated conversation
    
    Raises:
        HTTPException: If conversation not found or update fails
    """
    try:
        update_dict = {}
        if update_data.title is not None:
            update_dict["title"] = update_data.title
        
        if not update_dict:
            return get_conversation_by_id(supabase, user_id, conversation_id)
        
        response = (
            supabase.table("chat_conversations")
            .update(update_dict)
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return ChatConversation(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update conversation: {str(e)}"
        )


def delete_conversation(
    supabase: Client,
    user_id: str,
    conversation_id: str,
) -> None:
    """
    Delete a conversation and all its messages.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
    
    Raises:
        HTTPException: If deletion fails
    """
    try:
        # Messages will be deleted automatically via CASCADE
        response = (
            supabase.table("chat_conversations")
            .delete()
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        logger.info(f"Conversation {conversation_id} deleted for user {user_id}")
    
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(e)}"
        )


# ============================================================================
# Message Operations
# ============================================================================

def save_message(
    supabase: Client,
    message_data: ChatMessageCreate,
) -> ChatMessage:
    """
    Save a chat message to the database.
    
    Args:
        supabase: Supabase client instance
        message_data: Message data to save
    
    Returns:
        ChatMessage: Saved message with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        data = {
            "conversation_id": str(message_data.conversation_id),
            "role": message_data.role,
            "content": message_data.content,
        }
        
        if message_data.metadata:
            data["metadata"] = message_data.metadata
        
        response = supabase.table("chat_messages").insert(data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save message"
            )
        
        return ChatMessage(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save message: {str(e)}"
        )


def get_conversation_history(
    supabase: Client,
    conversation_id: str,
    limit: Optional[int] = None,
) -> List[ChatMessage]:
    """
    Get message history for a conversation.
    
    Args:
        supabase: Supabase client instance
        conversation_id: Conversation ID (UUID string)
        limit: Optional limit on number of messages
    
    Returns:
        List[ChatMessage]: List of messages in chronological order
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        query = (
            supabase.table("chat_messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)  # Oldest first
        )
        
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        return [ChatMessage(**item) for item in response.data]
    
    except Exception as e:
        logger.error(f"Error fetching conversation history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation history: {str(e)}"
        )


def get_conversation_with_messages(
    supabase: Client,
    user_id: str,
    conversation_id: str,
    message_limit: Optional[int] = None,
) -> ConversationWithMessages:
    """
    Get a conversation with its messages.
    
    Args:
        supabase: Supabase client instance
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
        message_limit: Optional limit on number of messages
    
    Returns:
        ConversationWithMessages: Conversation with its messages
    
    Raises:
        HTTPException: If conversation not found or database operation fails
    """
    try:
        conversation = get_conversation_by_id(supabase, user_id, conversation_id)
        messages = get_conversation_history(supabase, conversation_id, message_limit)
        
        return ConversationWithMessages(
            conversation=conversation,
            messages=messages
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation with messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(e)}"
        )

