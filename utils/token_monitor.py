"""
Token Monitor Utility
Monitors and manages token usage to prevent exceeding limits
"""

from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Default token limit (150k tokens, leaving room for model responses)
DEFAULT_TOKEN_LIMIT = 150000
WARNING_THRESHOLD = 0.8  # Warn at 80% of limit


class TokenMonitor:
    """Monitors token usage and provides truncation capabilities"""
    
    def __init__(self, limit: int = DEFAULT_TOKEN_LIMIT):
        """
        Initialize token monitor.
        
        Args:
            limit: Maximum token limit (default: 150000)
        """
        self.limit = limit
        self.warning_threshold = int(limit * WARNING_THRESHOLD)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text.
        Uses rough approximation: ~4 characters per token.
        
        Args:
            text: Text to estimate tokens for
        
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // 4
    
    def check_limit(
        self, 
        content: str, 
        current_usage: int = 0
    ) -> Tuple[bool, int, str]:
        """
        Check if content would exceed token limit.
        
        Args:
            content: Content to check
            current_usage: Current token usage (default: 0)
        
        Returns:
            Tuple of (within_limit: bool, token_count: int, message: str)
        """
        content_tokens = self.estimate_tokens(content)
        total_tokens = current_usage + content_tokens
        
        if total_tokens > self.limit:
            return (
                False,
                total_tokens,
                f"Content would exceed token limit ({total_tokens:,} / {self.limit:,} tokens). Please reduce the amount of data requested."
            )
        elif total_tokens > self.warning_threshold:
            return (
                True,
                total_tokens,
                f"Warning: Approaching token limit ({total_tokens:,} / {self.limit:,} tokens). Consider requesting less data."
            )
        else:
            return (True, total_tokens, "")
    
    def truncate_content(self, content: str, max_tokens: int) -> str:
        """
        Truncate content to fit within token limit.
        
        Args:
            content: Content to truncate
            max_tokens: Maximum tokens allowed
        
        Returns:
            Truncated content
        """
        max_chars = max_tokens * 4  # Rough conversion
        
        if len(content) <= max_chars:
            return content
        
        truncated = content[:max_chars]
        # Try to truncate at a reasonable point (end of line or sentence)
        last_newline = truncated.rfind('\n')
        last_period = truncated.rfind('.')
        
        cutoff = max(last_newline, last_period)
        if cutoff > max_chars * 0.8:  # Only use cutoff if it's not too early
            truncated = truncated[:cutoff + 1]
        
        return truncated + "\n\n[Content truncated due to token limit]"
    
    def get_user_friendly_error(self, token_count: int) -> str:
        """
        Get user-friendly error message for token limit exceeded.
        
        Args:
            token_count: Current token count
        
        Returns:
            User-friendly error message
        """
        return (
            f"The request is too large to process ({token_count:,} tokens). "
            "Please try requesting fewer charts or more specific information. "
            "You can ask about individual planets or specific aspects instead of full chart data."
        )


# Global instance for easy access
default_monitor = TokenMonitor()

