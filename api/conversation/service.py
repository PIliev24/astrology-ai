"""
Conversation and message database service.

Provides operations for chat conversations and messages,
including linking conversations to birth charts.
"""

import logging
from typing import List, Optional
from uuid import UUID

from core.database.base_service import BaseService
from core.clients.supabase import get_supabase_client
from core.exceptions import ConversationNotFoundError, AppException
from models.database import (
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


class ConversationService(BaseService[ChatConversation, ChatConversationCreate, ChatConversationUpdate]):
    """
    Conversation database operations.

    Extends BaseService with message operations and
    conversation-chart linking functionality.
    """

    table_name = "chat_conversations"
    model_class = ChatConversation
    not_found_error = ConversationNotFoundError
    order_by = "updated_at"

    def get_all_with_chart_ids(
        self,
        user_id: str,
        limit: Optional[int] = None,
    ) -> List[ChatConversation]:
        """
        Get conversations with their linked birth chart IDs.

        Args:
            user_id: User ID
            limit: Optional limit

        Returns:
            List of conversations with birth_chart_ids populated
        """
        conversations = self.get_all(user_id, limit)

        for conv in conversations:
            try:
                chart_ids = self.get_chart_ids(user_id, str(conv.id))
                conv.birth_chart_ids = chart_ids
            except Exception:
                conv.birth_chart_ids = []

        return conversations

    # Message Operations

    def save_message(self, message_data: ChatMessageCreate) -> ChatMessage:
        """
        Save a chat message.

        Args:
            message_data: Message data to save

        Returns:
            Saved message with generated ID
        """
        try:
            data = {
                "conversation_id": str(message_data.conversation_id),
                "role": message_data.role,
                "content": message_data.content,
            }

            if message_data.metadata:
                data["metadata"] = message_data.metadata

            response = self.client.table("chat_messages").insert(data).execute()

            if not response.data:
                raise AppException(message="Failed to save message")

            return ChatMessage(**response.data[0])

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise AppException(message="Failed to save message", details=str(e))

    def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[ChatMessage]:
        """
        Get message history for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Optional limit

        Returns:
            List of messages in chronological order
        """
        try:
            query = (
                self.client.table("chat_messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)  # Oldest first
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()
            return [ChatMessage(**item) for item in response.data]

        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            raise AppException(message="Failed to fetch messages", details=str(e))

    def get_with_messages(
        self,
        user_id: str,
        conversation_id: str,
        message_limit: Optional[int] = None,
    ) -> ConversationWithMessages:
        """
        Get conversation with its messages.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message_limit: Optional limit on messages

        Returns:
            Conversation with messages
        """
        conversation = self.get_by_id(user_id, conversation_id)
        messages = self.get_messages(conversation_id, message_limit)

        return ConversationWithMessages(
            conversation=conversation,
            messages=messages,
        )

    # Chart Linking Operations

    def link_to_charts(
        self,
        user_id: str,
        conversation_id: str,
        chart_ids: List[str],
    ) -> None:
        """
        Link a conversation to birth charts.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            chart_ids: Chart IDs to link
        """
        if not chart_ids:
            return

        try:
            # Verify conversation belongs to user
            self.get_by_id(user_id, conversation_id)

            # Prepare link data
            links = [
                {
                    "conversation_id": str(conversation_id),
                    "birth_chart_id": str(chart_id),
                }
                for chart_id in chart_ids
            ]

            # Insert links (duplicates handled by primary key constraint)
            self.client.table("conversation_birth_charts").insert(links).execute()

            logger.info(f"Linked conversation {conversation_id} to {len(chart_ids)} charts")

        except self.not_found_error:
            raise
        except Exception as e:
            logger.error(f"Error linking conversation to charts: {e}")
            raise AppException(message="Failed to link conversation to charts", details=str(e))

    def get_chart_ids(
        self,
        user_id: str,
        conversation_id: str,
    ) -> List[UUID]:
        """
        Get birth chart IDs linked to a conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            List of chart IDs
        """
        try:
            # Verify conversation belongs to user
            self.get_by_id(user_id, conversation_id)

            response = (
                self.client.table("conversation_birth_charts")
                .select("birth_chart_id")
                .eq("conversation_id", conversation_id)
                .execute()
            )

            return [UUID(item["birth_chart_id"]) for item in response.data]

        except self.not_found_error:
            raise
        except Exception as e:
            logger.error(f"Error fetching chart IDs: {e}")
            raise AppException(message="Failed to fetch chart IDs", details=str(e))

    def get_with_charts(
        self,
        user_id: str,
        conversation_id: str,
    ) -> ConversationWithCharts:
        """
        Get conversation with its linked chart IDs.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            Conversation with chart IDs
        """
        conversation = self.get_by_id(user_id, conversation_id)
        chart_ids = self.get_chart_ids(user_id, conversation_id)

        return ConversationWithCharts(
            conversation=conversation,
            birth_chart_ids=chart_ids,
        )

    def get_by_chart_id(
        self,
        user_id: str,
        chart_id: str,
        limit: Optional[int] = None,
    ) -> List[ChatConversation]:
        """
        Get conversations linked to a specific chart.

        Args:
            user_id: User ID
            chart_id: Chart ID
            limit: Optional limit

        Returns:
            List of conversations
        """
        try:
            # Get conversation IDs from junction table
            query = (
                self.client.table("conversation_birth_charts")
                .select("conversation_id")
                .eq("birth_chart_id", chart_id)
                .order("created_at", desc=True)
            )

            if limit:
                query = query.limit(limit)

            response = query.execute()
            conversation_ids = [item["conversation_id"] for item in response.data]

            if not conversation_ids:
                return []

            # Fetch conversations and filter by user
            conv_response = (
                self.client.table(self.table_name)
                .select("*")
                .in_("id", conversation_ids)
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .execute()
            )

            return [ChatConversation(**item) for item in conv_response.data]

        except Exception as e:
            logger.error(f"Error fetching conversations by chart: {e}")
            raise AppException(message="Failed to fetch conversations", details=str(e))


# Singleton service instance
conversation_service = ConversationService()
