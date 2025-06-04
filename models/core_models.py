"""Core data models for job inputs, progress tracking, and workflow state management."""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
import json


class Step(str, Enum):
    """Enumeration of workflow steps."""
    IMAGE = "image"
    VIDEO = "video"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    """Status of job execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobInput(BaseModel):
    """Input model for generation jobs."""
    
    prompt: str = Field(
        ..., 
        description="Text prompt for generation",
        min_length=1,
        max_length=500
    )
    style: str = Field(
        default="realistic",
        description="Generation style"
    )
    job_type: Step = Field(
        ...,
        description="Type of generation job"
    )
    
    # Optional parameters
    width: Optional[int] = Field(
        default=1024,
        description="Output width in pixels",
        ge=64,
        le=4096
    )
    height: Optional[int] = Field(
        default=1024,
        description="Output height in pixels",
        ge=64,
        le=4096
    )
    duration: Optional[int] = Field(
        default=None,
        description="Video duration in seconds (for video jobs)",
        ge=1,
        le=60
    )
    
    # Metadata
    user_id: Optional[str] = Field(default=None, description="User identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Prompt validation is handled by Field constraints (min_length=1)
    
    @model_validator(mode='after')
    def validate_duration(self):
        """Validate duration for video jobs."""
        if self.job_type == Step.VIDEO and self.duration is None:
            raise ValueError("Duration is required for video jobs")
        if self.job_type == Step.IMAGE and self.duration is not None:
            raise ValueError("Duration should not be specified for image jobs")
        return self
    
    def to_temporal_payload(self) -> Dict[str, Any]:
        """Convert to Temporal workflow payload."""
        return self.model_dump(exclude_none=True)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'JobInput':
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class Progress(BaseModel):
    """Progress tracking model for workflow execution."""
    
    step: Step = Field(..., description="Current workflow step")
    status: JobStatus = Field(..., description="Current status")
    percent: int = Field(
        ..., 
        description="Progress percentage",
        ge=0,
        le=100
    )
    asset_url: Optional[str] = Field(
        default=None,
        description="URL of generated asset (if available)"
    )
    
    # Additional progress info
    message: Optional[str] = Field(
        default=None,
        description="Progress message or description"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is failed"
    )
    estimated_completion: Optional[datetime] = Field(
        default=None,
        description="Estimated completion time"
    )
    
    # Timestamps
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    
    # Percent validation is handled by Field constraints (ge=0, le=100)
    
    @model_validator(mode='after')
    def validate_status_consistency(self):
        """Validate status and percent consistency."""
        if self.status == JobStatus.COMPLETED and self.percent != 100:
            raise ValueError("Completed status must have 100% progress")
        
        if self.status == JobStatus.PENDING and self.percent != 0:
            raise ValueError("Pending status must have 0% progress")
        
        if self.status == JobStatus.FAILED and self.error_message is None:
            raise ValueError("Failed status must include error message")
        
        return self
    
    def to_temporal_payload(self) -> Dict[str, Any]:
        """Convert to Temporal workflow payload."""
        data = self.model_dump(exclude_none=True)
        # Convert datetime to ISO string for Temporal
        if 'updated_at' in data:
            data['updated_at'] = data['updated_at'].isoformat()
        if 'estimated_completion' in data and data['estimated_completion']:
            data['estimated_completion'] = data['estimated_completion'].isoformat()
        return data
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Progress':
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class WorkflowState(BaseModel):
    """Workflow state management model."""
    
    workflow_id: str = Field(..., description="Unique workflow identifier")
    job_input: JobInput = Field(..., description="Original job input")
    current_progress: Progress = Field(..., description="Current progress state")
    
    # Workflow metadata
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Workflow start time"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Workflow completion time"
    )
    
    # Progress history
    progress_history: List[Progress] = Field(
        default_factory=list,
        description="History of progress updates"
    )
    
    # Error tracking
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts",
        ge=0
    )
    last_error: Optional[str] = Field(
        default=None,
        description="Last error message"
    )
    
    # Result data
    result_urls: List[str] = Field(
        default_factory=list,
        description="URLs of generated assets"
    )
    
    def add_progress_update(self, progress: Progress) -> None:
        """Add a new progress update to history."""
        self.progress_history.append(self.current_progress)
        self.current_progress = progress
        
        # Update completion time if completed
        if progress.status == JobStatus.COMPLETED:
            self.completed_at = datetime.utcnow()
    
    def increment_retry(self, error_message: str) -> None:
        """Increment retry count and update error."""
        self.retry_count += 1
        self.last_error = error_message
    
    def is_terminal_state(self) -> bool:
        """Check if workflow is in a terminal state."""
        return self.current_progress.status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED
        ]
    
    def get_duration(self) -> Optional[float]:
        """Get workflow duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_temporal_payload(self) -> Dict[str, Any]:
        """Convert to Temporal workflow payload."""
        data = self.model_dump(exclude_none=True)
        
        # Convert datetime fields to ISO strings
        datetime_fields = ['started_at', 'completed_at']
        for field in datetime_fields:
            if field in data and data[field]:
                data[field] = data[field].isoformat()
        
        # Convert progress history
        if 'progress_history' in data:
            data['progress_history'] = [
                progress.to_temporal_payload() if hasattr(progress, 'to_temporal_payload') 
                else progress for progress in data['progress_history']
            ]
        
        # Convert current progress
        if 'current_progress' in data:
            data['current_progress'] = (
                data['current_progress'].to_temporal_payload() 
                if hasattr(data['current_progress'], 'to_temporal_payload') 
                else data['current_progress']
            )
        
        # Convert job input
        if 'job_input' in data:
            data['job_input'] = (
                data['job_input'].to_temporal_payload() 
                if hasattr(data['job_input'], 'to_temporal_payload') 
                else data['job_input']
            )
        
        return data
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WorkflowState':
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)
    
    @classmethod
    def create_initial_state(
        cls, 
        workflow_id: str, 
        job_input: JobInput
    ) -> 'WorkflowState':
        """Create initial workflow state."""
        initial_progress = Progress(
            step=Step.PROCESSING,
            status=JobStatus.PENDING,
            percent=0,
            message="Workflow initialized"
        )
        
        return cls(
            workflow_id=workflow_id,
            job_input=job_input,
            current_progress=initial_progress
        )


class JobResult(BaseModel):
    """Final job result model."""
    
    job_input: JobInput = Field(..., description="Original job input")
    final_state: WorkflowState = Field(..., description="Final workflow state")
    
    # Result summary
    success: bool = Field(..., description="Whether job completed successfully")
    asset_urls: List[str] = Field(
        default_factory=list,
        description="URLs of generated assets"
    )
    
    # Performance metrics
    total_duration: Optional[float] = Field(
        default=None,
        description="Total execution time in seconds"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries performed"
    )
    
    # Error info
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if job failed"
    )
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary for reporting."""
        return {
            "job_type": self.job_input.job_type,
            "prompt": self.job_input.prompt[:100] + "..." if len(self.job_input.prompt) > 100 else self.job_input.prompt,
            "success": self.success,
            "duration": self.total_duration,
            "retry_count": self.retry_count,
            "asset_count": len(self.asset_urls),
            "error": self.error_message
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(exclude_none=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'JobResult':
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)