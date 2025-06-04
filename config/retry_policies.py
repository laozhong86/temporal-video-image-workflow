"""Retry policies configuration for Temporal activities.

This module defines standardized retry policies for different types of activities
to ensure consistent error handling and recovery across the application.
"""

from datetime import timedelta
from temporalio.common import RetryPolicy
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Standard retry policy for most activities
STANDARD_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_attempts=3,
    maximum_interval=timedelta(seconds=60)
)

# Retry policy for external API calls (more aggressive)
API_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=5,
    maximum_interval=timedelta(minutes=2)
)

# Retry policy for long-running operations
LONG_RUNNING_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=1.5,
    maximum_attempts=3,
    maximum_interval=timedelta(minutes=5)
)

# Retry policy for critical operations (minimal retries)
CRITICAL_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_attempts=2,
    maximum_interval=timedelta(seconds=30)
)

# Retry policy for file operations
FILE_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=1.5,
    maximum_attempts=4,
    maximum_interval=timedelta(seconds=45)
)

# Retry policy for notification operations
NOTIFICATION_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=3),
    backoff_coefficient=2.0,
    maximum_attempts=4,
    maximum_interval=timedelta(minutes=1)
)

# Custom exceptions for retry handling
class RetryableError(Exception):
    """Base class for retryable errors."""
    pass

class APIError(RetryableError):
    """API-related errors that should be retried."""
    pass

class NetworkError(RetryableError):
    """Network-related errors that should be retried."""
    pass

class TimeoutError(RetryableError):
    """Timeout errors that should be retried."""
    pass

class RateLimitError(RetryableError):
    """Rate limit errors that should be retried with backoff."""
    pass

class NonRetryableError(Exception):
    """Base class for non-retryable errors."""
    pass

class ValidationError(NonRetryableError):
    """Validation errors that should not be retried."""
    pass

class AuthenticationError(NonRetryableError):
    """Authentication errors that should not be retried."""
    pass

class PermissionError(NonRetryableError):
    """Permission errors that should not be retried."""
    pass

# Mapping of activity types to retry policies
ACTIVITY_RETRY_POLICIES: Dict[str, RetryPolicy] = {
    # Image generation activities
    "submit_image_request": API_RETRY_POLICY,
    "check_image_status": API_RETRY_POLICY,
    "download_image_result": FILE_RETRY_POLICY,
    "gen_image": API_RETRY_POLICY,
    
    # Video generation activities
    "submit_video_request": API_RETRY_POLICY,
    "check_video_status": API_RETRY_POLICY,
    "download_video_result": FILE_RETRY_POLICY,
    "request_video": API_RETRY_POLICY,
    "check_video_generation_status": API_RETRY_POLICY,
    "download_generated_video": FILE_RETRY_POLICY,
    
    # Common activities
    "validate_request": STANDARD_RETRY_POLICY,
    "log_activity": CRITICAL_RETRY_POLICY,
    "handle_error": CRITICAL_RETRY_POLICY,
    "cleanup_resources": FILE_RETRY_POLICY,
    
    # Notification activities
    "send_video_notification": NOTIFICATION_RETRY_POLICY,
    "send_image_notification": NOTIFICATION_RETRY_POLICY,
    "send_webhook": NOTIFICATION_RETRY_POLICY,
    
    # Batch processing activities
    "process_batch_item": STANDARD_RETRY_POLICY,
    "aggregate_batch_results": STANDARD_RETRY_POLICY,
}

def get_retry_policy(activity_name: str) -> RetryPolicy:
    """Get retry policy for a specific activity.
    
    Args:
        activity_name: Name of the activity
        
    Returns:
        RetryPolicy for the activity, defaults to STANDARD_RETRY_POLICY
    """
    policy = ACTIVITY_RETRY_POLICIES.get(activity_name, STANDARD_RETRY_POLICY)
    logger.debug(f"Using retry policy for {activity_name}: {policy}")
    return policy

def is_retryable_error(error: Exception) -> bool:
    """Check if an error should be retried.
    
    Args:
        error: Exception to check
        
    Returns:
        True if the error should be retried, False otherwise
    """
    # Check if it's explicitly a retryable error
    if isinstance(error, RetryableError):
        return True
    
    # Check if it's explicitly non-retryable
    if isinstance(error, NonRetryableError):
        return False
    
    # Check error message for common retryable patterns
    error_message = str(error).lower()
    retryable_patterns = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "rate limit",
        "service unavailable",
        "internal server error",
        "bad gateway",
        "gateway timeout",
        "too many requests"
    ]
    
    for pattern in retryable_patterns:
        if pattern in error_message:
            return True
    
    # Default to non-retryable for unknown errors
    return False

def create_custom_retry_policy(
    initial_interval_seconds: int = 1,
    backoff_coefficient: float = 2.0,
    maximum_attempts: int = 3,
    maximum_interval_seconds: int = 60
) -> RetryPolicy:
    """Create a custom retry policy.
    
    Args:
        initial_interval_seconds: Initial retry interval in seconds
        backoff_coefficient: Backoff multiplier for subsequent retries
        maximum_attempts: Maximum number of retry attempts
        maximum_interval_seconds: Maximum interval between retries in seconds
        
    Returns:
        Custom RetryPolicy instance
    """
    return RetryPolicy(
        initial_interval=timedelta(seconds=initial_interval_seconds),
        backoff_coefficient=backoff_coefficient,
        maximum_attempts=maximum_attempts,
        maximum_interval=timedelta(seconds=maximum_interval_seconds)
    )

# Activity heartbeat configuration
HEARTBEAT_TIMEOUT = timedelta(minutes=5)
HEARTBEAT_INTERVAL = timedelta(seconds=30)

def should_send_heartbeat(activity_name: str) -> bool:
    """Check if an activity should send heartbeats.
    
    Args:
        activity_name: Name of the activity
        
    Returns:
        True if the activity should send heartbeats
    """
    long_running_activities = [
        "request_video",
        "check_video_generation_status",
        "download_generated_video",
        "gen_image",
        "download_video_result",
        "download_image_result"
    ]
    
    return activity_name in long_running_activities