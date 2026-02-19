"""
Database service layer for Supabase operations
Handles all CRUD operations for user birth charts, aspects, relationships, and conversations
"""

import os
from datetime import datetime
from typing import Optional, List
from uuid import UUID
import logging

from supabase import create_client, Client
from fastapi import HTTPException, status
from dotenv import load_dotenv
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
from models.subscription import (
    Subscription,
    SubscriptionUpdate,
    Usage,
)

logger = logging.getLogger(__name__)

load_dotenv()

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
    except Exception as exc:
        logger.error("Error saving birth chart: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save birth chart: {str(exc)}"
        ) from exc


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
    
    except Exception as exc:
        logger.error("Error fetching user birth charts: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth charts: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        # Check if it's a Supabase "no rows" error (PGRST116)
        error_str = str(exc)
        if "PGRST116" in error_str or "Cannot coerce the result to a single JSON object" in error_str:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Birth chart not found"
            ) from exc
        logger.error("Error fetching birth chart: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth chart: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error fetching birth data: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch birth data: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error updating birth chart: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update birth chart: {str(exc)}"
        ) from exc


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
        
        supabase.table("user_birth_charts") \
            .delete() \
            .eq("id", chart_id) \
            .eq("user_id", user_id) \
            .execute()
        
        logger.info("Birth chart %s deleted for user %s", chart_id, user_id)
    
    except Exception as exc:
        logger.error("Error deleting birth chart: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete birth chart: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error creating conversation: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(exc)}"
        ) from exc


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
    
    except Exception as exc:
        logger.error("Error fetching conversations: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        # Check if it's a Supabase "no rows" error (PGRST116)
        error_str = str(exc)
        if "PGRST116" in error_str or "Cannot coerce the result to a single JSON object" in error_str:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            ) from exc
        logger.error("Error fetching conversation: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error updating conversation: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update conversation: {str(exc)}"
        ) from exc


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
        supabase.table("chat_conversations") \
            .delete() \
            .eq("id", conversation_id) \
            .eq("user_id", user_id) \
            .execute()
        
        logger.info("Conversation %s deleted for user %s", conversation_id, user_id)
    
    except Exception as exc:
        logger.error("Error deleting conversation: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error saving message: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save message: {str(exc)}"
        ) from exc


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
    
    except Exception as exc:
        logger.error("Error fetching conversation history: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation history: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error fetching conversation with messages: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(exc)}"
        ) from exc


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
            get_birth_chart_by_id(user_id, chart_id)
            links_to_create.append({
                "conversation_id": str(conversation_id),
                "birth_chart_id": str(chart_id),
            })
        
        # Insert all links (Supabase will handle duplicates via primary key constraint)
        if links_to_create:
            supabase.table("conversation_birth_charts").insert(links_to_create).execute()
        
        logger.info("Linked conversation %s to %d birth charts", conversation_id, len(links_to_create))
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error linking conversation to charts: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link conversation to charts: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error fetching conversations by chart ID: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error fetching conversation chart IDs: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chart IDs: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error fetching conversation with charts: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(exc)}"
        ) from exc


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
    except Exception as exc:
        logger.error("Error fetching chart with conversations: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chart with conversations: {str(exc)}"
        ) from exc


# ============================================================================
# Subscription Operations
# ============================================================================

