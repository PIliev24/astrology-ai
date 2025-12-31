"""
Database service layer for Supabase operations
Handles all CRUD operations for user birth charts, aspects, relationships, and conversations
"""

import os
from typing import Optional, List
from uuid import UUID
import logging

from supabase import create_client, Client
from fastapi import HTTPException, status

from models.database import (
    UserBirthChart,
    UserBirthChartCreate,
    UserBirthChartUpdate,
    ChatConversation,
    ChatConversationCreate,
    ChatConversationUpdate,
    ChatMessage,
    ChatMessageCreate,
    ConversationWithMessages,
    ConversationWithCharts,
    ChartWithConversations,
)

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


def _create_supabase_client() -> Client:
    """
    Create a Supabase client instance using service role key.
    Service role key bypasses RLS, which is appropriate for backend services.
    User authorization is enforced at the application level via user_id checks.
    
    Returns:
        Client: Supabase client instance
    
    Raises:
        HTTPException: If Supabase credentials are not configured
    """
    if not SUPABASE_URL:
        logger.error("SUPABASE_URL environment variable is not set")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase URL not configured. Please set SUPABASE_URL environment variable."
        )
    
    if not SUPABASE_SECRET_KEY:
        logger.error("SUPABASE_SECRET_KEY environment variable is not set")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase service role key not configured. Please set SUPABASE_SECRET_KEY environment variable. You can find it in your Supabase dashboard under Project Settings > API > service_role key (secret)."
        )
    
    return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


# ============================================================================
# Birth Chart Operations
# ============================================================================

def save_birth_chart(
    user_id: str,
    chart_data: UserBirthChartCreate,
) -> UserBirthChart:
    """
    Save a birth chart to the database.
    
    Args:
        user_id: User ID (UUID string)
        chart_data: Birth chart data to save
    
    Returns:
        UserBirthChart: Saved birth chart with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
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
    user_id: str,
    limit: Optional[int] = None,
) -> List[UserBirthChart]:
    """
    Get all birth charts for a user (returns only id, name, and birth_data for list view).
    
    Args:
        user_id: User ID (UUID string)
        limit: Optional limit on number of results
    
    Returns:
        List[UserBirthChart]: List of user's birth charts (with only id, name, birth_data)
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        # Only select id, name, and birth_data to avoid loading large chart_data (SVG)
        query = supabase.table("user_birth_charts").select("id,name,birth_data,created_at,updated_at").eq("user_id", user_id).order("created_at", desc=True)
        
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        # Create UserBirthChart objects with chart_data as empty dict (since we didn't select it)
        return [
            UserBirthChart(
                id=item["id"],
                user_id=user_id,
                name=item["name"],
                birth_data=item["birth_data"],
                chart_data={},  # Empty since we didn't select it
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            )
            for item in response.data
        ]
    
    except Exception as e:
        logger.error(f"Error fetching user birth charts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth charts: {str(e)}"
        )


