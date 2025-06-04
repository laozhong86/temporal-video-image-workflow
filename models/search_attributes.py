"""Search Attributes Management Module

This module provides utility functions for updating workflow search attributes
using Temporal's upsert_search_attributes API with type safety and validation.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Type
from enum import Enum

from temporalio import workflow
from temporalio.common import SearchAttributeKey, SearchAttributePair, TypedSearchAttributes
from pydantic import BaseModel, Field, validator

from models.core_models import WorkflowState, Progress, JobStatus, Step, JobType


class SearchAttributeType(str, Enum):
    """Supported search attribute types in Temporal."""
    TEXT = "text"
    INT = "int"
    DOUBLE = "double"
    BOOL = "bool"
    DATETIME = "datetime"
    TEXT_ARRAY = "text_array"


class SearchAttributeDefinition(BaseModel):
    """Definition of a search attribute with type information."""
    
    key: str = Field(..., description="Search attribute key name")
    type: SearchAttributeType = Field(..., description="Attribute type")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(default=False, description="Whether this attribute is required")
    default_value: Optional[Any] = Field(default=None, description="Default value if not provided")
    
    @validator('key')
    def validate_key(cls, v):
        """Validate search attribute key format."""
        if not v or not isinstance(v, str):
            raise ValueError("Search attribute key must be a non-empty string")
        if not v[0].isupper():
            raise ValueError("Search attribute key must start with uppercase letter")
        return v


class WorkflowSearchAttributes:
    """Registry of workflow search attributes with type definitions."""
    
    # Define all search attributes with their types
    ATTRIBUTES = {
        "WorkflowStatus": SearchAttributeDefinition(
            key="WorkflowStatus",
            type=SearchAttributeType.TEXT,
            description="Current workflow status (pending, in-progress, completed, failed)",
            required=True
        ),
        "ProgressPercentage": SearchAttributeDefinition(
            key="ProgressPercentage",
            type=SearchAttributeType.INT,
            description="Progress percentage (0-100)",
            required=True,
            default_value=0
        ),
        "CurrentStep": SearchAttributeDefinition(
            key="CurrentStep",
            type=SearchAttributeType.TEXT,
            description="Current workflow step",
            required=True
        ),
        "ErrorCount": SearchAttributeDefinition(
            key="ErrorCount",
            type=SearchAttributeType.INT,
            description="Number of errors encountered",
            required=False,
            default_value=0
        ),
        "LastUpdateTime": SearchAttributeDefinition(
            key="LastUpdateTime",
            type=SearchAttributeType.DATETIME,
            description="Timestamp of last state update",
            required=True
        ),
        "JobType": SearchAttributeDefinition(
            key="JobType",
            type=SearchAttributeType.TEXT,
            description="Type of job being processed",
            required=True
        ),
        "UserId": SearchAttributeDefinition(
            key="UserId",
            type=SearchAttributeType.TEXT,
            description="User identifier who initiated the workflow",
            required=False
        ),
        "RequestId": SearchAttributeDefinition(
            key="RequestId",
            type=SearchAttributeType.TEXT,
            description="Unique request identifier",
            required=True
        ),
        "RetryCount": SearchAttributeDefinition(
            key="RetryCount",
            type=SearchAttributeType.INT,
            description="Number of retry attempts",
            required=False,
            default_value=0
        ),
        "DurationSeconds": SearchAttributeDefinition(
            key="DurationSeconds",
            type=SearchAttributeType.INT,
            description="Workflow duration in seconds",
            required=False
        ),
        "PromptHash": SearchAttributeDefinition(
            key="PromptHash",
            type=SearchAttributeType.TEXT,
            description="Hash of the input prompt for deduplication",
            required=False
        ),
        "AssetCount": SearchAttributeDefinition(
            key="AssetCount",
            type=SearchAttributeType.INT,
            description="Number of generated assets",
            required=False,
            default_value=0
        ),
        "FileSizeMB": SearchAttributeDefinition(
            key="FileSizeMB",
            type=SearchAttributeType.INT,
            description="Total file size in megabytes",
            required=False        ),
        "CustomProgress": SearchAttributeDefinition(
            key="CustomProgress",
            type=SearchAttributeType.TEXT,
            description="Custom progress tracking with step:status:percent format",
            required=False
        ),
        "CustomTag": SearchAttributeDefinition(
            key="CustomTag",
            type=SearchAttributeType.TEXT,
            description="Custom tag for workflow categorization and filtering",
            required=False
        )
    }
    
    @classmethod
    def get_search_attribute_key(cls, key_name: str) -> SearchAttributeKey:
        """Get typed search attribute key.
        
        Args:
            key_name: Name of the search attribute
            
        Returns:
            Typed search attribute key
            
        Raises:
            ValueError: If key_name is not defined
        """
        if key_name not in cls.ATTRIBUTES:
            raise ValueError(f"Unknown search attribute: {key_name}")
        
        attr_def = cls.ATTRIBUTES[key_name]
        
        if attr_def.type == SearchAttributeType.TEXT:
            return SearchAttributeKey.for_text(key_name)
        elif attr_def.type == SearchAttributeType.INT:
            return SearchAttributeKey.for_int(key_name)
        elif attr_def.type == SearchAttributeType.DOUBLE:
            return SearchAttributeKey.for_float(key_name)
        elif attr_def.type == SearchAttributeType.BOOL:
            return SearchAttributeKey.for_bool(key_name)
        elif attr_def.type == SearchAttributeType.DATETIME:
            return SearchAttributeKey.for_datetime(key_name)
        elif attr_def.type == SearchAttributeType.TEXT_ARRAY:
            return SearchAttributeKey.for_text_array(key_name)
        else:
            raise ValueError(f"Unsupported search attribute type: {attr_def.type}")


class SearchAttributeUpdater:
    """Utility class for updating search attributes with type safety."""
    
    def __init__(self):
        """Initialize the search attribute updater."""
        self._pending_updates: Dict[str, Any] = {}
    
    def set_workflow_status(self, status: Union[JobStatus, str]) -> 'SearchAttributeUpdater':
        """Set workflow status attribute.
        
        Args:
            status: Workflow status
            
        Returns:
            Self for method chaining
        """
        status_value = status.value if isinstance(status, JobStatus) else str(status)
        self._pending_updates["WorkflowStatus"] = status_value
        return self
    
    def set_progress_percentage(self, percentage: int) -> 'SearchAttributeUpdater':
        """Set progress percentage attribute.
        
        Args:
            percentage: Progress percentage (0-100)
            
        Returns:
            Self for method chaining
        """
        if not 0 <= percentage <= 100:
            raise ValueError("Progress percentage must be between 0 and 100")
        self._pending_updates["ProgressPercentage"] = percentage
        return self
    
    def set_current_step(self, step: Union[Step, str]) -> 'SearchAttributeUpdater':
        """Set current step attribute.
        
        Args:
            step: Current workflow step
            
        Returns:
            Self for method chaining
        """
        step_value = step.value if isinstance(step, Step) else str(step)
        self._pending_updates["CurrentStep"] = step_value
        return self
    
    def set_error_count(self, count: int) -> 'SearchAttributeUpdater':
        """Set error count attribute.
        
        Args:
            count: Number of errors
            
        Returns:
            Self for method chaining
        """
        if count < 0:
            raise ValueError("Error count cannot be negative")
        self._pending_updates["ErrorCount"] = count
        return self
    
    def set_last_update_time(self, timestamp: Optional[datetime] = None) -> 'SearchAttributeUpdater':
        """Set last update time attribute.
        
        Args:
            timestamp: Update timestamp (defaults to current time)
            
        Returns:
            Self for method chaining
        """
        self._pending_updates["LastUpdateTime"] = timestamp or datetime.utcnow()
        return self
    
    def set_job_type(self, job_type: Union[JobType, str]) -> 'SearchAttributeUpdater':
        """Set job type attribute.
        
        Args:
            job_type: Type of job
            
        Returns:
            Self for method chaining
        """
        job_type_value = job_type.value if isinstance(job_type, JobType) else str(job_type)
        self._pending_updates["JobType"] = job_type_value
        return self
    
    def set_user_id(self, user_id: str) -> 'SearchAttributeUpdater':
        """Set user ID attribute.
        
        Args:
            user_id: User identifier
            
        Returns:
            Self for method chaining
        """
        self._pending_updates["UserId"] = str(user_id)
        return self
    
    def set_request_id(self, request_id: str) -> 'SearchAttributeUpdater':
        """Set request ID attribute.
        
        Args:
            request_id: Request identifier
            
        Returns:
            Self for method chaining
        """
        self._pending_updates["RequestId"] = str(request_id)
        return self
    
    def set_retry_count(self, count: int) -> 'SearchAttributeUpdater':
        """Set retry count attribute.
        
        Args:
            count: Number of retries
            
        Returns:
            Self for method chaining
        """
        if count < 0:
            raise ValueError("Retry count cannot be negative")
        self._pending_updates["RetryCount"] = count
        return self
    
    def set_duration_seconds(self, duration: int) -> 'SearchAttributeUpdater':
        """Set duration attribute.
        
        Args:
            duration: Duration in seconds
            
        Returns:
            Self for method chaining
        """
        if duration < 0:
            raise ValueError("Duration cannot be negative")
        self._pending_updates["DurationSeconds"] = duration
        return self
    
    def set_prompt_hash(self, prompt: str) -> 'SearchAttributeUpdater':
        """Set prompt hash attribute.
        
        Args:
            prompt: Input prompt to hash
            
        Returns:
            Self for method chaining
        """
        prompt_hash = str(hash(prompt))[-8:]  # Last 8 chars of hash
        self._pending_updates["PromptHash"] = prompt_hash
        return self
    
    def set_asset_count(self, count: int) -> 'SearchAttributeUpdater':
        """Set asset count attribute.
        
        Args:
            count: Number of assets
            
        Returns:
            Self for method chaining
        """
        if count < 0:
            raise ValueError("Asset count cannot be negative")
        self._pending_updates["AssetCount"] = count
        return self
    
    def set_file_size_mb(self, size_mb: int) -> 'SearchAttributeUpdater':
        """Set file size attribute.
        
        Args:
            size_mb: File size in megabytes
            
        Returns:
            Self for method chaining
        """
        if size_mb < 0:
            raise ValueError("File size cannot be negative")
        self._pending_updates["FileSizeMB"] = size_mb
        return self
    
    def set_custom_progress(self, step: str, status: str, percent: int) -> 'SearchAttributeUpdater':
        """Set custom progress attribute with step:status:percent format.
        
        Args:
            step: Current workflow step
            status: Current status
            percent: Progress percentage (0-100)
            
        Returns:
            Self for method chaining
        """
        if not 0 <= percent <= 100:
            raise ValueError("Progress percentage must be between 0 and 100")
        progress_value = f"{step}:{status}:{percent}"
        self._pending_updates["CustomProgress"] = progress_value
        return self
    
    def set_custom_tag(self, tag: str) -> 'SearchAttributeUpdater':
        """Set custom tag attribute for workflow categorization.
        
        Args:
            tag: Custom tag value (e.g., batch1, test_run, production)
            
        Returns:
            Self for method chaining
        """
        if not tag or not isinstance(tag, str):
            raise ValueError("Custom tag must be a non-empty string")
        self._pending_updates["CustomTag"] = tag
        return self
    
    def set_custom_attribute(self, key: str, value: Any) -> 'SearchAttributeUpdater':
        """Set a custom search attribute.
        
        Args:
            key: Attribute key
            value: Attribute value
            
        Returns:
            Self for method chaining
        """
        self._pending_updates[key] = value
        return self
    
    def build_search_attribute_pairs(self) -> List[SearchAttributePair]:
        """Build search attribute pairs from pending updates.
        
        Returns:
            List of search attribute pairs ready for upsert
            
        Raises:
            ValueError: If required attributes are missing or invalid
        """
        pairs = []
        
        for key, value in self._pending_updates.items():
            try:
                search_key = WorkflowSearchAttributes.get_search_attribute_key(key)
                pairs.append(SearchAttributePair(search_key, value))
            except ValueError as e:
                # Handle custom attributes that might not be in registry
                if key not in WorkflowSearchAttributes.ATTRIBUTES:
                    # For custom attributes, try to infer type
                    if isinstance(value, str):
                        search_key = SearchAttributeKey.for_text(key)
                    elif isinstance(value, int):
                        search_key = SearchAttributeKey.for_int(key)
                    elif isinstance(value, float):
                        search_key = SearchAttributeKey.for_float(key)
                    elif isinstance(value, bool):
                        search_key = SearchAttributeKey.for_bool(key)
                    elif isinstance(value, datetime):
                        search_key = SearchAttributeKey.for_datetime(key)
                    else:
                        raise ValueError(f"Cannot infer type for custom attribute {key} with value {value}")
                    
                    pairs.append(SearchAttributePair(search_key, value))
                else:
                    raise e
        
        return pairs
    
    def apply_updates(self) -> None:
        """Apply all pending updates to workflow search attributes.
        
        This method calls workflow.upsert_search_attributes with all pending updates.
        """
        if not self._pending_updates:
            return
        
        pairs = self.build_search_attribute_pairs()
        workflow.upsert_search_attributes(pairs)
        
        # Clear pending updates after successful application
        self._pending_updates.clear()
    
    def clear_pending_updates(self) -> None:
        """Clear all pending updates without applying them."""
        self._pending_updates.clear()
    
    def get_pending_updates(self) -> Dict[str, Any]:
        """Get copy of pending updates.
        
        Returns:
            Dictionary of pending attribute updates
        """
        return self._pending_updates.copy()


def create_search_attributes_from_state(state: WorkflowState) -> List[SearchAttributePair]:
    """Create search attribute pairs from workflow state.
    
    This is a convenience function that creates search attributes from a WorkflowState object.
    
    Args:
        state: Workflow state to convert
        
    Returns:
        List of search attribute pairs
    """
    updater = SearchAttributeUpdater()
    
    # Set core attributes
    updater.set_workflow_status(state.current_progress.status)
    updater.set_progress_percentage(state.current_progress.percent)
    updater.set_current_step(state.current_progress.step)
    updater.set_error_count(state.retry_count)
    updater.set_last_update_time()
    updater.set_job_type(state.job_input.job_type)
    updater.set_request_id(state.workflow_id)
    updater.set_retry_count(state.retry_count)
    
    # Set optional attributes
    if state.job_input.user_id:
        updater.set_user_id(state.job_input.user_id)
    
    if state.completed_at:
        duration = state.get_duration()
        if duration:
            updater.set_duration_seconds(int(duration))
    
    if state.result_urls:
        updater.set_asset_count(len(state.result_urls))
    
    # Set prompt hash for deduplication
    updater.set_prompt_hash(state.job_input.prompt)
    
    return updater.build_search_attribute_pairs()


def update_workflow_search_attributes(**kwargs) -> None:
    """Convenience function to update workflow search attributes.
    
    Args:
        **kwargs: Attribute key-value pairs to update
        
    Example:
        update_workflow_search_attributes(
            workflow_status="in-progress",
            progress_percentage=50,
            current_step="processing"
        )
    """
    updater = SearchAttributeUpdater()
    
    for key, value in kwargs.items():
        # Convert snake_case to PascalCase for attribute keys
        attr_key = ''.join(word.capitalize() for word in key.split('_'))
        updater.set_custom_attribute(attr_key, value)
    
    updater.apply_updates()