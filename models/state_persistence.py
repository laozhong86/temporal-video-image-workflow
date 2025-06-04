"""State persistence system using Temporal search attributes and PostgreSQL.

This module implements state management leveraging Temporal's native capabilities:
- Search attributes for real-time state tracking
- PostgreSQL backend through Temporal's visibility store
- Type-safe attribute management
- Audit logging capabilities
"""

from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from enum import Enum

from temporalio import workflow
from temporalio.common import SearchAttributeKey, SearchAttributePair, TypedSearchAttributes
from pydantic import BaseModel, Field

from models.core_models import WorkflowState, Progress, JobStatus, Step


class StateSearchAttributes:
    """Defines search attribute keys for workflow state management."""
    
    # Core state attributes
    WORKFLOW_STATUS = SearchAttributeKey.for_text("WorkflowStatus")
    PROGRESS_PERCENTAGE = SearchAttributeKey.for_int("ProgressPercentage")
    CURRENT_STEP = SearchAttributeKey.for_text("CurrentStep")
    ERROR_COUNT = SearchAttributeKey.for_int("ErrorCount")
    LAST_UPDATE_TIME = SearchAttributeKey.for_datetime("LastUpdateTime")
    
    # Additional tracking attributes
    JOB_TYPE = SearchAttributeKey.for_text("JobType")
    USER_ID = SearchAttributeKey.for_text("UserId")
    REQUEST_ID = SearchAttributeKey.for_text("RequestId")
    RETRY_COUNT = SearchAttributeKey.for_int("RetryCount")
    DURATION_SECONDS = SearchAttributeKey.for_int("DurationSeconds")
    
    # Business-specific attributes
    PROMPT_HASH = SearchAttributeKey.for_text("PromptHash")
    ASSET_COUNT = SearchAttributeKey.for_int("AssetCount")
    FILE_SIZE_MB = SearchAttributeKey.for_int("FileSizeMB")


class StateUpdateType(str, Enum):
    """Types of state updates for audit logging."""
    WORKFLOW_START = "workflow_start"
    PROGRESS_UPDATE = "progress_update"
    ERROR_OCCURRED = "error_occurred"
    RETRY_ATTEMPT = "retry_attempt"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_FAILED = "workflow_failed"
    RESOURCE_CLEANUP = "resource_cleanup"