def get_birth_chart_by_id(
    user_id: str,
    chart_id: str,
) -> UserBirthChart:
    """
    Get a specific birth chart by ID.
    
    Args:
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
    
    Returns:
        UserBirthChart: Birth chart data
    
    Raises:
        HTTPException: If chart not found or database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
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


def get_birth_data_by_chart_ids(
    user_id: str,
    chart_ids: List[str],
) -> List[dict]:
    """
    Get birth_data only for specified charts (for compatibility calculations).
    Does not fetch chart_data to reduce token usage.
    
    Args:
        user_id: User ID (UUID string)
        chart_ids: List of birth chart IDs (UUID strings)
    
    Returns:
        List of dictionaries containing id, name, and birth_data for each chart
    
    Raises:
        HTTPException: If charts not found or database operation fails
    """
    if not chart_ids:
        return []
    
    try:
        supabase = _create_supabase_client()
        
        # Fetch only id, name, and birth_data (no chart_data)
        response = (
            supabase.table("user_birth_charts")
            .select("id,name,birth_data")
            .eq("user_id", user_id)
            .in_("id", chart_ids)
            .execute()
        )
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Birth charts not found"
            )
        
        # Convert to list of dicts and ensure "country" -> "nation" mapping
        result = []
        for item in response.data:
            birth_data = item.get("birth_data", {})
            # Ensure nation field exists (map from country if needed)
            if "country" in birth_data and "nation" not in birth_data:
                birth_data["nation"] = birth_data["country"]
            
            result.append({
                "id": item["id"],
                "name": item["name"],
                "birth_data": birth_data,
            })
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching birth data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth data: {str(e)}"
        )


def update_birth_chart(
    user_id: str,
    chart_id: str,
    update_data: UserBirthChartUpdate,
) -> UserBirthChart:
    """
    Update an existing birth chart.
    
    Args:
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
        update_data: Fields to update
    
    Returns:
        UserBirthChart: Updated birth chart
    
    Raises:
        HTTPException: If chart not found or update fails
    """
    try:
        supabase = _create_supabase_client()
        
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
            return get_birth_chart_by_id(user_id, chart_id)
        
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
    user_id: str,
    chart_id: str,
) -> None:
    """
    Delete a birth chart.
    
    Args:
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
    
    Raises:
        HTTPException: If deletion fails
    """
    try:
        supabase = _create_supabase_client()
        
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
# Conversation Operations
# ============================================================================

def save_conversation(
    user_id: str,
    conversation_data: ChatConversationCreate,
) -> ChatConversation:
    """
    Create a new conversation.
    
    Args:
        user_id: User ID (UUID string)
        conversation_data: Conversation data to create
    
    Returns:
        ChatConversation: Created conversation with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
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
    user_id: str,
    limit: Optional[int] = None,
    include_chart_ids: bool = False,
) -> List[ChatConversation]:
    """
    Get all conversations for a user.
    
    Args:
        user_id: User ID (UUID string)
        limit: Optional limit on number of results
        include_chart_ids: If True, include birth_chart_ids in response
    
    Returns:
        List[ChatConversation]: List of user's conversations
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        query = supabase.table("chat_conversations").select("*").eq("user_id", user_id).order("updated_at", desc=True)
        
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        conversations = []
        for item in response.data:
            conv = ChatConversation(**item)
            if include_chart_ids:
                try:
                    chart_ids = get_conversation_chart_ids(user_id, str(conv.id))
                    conv.birth_chart_ids = chart_ids
                except Exception:
                    conv.birth_chart_ids = []
            conversations.append(conv)
        
        return conversations
    
    except Exception as e:
        logger.error(f"Error fetching conversations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(e)}"
        )


def get_conversation_by_id(
    user_id: str,
    conversation_id: str,
) -> ChatConversation:
    """
    Get a specific conversation by ID.
    
    Args:
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
    
    Returns:
        ChatConversation: Conversation data
    
    Raises:
        HTTPException: If conversation not found or database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
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
    user_id: str,
    conversation_id: str,
    update_data: ChatConversationUpdate,
) -> ChatConversation:
    """
    Update conversation metadata.
    
    Args:
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
        update_data: Fields to update
    
    Returns:
        ChatConversation: Updated conversation
    
    Raises:
        HTTPException: If conversation not found or update fails
    """
    try:
        supabase = _create_supabase_client()
        
        update_dict = {}
        if update_data.title is not None:
            update_dict["title"] = update_data.title
        
        if not update_dict:
            return get_conversation_by_id(user_id, conversation_id)
        
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
    user_id: str,
    conversation_id: str,
) -> None:
    """
    Delete a conversation and all its messages.
    
    Args:
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
    
    Raises:
        HTTPException: If deletion fails
    """
    try:
        supabase = _create_supabase_client()
        
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
    message_data: ChatMessageCreate,
) -> ChatMessage:
    """
    Save a chat message to the database.
    
    Args:
        message_data: Message data to save
    
    Returns:
        ChatMessage: Saved message with generated ID
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
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
    conversation_id: str,
    limit: Optional[int] = None,
) -> List[ChatMessage]:
    """
    Get message history for a conversation.
    
    Args:
        conversation_id: Conversation ID (UUID string)
        limit: Optional limit on number of messages
    
    Returns:
        List[ChatMessage]: List of messages in chronological order
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
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
    user_id: str,
    conversation_id: str,
    message_limit: Optional[int] = None,
) -> ConversationWithMessages:
    """
    Get a conversation with its messages.
    
    Args:
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
        message_limit: Optional limit on number of messages
    
    Returns:
        ConversationWithMessages: Conversation with its messages
    
    Raises:
        HTTPException: If conversation not found or database operation fails
    """
    try:
        conversation = get_conversation_by_id(user_id, conversation_id)
        messages = get_conversation_history(conversation_id, message_limit)
        
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


# ============================================================================
# Conversation-Birth Chart Relations
# ============================================================================

