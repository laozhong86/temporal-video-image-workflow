"""Common activities shared across workflows."""

import json
import asyncio
from typing import Dict, Any, Optional
from temporalio import activity
from datetime import datetime
from pydantic import BaseModel, ValidationError

from models.video_request import VideoRequest
from models.image_request import ImageRequest
from config.retry_policies import (
    get_retry_policy,
    should_send_heartbeat,
    is_retryable_error,
    ValidationError as CustomValidationError,
    TimeoutError as CustomTimeoutError,
    NetworkError,
    APIError
)
from config.concurrency_control import with_concurrency_control


@activity.defn
@with_concurrency_control(timeout=60)
async def validate_request(request_data: Dict[str, Any], request_type: str) -> Dict[str, Any]:
    """Validate incoming request data.
    
    Args:
        request_data: Raw request data to validate
        request_type: Type of request ('video' or 'image')
        
    Returns:
        Dict containing validation result
    """
    activity.logger.info(f"Validating {request_type} request")
    
    # Send heartbeat for validation
    if should_send_heartbeat("validate_request"):
        activity.heartbeat()
    
    try:
        # Validate inputs
        if not request_data:
            raise CustomValidationError("Request data cannot be empty")
        if not request_type or request_type not in ["video", "image"]:
            raise CustomValidationError(f"Invalid request type: {request_type}")
        
        # Choose appropriate model based on request type
        if request_type == "video":
            model_class = VideoRequest
        elif request_type == "image":
            model_class = ImageRequest
        else:
            raise CustomValidationError(f"Unknown request type: {request_type}")
        
        # Validate using Pydantic model
        validated_request = model_class(**request_data)
        
        result = {
            "valid": True,
            "validated_data": validated_request.model_dump(),
            "validated_at": datetime.utcnow().isoformat()
        }
        
        activity.logger.info(f"Request validation successful for {request_type}")
        return result
        
    except ValidationError as e:
        activity.logger.error(f"Pydantic validation failed: {str(e)}")
        # Pydantic validation errors are not retryable
        raise CustomValidationError(f"Request validation failed: {str(e)}")
    except CustomValidationError as e:
        activity.logger.error(f"Custom validation failed: {str(e)}")
        raise  # Don't retry validation errors
    except Exception as e:
        activity.logger.error(f"Unexpected validation error: {str(e)}")
        if is_retryable_error(e):
            raise APIError(f"Validation service error: {str(e)}")
        else:
            raise CustomValidationError(f"Validation error: {str(e)}")


@activity.defn
@with_concurrency_control(timeout=30)
async def log_activity(activity_name: str, data: Dict[str, Any], level: str = "info") -> Dict[str, Any]:
    """Log activity execution with structured data.
    
    Args:
        activity_name: Name of the activity being logged
        data: Data to log
        level: Log level ('info', 'warning', 'error')
        
    Returns:
        Dict containing logging result
    """
    timestamp = datetime.utcnow().isoformat()
    
    log_entry = {
        "timestamp": timestamp,
        "activity": activity_name,
        "data": data,
        "level": level
    }
    
    # Log based on level
    if level == "error":
        activity.logger.error(f"[{activity_name}] {json.dumps(data)}")
    elif level == "warning":
        activity.logger.warning(f"[{activity_name}] {json.dumps(data)}")
    else:
        activity.logger.info(f"[{activity_name}] {json.dumps(data)}")
    
    # In a real implementation, you might also:
    # - Store logs in a database
    # - Send logs to external monitoring service
    # - Trigger alerts based on log level
    
    return {
        "logged": True,
        "timestamp": timestamp,
        "level": level
    }


@activity.defn
@with_concurrency_control(timeout=60)
async def handle_error(
    error: Exception,
    context: Dict[str, Any],
    retry_count: int = 0,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Handle errors with retry logic and logging.
    
    Args:
        error: The exception that occurred
        context: Context information about where the error occurred
        retry_count: Current retry attempt number
        max_retries: Maximum number of retries allowed
        
    Returns:
        Dict containing error handling result
    """
    error_message = str(error)
    error_type = type(error).__name__
    timestamp = datetime.utcnow().isoformat()
    
    activity.logger.error(
        f"Error in {context.get('activity', 'unknown')}: {error_type} - {error_message}"
    )
    
    # Determine if error is retryable
    retryable_errors = [
        "ConnectionError",
        "TimeoutError",
        "HTTPStatusError",
        "TemporaryFailure"
    ]
    
    is_retryable = any(retryable in error_type for retryable in retryable_errors)
    should_retry = is_retryable and retry_count < max_retries
    
    error_info = {
        "error_type": error_type,
        "error_message": error_message,
        "timestamp": timestamp,
        "context": context,
        "retry_count": retry_count,
        "max_retries": max_retries,
        "is_retryable": is_retryable,
        "should_retry": should_retry
    }
    
    # Log structured error information
    await log_activity("error_handler", error_info, "error")
    
    # In a real implementation, you might also:
    # - Send error notifications
    # - Update monitoring dashboards
    # - Trigger incident response workflows
    
    return error_info


@activity.defn
@with_concurrency_control(timeout=300)
async def cleanup_resources(resource_ids: list[str], resource_type: str) -> Dict[str, Any]:
    """Clean up temporary resources.
    
    Args:
        resource_ids: List of resource identifiers to clean up
        resource_type: Type of resources ('temp_files', 'cache_entries', etc.)
        
    Returns:
        Dict containing cleanup result
    """
    activity.logger.info(f"Cleaning up {len(resource_ids)} {resource_type} resources")
    
    cleaned_count = 0
    failed_cleanups = []
    
    try:
        for resource_id in resource_ids:
            try:
                # Simulate resource cleanup based on type
                if resource_type == "temp_files":
                    # In real implementation: os.remove(resource_id)
                    pass
                elif resource_type == "cache_entries":
                    # In real implementation: cache.delete(resource_id)
                    pass
                elif resource_type == "temp_storage":
                    # In real implementation: storage_client.delete(resource_id)
                    pass
                
                cleaned_count += 1
                activity.logger.debug(f"Cleaned up {resource_type}: {resource_id}")
                
            except Exception as e:
                failed_cleanups.append({
                    "resource_id": resource_id,
                    "error": str(e)
                })
                activity.logger.warning(f"Failed to cleanup {resource_id}: {str(e)}")
        
        result = {
            "success": len(failed_cleanups) == 0,
            "cleaned_count": cleaned_count,
            "failed_count": len(failed_cleanups),
            "failed_cleanups": failed_cleanups,
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
        activity.logger.info(
            f"Cleanup completed: {cleaned_count} successful, {len(failed_cleanups)} failed"
        )
        return result
        
    except Exception as e:
        activity.logger.error(f"Cleanup operation failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "cleaned_count": cleaned_count
        }