class StateAuditEntry(BaseModel):
    """Audit log entry for state changes."""
    
    workflow_id: str = Field(..., description="Workflow identifier")
    update_type: StateUpdateType = Field(..., description="Type of state update")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")
    
    # State data
    previous_state: Optional[Dict[str, Any]] = Field(default=None, description="Previous state snapshot")
    new_state: Dict[str, Any] = Field(..., description="New state snapshot")
    
    # Context information
    user_id: Optional[str] = Field(default=None, description="User identifier")
    request_id: Optional[str] = Field(default=None, description="Request identifier")
    error_message: Optional[str] = Field(default=None, description="Error message if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'StateAuditEntry':
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class WorkflowStateManager:
    """Manages workflow state using Temporal search attributes."""
    
    def __init__(self, workflow_id: str):
        """Initialize state manager for a workflow.
        
        Args:
            workflow_id: Unique workflow identifier
        """
        self.workflow_id = workflow_id
        self._current_state: Optional[WorkflowState] = None
        self._audit_entries: List[StateAuditEntry] = []
    
    async def initialize_state(self, workflow_state: WorkflowState) -> None:
        """Initialize workflow state with search attributes.
        
        Args:
            workflow_state: Initial workflow state
        """
        self._current_state = workflow_state
        
        # Create initial search attributes
        search_attrs = self._create_search_attributes(workflow_state)
        
        # Update search attributes in Temporal
        workflow.upsert_search_attributes(search_attrs)
        
        # Create audit entry
        audit_entry = StateAuditEntry(
            workflow_id=self.workflow_id,
            update_type=StateUpdateType.WORKFLOW_START,
            new_state=workflow_state.model_dump(),
            user_id=workflow_state.job_input.user_id,
            request_id=workflow_state.workflow_id
        )
        self._audit_entries.append(audit_entry)
    
    async def update_progress(self, progress: Progress) -> None:
        """Update workflow progress and search attributes.
        
        Args:
            progress: New progress information
        """
        if not self._current_state:
            raise ValueError("State not initialized. Call initialize_state first.")
        
        # Store previous state for audit
        previous_state = self._current_state.model_dump()
        
        # Update current state
        self._current_state.add_progress_update(progress)
        
        # Update search attributes
        search_attrs = self._create_search_attributes(self._current_state)
        workflow.upsert_search_attributes(search_attrs)
        
        # Create audit entry
        audit_entry = StateAuditEntry(
            workflow_id=self.workflow_id,
            update_type=StateUpdateType.PROGRESS_UPDATE,
            previous_state=previous_state,
            new_state=self._current_state.model_dump(),
            user_id=self._current_state.job_input.user_id,
            request_id=self._current_state.workflow_id
        )
        self._audit_entries.append(audit_entry)
    
    async def record_error(self, error_message: str, retry_count: int = 0) -> None:
        """Record error occurrence and update state.
        
        Args:
            error_message: Error description
            retry_count: Current retry attempt count
        """
        if not self._current_state:
            raise ValueError("State not initialized. Call initialize_state first.")
        
        # Store previous state for audit
        previous_state = self._current_state.model_dump()
        
        # Update error information
        self._current_state.increment_retry(error_message)
        
        # Update search attributes
        search_attrs = self._create_search_attributes(self._current_state)
        workflow.upsert_search_attributes(search_attrs)
        
        # Create audit entry
        audit_entry = StateAuditEntry(
            workflow_id=self.workflow_id,
            update_type=StateUpdateType.ERROR_OCCURRED,
            previous_state=previous_state,
            new_state=self._current_state.model_dump(),
            user_id=self._current_state.job_input.user_id,
            request_id=self._current_state.workflow_id,
            error_message=error_message,
            metadata={"retry_count": retry_count}
        )
        self._audit_entries.append(audit_entry)
    
    async def complete_workflow(self, result_urls: List[str] = None) -> None:
        """Mark workflow as completed and update final state.
        
        Args:
            result_urls: URLs of generated assets
        """
        if not self._current_state:
            raise ValueError("State not initialized. Call initialize_state first.")
        
        # Store previous state for audit
        previous_state = self._current_state.model_dump()
        
        # Update result URLs if provided
        if result_urls:
            self._current_state.result_urls = result_urls
        
        # Update completion time
        self._current_state.completed_at = datetime.utcnow()
        
        # Update search attributes with final state
        search_attrs = self._create_search_attributes(self._current_state)
        workflow.upsert_search_attributes(search_attrs)
        
        # Create audit entry
        audit_entry = StateAuditEntry(
            workflow_id=self.workflow_id,
            update_type=StateUpdateType.WORKFLOW_COMPLETE,
            previous_state=previous_state,
            new_state=self._current_state.model_dump(),
            user_id=self._current_state.job_input.user_id,
            request_id=self._current_state.workflow_id,
            metadata={
                "duration_seconds": self._current_state.get_duration(),
                "asset_count": len(result_urls) if result_urls else 0
            }
        )
        self._audit_entries.append(audit_entry)
    
    def _create_search_attributes(self, state: WorkflowState) -> List[SearchAttributePair]:
        """Create search attribute pairs from workflow state.
        
        Args:
            state: Current workflow state
            
        Returns:
            List of search attribute pairs
        """
        attrs = [
            SearchAttributePair(StateSearchAttributes.WORKFLOW_STATUS, state.current_progress.status.value),
            SearchAttributePair(StateSearchAttributes.PROGRESS_PERCENTAGE, state.current_progress.percent),
            SearchAttributePair(StateSearchAttributes.CURRENT_STEP, state.current_progress.step.value),
            SearchAttributePair(StateSearchAttributes.ERROR_COUNT, state.retry_count),
            SearchAttributePair(StateSearchAttributes.LAST_UPDATE_TIME, datetime.utcnow()),
            SearchAttributePair(StateSearchAttributes.JOB_TYPE, state.job_input.job_type.value),
            SearchAttributePair(StateSearchAttributes.REQUEST_ID, state.workflow_id),
            SearchAttributePair(StateSearchAttributes.RETRY_COUNT, state.retry_count),
        ]
        
        # Add optional attributes
        if state.job_input.user_id:
            attrs.append(SearchAttributePair(StateSearchAttributes.USER_ID, state.job_input.user_id))
        
        if state.completed_at:
            duration = state.get_duration()
            if duration:
                attrs.append(SearchAttributePair(StateSearchAttributes.DURATION_SECONDS, int(duration)))
        
        if state.result_urls:
            attrs.append(SearchAttributePair(StateSearchAttributes.ASSET_COUNT, len(state.result_urls)))
        
        # Add prompt hash for deduplication
        prompt_hash = str(hash(state.job_input.prompt))[-8:]  # Last 8 chars of hash
        attrs.append(SearchAttributePair(StateSearchAttributes.PROMPT_HASH, prompt_hash))
        
        return attrs
    
    def get_current_state(self) -> Optional[WorkflowState]:
        """Get current workflow state.
        
        Returns:
            Current workflow state or None if not initialized
        """
        return self._current_state
    
    def get_audit_entries(self) -> List[StateAuditEntry]:
        """Get all audit entries for this workflow.
        
        Returns:
            List of audit entries
        """
        return self._audit_entries.copy()
    
    def to_json(self) -> str:
        """Serialize state manager to JSON.
        
        Returns:
            JSON string representation
        """
        data = {
            "workflow_id": self.workflow_id,
            "current_state": self._current_state.model_dump() if self._current_state else None,
            "audit_entries": [entry.model_dump() for entry in self._audit_entries]
        }
        return str(data)  # Simple string representation for now