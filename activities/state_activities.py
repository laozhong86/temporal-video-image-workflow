"""State Management Activities

This module provides Temporal activity functions for managing workflow state
and search attributes. Activities encapsulate state update logic and provide
reliable, retryable operations for state persistence.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

from temporalio import activity
from temporalio.exceptions import ApplicationError

from models.core_models import WorkflowState, Progress, JobStatus, Step, JobInput, JobType
from models.search_attributes import (
    SearchAttributeUpdater,
    create_search_attributes_from_state,
    update_workflow_search_attributes
)

# Configure logging
logger = logging.getLogger(__name__)


class StateValidationError(ApplicationError):
    """Raised when state validation fails."""
    pass


class StateTransitionError(ApplicationError):
    """Raised when state transition is invalid."""
    pass


@activity.defn
async def initialize_workflow_state(
    workflow_id: str,
    job_input: Dict[str, Any],
    initial_step: str = "INITIALIZATION"
) -> Dict[str, Any]:
    """Initialize workflow state and search attributes.
    
    Args:
        workflow_id: Unique workflow identifier
        job_input: Job input parameters
        initial_step: Initial workflow step
        
    Returns:
        Dictionary containing initialized state information
        
    Raises:
        StateValidationError: If input validation fails
    """
    try:
        logger.info(f"Initializing workflow state for {workflow_id}")
        
        # Validate input
        if not workflow_id:
            raise StateValidationError("Workflow ID cannot be empty")
        
        if not job_input:
            raise StateValidationError("Job input cannot be empty")
        
        # Create job input object
        try:
            job_input_obj = JobInput(**job_input)
        except Exception as e:
            raise StateValidationError(f"Invalid job input: {str(e)}")
        
        # Create initial progress
        initial_progress = Progress(
            step=Step(initial_step),
            status=JobStatus.PENDING,
            percent=0,
            message="Workflow initialized",
            updated_at=datetime.utcnow()
        )
        
        # Create initial workflow state
        workflow_state = WorkflowState(
            workflow_id=workflow_id,
            job_input=job_input_obj,
            current_progress=initial_progress,
            started_at=datetime.utcnow(),
            retry_count=0,
            error_messages=[],
            result_urls=[]
        )
        
        # Update search attributes
        updater = SearchAttributeUpdater()
        updater.set_workflow_status(JobStatus.PENDING)
        updater.set_progress_percentage(0)
        updater.set_current_step(initial_step)
        updater.set_error_count(0)
        updater.set_last_update_time()
        updater.set_job_type(job_input_obj.job_type)
        updater.set_request_id(workflow_id)
        updater.set_retry_count(0)
        
        # Set initial custom progress and tag
        updater.set_custom_progress(initial_step.value, JobStatus.PENDING.value, 0)
        updater.set_custom_tag(f"{initial_step.value}_pending_initialized")
        
        if job_input_obj.user_id:
            updater.set_user_id(job_input_obj.user_id)
        
        updater.set_prompt_hash(job_input_obj.prompt)
        updater.apply_updates()
        
        logger.info(f"Successfully initialized workflow state for {workflow_id}")
        
        return {
            "workflow_id": workflow_id,
            "status": "initialized",
            "step": initial_step,
            "progress_percent": 0,
            "initialized_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize workflow state for {workflow_id}: {str(e)}")
        raise


@activity.defn
async def update_workflow_progress(
    workflow_id: str,
    step: str,
    status: str,
    progress_percent: int,
    message: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Update workflow progress and search attributes.
    
    Args:
        workflow_id: Workflow identifier
        step: Current workflow step
        status: Current status
        progress_percent: Progress percentage (0-100)
        message: Optional progress message
        additional_data: Additional data to include in search attributes
        
    Returns:
        Dictionary containing update confirmation
        
    Raises:
        StateValidationError: If input validation fails
        StateTransitionError: If state transition is invalid
    """
    try:
        logger.info(f"Updating progress for {workflow_id}: {step} - {status} ({progress_percent}%)")
        
        # Validate inputs
        if not workflow_id:
            raise StateValidationError("Workflow ID cannot be empty")
        
        if not 0 <= progress_percent <= 100:
            raise StateValidationError("Progress percentage must be between 0 and 100")
        
        try:
            job_status = JobStatus(status)
            workflow_step = Step(step)
        except ValueError as e:
            raise StateValidationError(f"Invalid status or step: {str(e)}")
        
        # Update search attributes
        updater = SearchAttributeUpdater()
        updater.set_workflow_status(job_status)
        updater.set_progress_percentage(progress_percent)
        updater.set_current_step(workflow_step)
        updater.set_last_update_time()
        
        # Set custom progress attribute with step:status:percent format
        updater.set_custom_progress(workflow_step.value, job_status.value, progress_percent)
        
        # Set custom tag based on workflow step and status
        tag = f"{workflow_step.value}_{job_status.value}"
        if message:
            tag += f"_{message.replace(' ', '_').lower()}"
        updater.set_custom_tag(tag)
        
        # Add additional data if provided
        if additional_data:
            for key, value in additional_data.items():
                if key == "retry_count":
                    updater.set_retry_count(value)
                elif key == "asset_count":
                    updater.set_asset_count(value)
                elif key == "file_size_mb":
                    updater.set_file_size_mb(value)
                elif key == "custom_tag":
                    # Allow overriding custom tag through additional_data
                    updater.set_custom_tag(str(value))
                else:
                    updater.set_custom_attribute(key, value)
        
        updater.apply_updates()
        
        logger.info(f"Successfully updated progress for {workflow_id}")
        
        return {
            "workflow_id": workflow_id,
            "step": step,
            "status": status,
            "progress_percent": progress_percent,
            "message": message,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to update progress for {workflow_id}: {str(e)}")
        raise


@activity.defn
async def record_workflow_error(
    workflow_id: str,
    error_message: str,
    error_type: str = "GENERAL_ERROR",
    step: Optional[str] = None,
    retry_count: Optional[int] = None,
    is_recoverable: bool = True
) -> Dict[str, Any]:
    """Record workflow error and update search attributes.
    
    Args:
        workflow_id: Workflow identifier
        error_message: Error description
        error_type: Type of error
        step: Step where error occurred
        retry_count: Current retry count
        is_recoverable: Whether error is recoverable
        
    Returns:
        Dictionary containing error record confirmation
        
    Raises:
        StateValidationError: If input validation fails
    """
    try:
        logger.error(f"Recording error for {workflow_id}: {error_type} - {error_message}")
        
        # Validate inputs
        if not workflow_id:
            raise StateValidationError("Workflow ID cannot be empty")
        
        if not error_message:
            raise StateValidationError("Error message cannot be empty")
        
        # Update search attributes
        updater = SearchAttributeUpdater()
        
        # Set error status if not recoverable
        status = JobStatus.FAILED if not is_recoverable else JobStatus.PROCESSING
        updater.set_workflow_status(status)
        
        # Update error count
        current_retry = retry_count if retry_count is not None else 0
        updater.set_error_count(current_retry + 1)
        updater.set_retry_count(current_retry)
        
        if step:
            updater.set_current_step(step)
            # Set custom progress for error state
            progress_percent = 0 if not is_recoverable else 50  # Assume 50% if recoverable
            updater.set_custom_progress(step.value, status.value, progress_percent)
        
        # Set custom tag for error state
        error_tag = f"error_{error_type.lower().replace(' ', '_')}"
        if not is_recoverable:
            error_tag += "_failed"
        else:
            error_tag += "_recoverable"
        updater.set_custom_tag(error_tag)
        
        updater.set_last_update_time()
        
        # Add error-specific attributes
        updater.set_custom_attribute("LastErrorType", error_type)
        updater.set_custom_attribute("LastErrorMessage", error_message[:500])  # Truncate long messages
        updater.set_custom_attribute("IsRecoverable", is_recoverable)
        
        updater.apply_updates()
        
        logger.info(f"Successfully recorded error for {workflow_id}")
        
        return {
            "workflow_id": workflow_id,
            "error_type": error_type,
            "error_message": error_message,
            "is_recoverable": is_recoverable,
            "retry_count": current_retry,
            "recorded_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to record error for {workflow_id}: {str(e)}")
        raise


@activity.defn
async def finalize_workflow_state(
    workflow_id: str,
    final_status: str,
    result_urls: Optional[List[str]] = None,
    final_message: Optional[str] = None,
    execution_summary: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Finalize workflow state and search attributes.
    
    Args:
        workflow_id: Workflow identifier
        final_status: Final workflow status
        result_urls: List of result URLs
        final_message: Final status message
        execution_summary: Summary of workflow execution
        
    Returns:
        Dictionary containing finalization confirmation
        
    Raises:
        StateValidationError: If input validation fails
    """
    try:
        logger.info(f"Finalizing workflow state for {workflow_id}: {final_status}")
        
        # Validate inputs
        if not workflow_id:
            raise StateValidationError("Workflow ID cannot be empty")
        
        try:
            job_status = JobStatus(final_status)
        except ValueError as e:
            raise StateValidationError(f"Invalid final status: {str(e)}")
        
        # Update search attributes
        updater = SearchAttributeUpdater()
        updater.set_workflow_status(job_status)
        updater.set_current_step("COMPLETION")
        updater.set_last_update_time()
        
        # Set final progress based on status
        final_progress = 100 if job_status == JobStatus.COMPLETED else 0
        if job_status == JobStatus.COMPLETED:
            updater.set_progress_percentage(100)
        elif job_status == JobStatus.FAILED:
            # Keep current progress, don't set to 100 for failed workflows
            final_progress = 0
            pass
        
        # Set final custom progress and tag
        updater.set_custom_progress("COMPLETION", job_status.value, final_progress)
        
        # Set final custom tag
        final_tag = f"completion_{job_status.value.lower()}"
        if final_message:
            final_tag += f"_{final_message.replace(' ', '_').lower()[:20]}"  # Limit tag length
        updater.set_custom_tag(final_tag)
        
        # Add result information
        if result_urls:
            updater.set_asset_count(len(result_urls))
        
        # Add execution summary data
        if execution_summary:
            for key, value in execution_summary.items():
                if key == "duration_seconds":
                    updater.set_duration_seconds(value)
                elif key == "total_file_size_mb":
                    updater.set_file_size_mb(value)
                elif key == "total_retries":
                    updater.set_retry_count(value)
                else:
                    updater.set_custom_attribute(f"Summary{key.title()}", value)
        
        updater.apply_updates()
        
        logger.info(f"Successfully finalized workflow state for {workflow_id}")
        
        return {
            "workflow_id": workflow_id,
            "final_status": final_status,
            "result_count": len(result_urls) if result_urls else 0,
            "final_message": final_message,
            "finalized_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to finalize workflow state for {workflow_id}: {str(e)}")
        raise


@activity.defn
async def validate_state_transition(
    current_step: str,
    current_status: str,
    target_step: str,
    target_status: str
) -> Dict[str, Any]:
    """Validate if a state transition is allowed.
    
    Args:
        current_step: Current workflow step
        current_status: Current workflow status
        target_step: Target workflow step
        target_status: Target workflow status
        
    Returns:
        Dictionary containing validation result
        
    Raises:
        StateTransitionError: If transition is not allowed
    """
    try:
        logger.debug(f"Validating transition: {current_step}:{current_status} -> {target_step}:{target_status}")
        
        # Parse statuses and steps
        try:
            current_job_status = JobStatus(current_status)
            target_job_status = JobStatus(target_status)
            current_workflow_step = Step(current_step)
            target_workflow_step = Step(target_step)
        except ValueError as e:
            raise StateTransitionError(f"Invalid status or step: {str(e)}")
        
        # Define valid transitions
        valid_transitions = {
            JobStatus.PENDING: [JobStatus.IN_PROGRESS, JobStatus.FAILED],
            JobStatus.IN_PROGRESS: [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.IN_PROGRESS],
            JobStatus.COMPLETED: [],  # Terminal state
            JobStatus.FAILED: [JobStatus.IN_PROGRESS]  # Can retry
        }
        
        # Check if status transition is valid
        if target_job_status not in valid_transitions.get(current_job_status, []):
            raise StateTransitionError(
                f"Invalid status transition: {current_status} -> {target_status}"
            )
        
        # Define step progression order
        step_order = {
            Step.INITIALIZATION: 0,
            Step.VALIDATION: 1,
            Step.SUBMISSION: 2,
            Step.PROCESSING: 3,
            Step.DOWNLOAD: 4,
            Step.NOTIFICATION: 5,
            Step.COMPLETION: 6,
            Step.ERROR_HANDLING: 99  # Can happen at any time
        }
        
        # Check if step transition is valid (can only move forward or to error handling)
        current_order = step_order.get(current_workflow_step, 0)
        target_order = step_order.get(target_workflow_step, 0)
        
        if target_workflow_step != Step.ERROR_HANDLING and target_order < current_order:
            raise StateTransitionError(
                f"Invalid step transition: cannot go backwards from {current_step} to {target_step}"
            )
        
        logger.debug(f"State transition validation passed")
        
        return {
            "is_valid": True,
            "current_step": current_step,
            "current_status": current_status,
            "target_step": target_step,
            "target_status": target_status,
            "validated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"State transition validation failed: {str(e)}")
        raise


@activity.defn
async def get_workflow_state_summary(
    workflow_id: str
) -> Dict[str, Any]:
    """Get a summary of current workflow state from search attributes.
    
    Note: This activity doesn't directly read search attributes (which requires
    special permissions), but provides a template for state summary operations.
    
    Args:
        workflow_id: Workflow identifier
        
    Returns:
        Dictionary containing state summary
    """
    try:
        logger.info(f"Getting state summary for {workflow_id}")
        
        # In a real implementation, this would query search attributes
        # For now, return a template structure
        
        return {
            "workflow_id": workflow_id,
            "summary_generated_at": datetime.utcnow().isoformat(),
            "note": "This is a template. Actual implementation would query search attributes."
        }
        
    except Exception as e:
        logger.error(f"Failed to get state summary for {workflow_id}: {str(e)}")
        raise


# Activity configuration with retry policies
STATE_ACTIVITY_CONFIG = {
    "start_to_close_timeout": timedelta(minutes=5),
    "retry_policy": {
        "initial_interval": timedelta(seconds=1),
        "backoff_coefficient": 2.0,
        "maximum_interval": timedelta(minutes=1),
        "maximum_attempts": 3
    }
}