def link_conversation_to_charts(
    user_id: str,
    conversation_id: str,
    chart_ids: List[str],
) -> None:
    """
    Link a conversation to one or more birth charts.
    Verifies that both the conversation and charts belong to the user.
    
    Args:
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
        chart_ids: List of birth chart IDs to link
    
    Raises:
        HTTPException: If conversation or chart not found, or linking fails
    """
    if not chart_ids:
        return
    
    try:
        # Verify conversation belongs to user
        get_conversation_by_id(user_id, conversation_id)
        
        supabase = _create_supabase_client()
        
        # Verify all charts belong to user and prepare link data
        links_to_create = []
        for chart_id in chart_ids:
            # Verify chart belongs to user
            chart = get_birth_chart_by_id(user_id, chart_id)
            links_to_create.append({
                "conversation_id": str(conversation_id),
                "birth_chart_id": str(chart_id),
            })
        
        # Insert all links (Supabase will handle duplicates via primary key constraint)
        if links_to_create:
            supabase.table("conversation_birth_charts").insert(links_to_create).execute()
        
        logger.info(f"Linked conversation {conversation_id} to {len(links_to_create)} birth charts")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking conversation to charts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link conversation to charts: {str(e)}"
        )


def get_conversations_by_chart_id(
    user_id: str,
    chart_id: str,
    limit: Optional[int] = None,
) -> List[ChatConversation]:
    """
    Get all conversations linked to a specific birth chart.
    
    Args:
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
        limit: Optional limit on number of results
    
    Returns:
        List[ChatConversation]: List of conversations linked to the chart
    
    Raises:
        HTTPException: If chart not found or database operation fails
    """
    try:
        # Verify chart belongs to user
        get_birth_chart_by_id(user_id, chart_id)
        
        supabase = _create_supabase_client()
        
        # Query conversation IDs from the junction table
        query = (
            supabase.table("conversation_birth_charts")
            .select("conversation_id")
            .eq("birth_chart_id", chart_id)
            .order("created_at", desc=True)
        )
        
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        
        # Extract conversation IDs
        conversation_ids = [item["conversation_id"] for item in response.data]
        
        if not conversation_ids:
            return []
        
        # Fetch conversations and filter by user_id
        conversations_response = (
            supabase.table("chat_conversations")
            .select("*")
            .in_("id", conversation_ids)
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        
        return [ChatConversation(**item) for item in conversations_response.data]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversations by chart ID: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(e)}"
        )


def get_conversation_chart_ids(
    user_id: str,
    conversation_id: str,
) -> List[UUID]:
    """
    Get all birth chart IDs linked to a conversation.
    
    Args:
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
    
    Returns:
        List[UUID]: List of birth chart IDs linked to the conversation
    
    Raises:
        HTTPException: If conversation not found or database operation fails
    """
    try:
        # Verify conversation belongs to user
        get_conversation_by_id(user_id, conversation_id)
        
        supabase = _create_supabase_client()
        
        response = (
            supabase.table("conversation_birth_charts")
            .select("birth_chart_id")
            .eq("conversation_id", conversation_id)
            .execute()
        )
        
        return [UUID(item["birth_chart_id"]) for item in response.data]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation chart IDs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chart IDs: {str(e)}"
        )


def get_conversation_with_charts(
    user_id: str,
    conversation_id: str,
) -> ConversationWithCharts:
    """
    Get a conversation with its linked birth chart IDs.
    
    Args:
        user_id: User ID (UUID string)
        conversation_id: Conversation ID (UUID string)
    
    Returns:
        ConversationWithCharts: Conversation with its linked chart IDs
    
    Raises:
        HTTPException: If conversation not found or database operation fails
    """
    try:
        conversation = get_conversation_by_id(user_id, conversation_id)
        chart_ids = get_conversation_chart_ids(user_id, conversation_id)
        
        return ConversationWithCharts(
            conversation=conversation,
            birth_chart_ids=chart_ids
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation with charts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(e)}"
        )


def get_chart_with_conversations(
    user_id: str,
    chart_id: str,
    conversation_limit: Optional[int] = None,
) -> ChartWithConversations:
    """
    Get a birth chart with all its linked conversations.
    
    Args:
        user_id: User ID (UUID string)
        chart_id: Birth chart ID (UUID string)
        conversation_limit: Optional limit on number of conversations
    
    Returns:
        ChartWithConversations: Birth chart with its linked conversations
    
    Raises:
        HTTPException: If chart not found or database operation fails
    """
    try:
        chart = get_birth_chart_by_id(user_id, chart_id)
        conversations = get_conversations_by_chart_id(
            user_id,
            chart_id,
            limit=conversation_limit,
        )
        
        return ChartWithConversations(
            chart=chart,
            conversations=conversations
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chart with conversations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chart with conversations: {str(e)}"
        )