def get_or_create_user_subscription(
    user_id: str,
    stripe_customer_id: Optional[str] = None,
) -> Subscription:
    """
    Get existing subscription or create a new free tier subscription for user.
    
    Args:
        user_id: User ID (UUID string)
        stripe_customer_id: Optional Stripe customer ID. If not provided, will use placeholder for free tier.
    
    Returns:
        Subscription: User's subscription (existing or newly created)
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        # Try to get existing subscription
        response = (
            supabase.table("user_subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        
        # Check if subscription exists
        if response.data and len(response.data) > 0:
            data = response.data[0]
            return Subscription(**data)
        
        # Create new free tier subscription
        # Use provided customer ID or generate placeholder for free tier
        customer_id = stripe_customer_id or f"cus_free_{user_id}"
        
        data = {
            "user_id": user_id,
            "stripe_customer_id": customer_id,
            "status": "free",
            "is_active": True,
        }
        
        create_response = supabase.table("user_subscriptions").insert(data).execute()
        
        if not create_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create subscription"
            )
        
        logger.info("Created free tier subscription for user %s", user_id)
        return Subscription(**create_response.data[0])
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting or creating subscription: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get or create subscription: {str(exc)}"
        ) from exc


def get_user_subscription(user_id: str) -> Subscription:
    """
    Get user's current subscription.
    
    Args:
        user_id: User ID (UUID string)
    
    Returns:
        Subscription: User's subscription
    
    Raises:
        HTTPException: If subscription not found or database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        response = (
            supabase.table("user_subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )
        
        return Subscription(**response.data)
    
    except HTTPException:
        raise
    except Exception as exc:
        # Check if it's a Supabase "no rows" error (PGRST116)
        error_str = str(exc)
        if "PGRST116" in error_str or "Cannot coerce the result to a single JSON object" in error_str:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            ) from exc
        logger.error("Error fetching subscription: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription: {str(exc)}"
        ) from exc


def get_user_subscription_by_stripe_id(stripe_subscription_id: str) -> Optional[Subscription]:
    """
    Get subscription by Stripe subscription ID.
    
    Args:
        stripe_subscription_id: Stripe subscription ID
    
    Returns:
        Subscription if found, None otherwise
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        response = (
            supabase.table("user_subscriptions")
            .select("*")
            .eq("stripe_subscription_id", stripe_subscription_id)
            .single()
            .execute()
        )
        
        if not response.data:
            return None
        
        return Subscription(**response.data)
    
    except Exception as exc:
        # Check if it's a "no rows" error
        error_str = str(exc)
        if "PGRST116" in error_str or "Cannot coerce the result to a single JSON object" in error_str:
            return None
        logger.error("Error fetching subscription by Stripe ID: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription: {str(exc)}"
        ) from exc


def update_user_subscription(
    user_id: str,
    update_data: SubscriptionUpdate,
) -> Subscription:
    """
    Update user's subscription.

    Args:
        user_id: User ID (UUID string)
        update_data: Fields to update

    Returns:
        Subscription: Updated subscription

    Raises:
        HTTPException: If subscription not found or update fails
    """
    try:
        supabase = _create_supabase_client()

        # Build update dict from non-None fields
        update_dict = {}
        if update_data.stripe_subscription_id is not None:
            update_dict["stripe_subscription_id"] = update_data.stripe_subscription_id
        if update_data.stripe_price_id is not None:
            update_dict["stripe_price_id"] = update_data.stripe_price_id
        if update_data.status is not None:
            status_value = update_data.status.value if hasattr(update_data.status, 'value') else update_data.status
            update_dict["status"] = status_value
        if update_data.is_active is not None:
            update_dict["is_active"] = update_data.is_active
        if update_data.current_period_end is not None:
            if isinstance(update_data.current_period_end, datetime):
                update_dict["current_period_end"] = update_data.current_period_end.isoformat()
            else:
                update_dict["current_period_end"] = update_data.current_period_end
        elif update_data.current_period_end is None:
            update_dict["current_period_end"] = None
        if update_data.message_credits is not None:
            update_dict["message_credits"] = update_data.message_credits
        if update_data.unlimited_until is not None:
            if isinstance(update_data.unlimited_until, datetime):
                update_dict["unlimited_until"] = update_data.unlimited_until.isoformat()
            else:
                update_dict["unlimited_until"] = update_data.unlimited_until

        if not update_dict:
            return get_user_subscription(user_id)

        update_dict["updated_at"] = "now()"

        response = (
            supabase.table("user_subscriptions")
            .update(update_dict)
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )

        logger.info("Updated subscription for user %s", user_id)
        return Subscription(**response.data[0])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating subscription: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription: {str(exc)}"
        ) from exc


def add_message_credits(user_id: str, amount: int) -> Subscription:
    """
    Atomically add message credits to a user's subscription.
    Credits stack with existing credits.

    Args:
        user_id: User ID (UUID string)
        amount: Number of credits to add

    Returns:
        Subscription: Updated subscription
    """
    try:
        supabase = _create_supabase_client()

        # Fetch current subscription to get current credits
        current = get_or_create_user_subscription(user_id)
        new_credits = current.message_credits + amount

        response = (
            supabase.table("user_subscriptions")
            .update({
                "message_credits": new_credits,
                "status": "credits" if new_credits > 0 else current.status,
                "updated_at": "now()",
            })
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )

        logger.info("Added %d credits for user %s (total: %d)", amount, user_id, new_credits)
        return Subscription(**response.data[0])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error adding credits for user %s: %s", user_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add message credits: {str(exc)}"
        ) from exc


def deduct_message_credit(user_id: str) -> Subscription:
    """
    Atomically deduct 1 message credit from a user's subscription.
    Only deducts if credits > 0.

    Args:
        user_id: User ID (UUID string)

    Returns:
        Subscription: Updated subscription
    """
    try:
        supabase = _create_supabase_client()

        current = get_or_create_user_subscription(user_id)

        if current.message_credits <= 0:
            logger.warning("Cannot deduct credit for user %s: no credits remaining", user_id)
            return current

        new_credits = current.message_credits - 1

        # If credits drop to 0 and no unlimited pass, set status back to free
        from services.usage_tracker import get_effective_plan

        update_data = {
            "message_credits": new_credits,
            "updated_at": "now()",
        }

        response = (
            supabase.table("user_subscriptions")
            .update(update_data)
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )

        logger.debug("Deducted 1 credit for user %s (remaining: %d)", user_id, new_credits)
        return Subscription(**response.data[0])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error deducting credit for user %s: %s", user_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deduct message credit: {str(exc)}"
        ) from exc


def set_unlimited_until(user_id: str, until_dt: datetime) -> Subscription:
    """
    Set the unlimited pass expiry for a user.

    Args:
        user_id: User ID (UUID string)
        until_dt: When unlimited access expires

    Returns:
        Subscription: Updated subscription
    """
    try:
        supabase = _create_supabase_client()

        from constants.limits import LIFETIME_EXPIRY
        status_value = "lifetime" if until_dt >= LIFETIME_EXPIRY else "unlimited"

        response = (
            supabase.table("user_subscriptions")
            .update({
                "unlimited_until": until_dt.isoformat(),
                "status": status_value,
                "updated_at": "now()",
            })
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )

        logger.info("Set unlimited_until=%s for user %s", until_dt.isoformat(), user_id)
        return Subscription(**response.data[0])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error setting unlimited_until for user %s: %s", user_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set unlimited access: {str(exc)}"
        ) from exc


def extend_unlimited_until(user_id: str, duration: 'timedelta') -> Subscription:
    """
    Extend unlimited pass from max(current unlimited_until, now) + duration.

    Args:
        user_id: User ID (UUID string)
        duration: Duration to extend by

    Returns:
        Subscription: Updated subscription
    """
    from datetime import timedelta as td

    try:
        current = get_or_create_user_subscription(user_id)
        now = datetime.now(timezone.utc)

        # Start from max(current unlimited_until, now)
        base = now
        if current.unlimited_until:
            current_until = current.unlimited_until
            if current_until.tzinfo is None:
                current_until = current_until.replace(tzinfo=timezone.utc)
            if current_until > now:
                base = current_until

        new_until = base + duration
        return set_unlimited_until(user_id, new_until)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error extending unlimited for user %s: %s", user_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend unlimited access: {str(exc)}"
        ) from exc


# ============================================================================
# Usage Tracking Operations
# ============================================================================

def get_user_usage(user_id: str) -> Usage:
    """
    Get user's current message usage (within rolling 24h window).
    
    Args:
        user_id: User ID (UUID string)
    
    Returns:
        Usage: User's usage record
    
    Raises:
        HTTPException: If usage record not found or database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        response = (
            supabase.table("user_usage")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        
        # Check if usage record exists
        if not response.data or len(response.data) == 0:
            # Create new usage record if it doesn't exist
            return create_user_usage(user_id)
        
        return Usage(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching usage: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch usage: {str(exc)}"
        ) from exc


def create_user_usage(user_id: str) -> Usage:
    """
    Create a new usage record for user.
    
    Args:
        user_id: User ID (UUID string)
    
    Returns:
        Usage: Created usage record
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        data = {
            "user_id": user_id,
            "message_count": 0,
            "last_reset_at": "now()",
        }
        
        response = supabase.table("user_usage").insert(data).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create usage record"
            )
        
        logger.info("Created usage record for user %s", user_id)
        return Usage(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating usage record: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create usage record: {str(exc)}"
        ) from exc


def increment_user_message_count(user_id: str) -> Usage:
    """
    Increment user's message count by 1.
    Uses fetch-increment-update pattern for atomic operation.
    
    Args:
        user_id: User ID (UUID string)
    
    Returns:
        Usage: Updated usage record
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        # Fetch current usage (or create if doesn't exist)
        current_usage = get_user_usage(user_id)
        
        # Increment message count
        new_count = current_usage.message_count + 1
        
        # Update with new count
        response = (
            supabase.table("user_usage")
            .update({"message_count": new_count})
            .eq("user_id", user_id)
            .execute()
        )
        
        if not response.data:
            logger.error("Failed to update usage for user %s - no data returned", user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to increment message count - update returned no data"
            )
        
        logger.debug("Incremented message count for user %s: %d -> %d", user_id, current_usage.message_count, new_count)
        return Usage(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error incrementing message count for user %s: %s", user_id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to increment message count: {str(exc)}"
        ) from exc


def reset_user_usage(user_id: str) -> Usage:
    """
    Reset user's message count and last_reset_at timestamp (for rolling 24h window).
    
    Args:
        user_id: User ID (UUID string)
    
    Returns:
        Usage: Updated usage record
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        supabase = _create_supabase_client()
        
        response = (
            supabase.table("user_usage")
            .update({
                "message_count": 0,
                "last_reset_at": "now()",
            })
            .eq("user_id", user_id)
            .execute()
        )
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usage record not found"
            )
        
        logger.info("Reset usage for user %s", user_id)
        return Usage(**response.data[0])
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error resetting usage: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset usage: {str(exc)}"
        ) from exc

