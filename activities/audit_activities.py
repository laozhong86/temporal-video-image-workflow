"""Audit logging activities for Temporal workflows.

This module provides activity functions for logging workflow events and state changes
to PostgreSQL audit logs. These activities are designed to be called from workflows
to maintain a comprehensive audit trail.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import asdict
import logging

from temporalio import activity

from ..models.audit_logging import (
    AuditLogger,
    AuditLoggerFactory,
    AuditEventType,
    AuditLogEntry,
    DatabaseConfig
)
from ..models.core_models import WorkflowState, WorkflowStep


logger = logging.getLogger(__name__)


@activity.defn
async def initialize_audit_logger(config_dict: Dict[str, Any]) -> bool:
    """Initialize the audit logger with database configuration.
    
    Args:
        config_dict: Database configuration as dictionary
        
    Returns:
        True if initialization successful, False otherwise
    """
    try:
        config = DatabaseConfig(**config_dict)
        audit_logger = AuditLoggerFactory.create_logger(config)
        await audit_logger.initialize()
        
        activity.logger.info("Audit logger initialized successfully")
        return True
        
    except Exception as e:
        activity.logger.error(f"Failed to initialize audit logger: {e}")
        return False


@activity.defn
async def log_workflow_started(
    workflow_id: str,
    run_id: str,
    user_id: Optional[str] = None,
    job_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Log workflow started event.
    
    Args:
        workflow_id: Unique workflow identifier
        run_id: Unique run identifier
        user_id: Optional user identifier
        job_type: Optional job type
        metadata: Optional additional metadata
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        log_metadata = metadata or {}
        if job_type:
            log_metadata["job_type"] = job_type
        
        entry_id = await audit_logger.log_workflow_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=AuditEventType.WORKFLOW_STARTED,
            metadata=log_metadata,
            user_id=user_id
        )
        
        activity.logger.info(f"Logged workflow started: {workflow_id}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log workflow started: {e}")
        raise


@activity.defn
async def log_workflow_completed(
    workflow_id: str,
    run_id: str,
    duration_ms: Optional[int] = None,
    final_status: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Log workflow completed event.
    
    Args:
        workflow_id: Unique workflow identifier
        run_id: Unique run identifier
        duration_ms: Total workflow duration in milliseconds
        final_status: Final workflow status
        metadata: Optional additional metadata
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        log_metadata = metadata or {}
        if final_status:
            log_metadata["final_status"] = final_status
        
        entry_id = await audit_logger.log_workflow_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=AuditEventType.WORKFLOW_COMPLETED,
            metadata=log_metadata,
            duration_ms=duration_ms
        )
        
        activity.logger.info(f"Logged workflow completed: {workflow_id}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log workflow completed: {e}")
        raise


@activity.defn
async def log_workflow_failed(
    workflow_id: str,
    run_id: str,
    error_message: str,
    duration_ms: Optional[int] = None,
    step_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Log workflow failed event.
    
    Args:
        workflow_id: Unique workflow identifier
        run_id: Unique run identifier
        error_message: Error description
        duration_ms: Duration until failure in milliseconds
        step_name: Step where failure occurred
        metadata: Optional additional metadata
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        entry_id = await audit_logger.log_workflow_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=AuditEventType.WORKFLOW_FAILED,
            step_name=step_name,
            error_message=error_message,
            metadata=metadata,
            duration_ms=duration_ms
        )
        
        activity.logger.info(f"Logged workflow failed: {workflow_id}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log workflow failed: {e}")
        raise


@activity.defn
async def log_step_started(
    workflow_id: str,
    run_id: str,
    step_name: str,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Log step started event.
    
    Args:
        workflow_id: Unique workflow identifier
        run_id: Unique run identifier
        step_name: Name of the step being started
        metadata: Optional additional metadata
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        entry_id = await audit_logger.log_workflow_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=AuditEventType.STEP_STARTED,
            step_name=step_name,
            new_status="in_progress",
            metadata=metadata
        )
        
        activity.logger.info(f"Logged step started: {step_name} in {workflow_id}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log step started: {e}")
        raise


@activity.defn
async def log_step_completed(
    workflow_id: str,
    run_id: str,
    step_name: str,
    duration_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Log step completed event.
    
    Args:
        workflow_id: Unique workflow identifier
        run_id: Unique run identifier
        step_name: Name of the completed step
        duration_ms: Step duration in milliseconds
        metadata: Optional additional metadata
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        entry_id = await audit_logger.log_workflow_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=AuditEventType.STEP_COMPLETED,
            step_name=step_name,
            old_status="in_progress",
            new_status="completed",
            metadata=metadata,
            duration_ms=duration_ms
        )
        
        activity.logger.info(f"Logged step completed: {step_name} in {workflow_id}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log step completed: {e}")
        raise


@activity.defn
async def log_step_failed(
    workflow_id: str,
    run_id: str,
    step_name: str,
    error_message: str,
    duration_ms: Optional[int] = None,
    retry_count: int = 0,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Log step failed event.
    
    Args:
        workflow_id: Unique workflow identifier
        run_id: Unique run identifier
        step_name: Name of the failed step
        error_message: Error description
        duration_ms: Duration until failure in milliseconds
        retry_count: Number of retries attempted
        metadata: Optional additional metadata
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        log_metadata = metadata or {}
        log_metadata["retry_count"] = retry_count
        
        entry_id = await audit_logger.log_workflow_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=AuditEventType.STEP_FAILED,
            step_name=step_name,
            old_status="in_progress",
            new_status="failed",
            error_message=error_message,
            metadata=log_metadata,
            duration_ms=duration_ms
        )
        
        activity.logger.info(f"Logged step failed: {step_name} in {workflow_id}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log step failed: {e}")
        raise


@activity.defn
async def log_state_change(
    workflow_state_dict: Dict[str, Any],
    old_step_dict: Optional[Dict[str, Any]] = None,
    new_step_dict: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
) -> int:
    """Log a comprehensive state change event.
    
    Args:
        workflow_state_dict: Current workflow state as dictionary
        old_step_dict: Previous step state as dictionary
        new_step_dict: New step state as dictionary
        error_message: Optional error message
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        # Convert dictionaries back to objects
        workflow_state = WorkflowState(**workflow_state_dict)
        old_step = WorkflowStep(**old_step_dict) if old_step_dict else None
        new_step = WorkflowStep(**new_step_dict) if new_step_dict else None
        
        entry_id = await audit_logger.log_state_change(
            workflow_state=workflow_state,
            old_step=old_step,
            new_step=new_step,
            error_message=error_message
        )
        
        activity.logger.info(f"Logged state change for workflow: {workflow_state.workflow_id}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log state change: {e}")
        raise


@activity.defn
async def log_retry_attempt(
    workflow_id: str,
    run_id: str,
    step_name: str,
    retry_count: int,
    error_message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Log retry attempt event.
    
    Args:
        workflow_id: Unique workflow identifier
        run_id: Unique run identifier
        step_name: Name of the step being retried
        retry_count: Current retry attempt number
        error_message: Error that triggered the retry
        metadata: Optional additional metadata
        
    Returns:
        Audit log entry ID
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        log_metadata = metadata or {}
        log_metadata["retry_count"] = retry_count
        
        entry_id = await audit_logger.log_workflow_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=AuditEventType.RETRY_ATTEMPTED,
            step_name=step_name,
            error_message=error_message,
            metadata=log_metadata
        )
        
        activity.logger.info(f"Logged retry attempt {retry_count} for step: {step_name}")
        return entry_id
        
    except Exception as e:
        activity.logger.error(f"Failed to log retry attempt: {e}")
        raise


@activity.defn
async def get_workflow_audit_history(
    workflow_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get audit history for a workflow.
    
    Args:
        workflow_id: Unique workflow identifier
        limit: Maximum number of entries to return
        offset: Number of entries to skip
        
    Returns:
        List of audit log entries as dictionaries
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        entries = await audit_logger.get_workflow_audit_history(
            workflow_id=workflow_id,
            limit=limit,
            offset=offset
        )
        
        # Convert to dictionaries for serialization
        return [asdict(entry) for entry in entries]
        
    except Exception as e:
        activity.logger.error(f"Failed to get workflow audit history: {e}")
        raise


@activity.defn
async def get_audit_summary(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    event_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Get audit summary statistics.
    
    Args:
        start_time: Start time as ISO string
        end_time: End time as ISO string
        event_types: List of event type strings to filter by
        
    Returns:
        Summary statistics dictionary
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        # Convert string dates to datetime objects
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        
        # Convert string event types to enum values
        event_type_enums = None
        if event_types:
            event_type_enums = [AuditEventType(et) for et in event_types]
        
        summary = await audit_logger.get_audit_summary(
            start_time=start_dt,
            end_time=end_dt,
            event_types=event_type_enums
        )
        
        activity.logger.info("Retrieved audit summary")
        return summary
        
    except Exception as e:
        activity.logger.error(f"Failed to get audit summary: {e}")
        raise


@activity.defn
async def cleanup_old_audit_logs(retention_days: int = 90) -> int:
    """Clean up old audit logs based on retention policy.
    
    Args:
        retention_days: Number of days to retain logs
        
    Returns:
        Number of deleted records
    """
    try:
        audit_logger = AuditLoggerFactory.get_logger()
        if not audit_logger:
            raise RuntimeError("Audit logger not initialized")
        
        deleted_count = await audit_logger.cleanup_old_logs(retention_days)
        
        activity.logger.info(f"Cleaned up {deleted_count} old audit log entries")
        return deleted_count
        
    except Exception as e:
        activity.logger.error(f"Failed to cleanup old audit logs: {e}")
        raise


@activity.defn
async def close_audit_logger() -> bool:
    """Close the audit logger and clean up resources.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        await AuditLoggerFactory.close_logger()
        activity.logger.info("Audit logger closed successfully")
        return True
        
    except Exception as e:
        activity.logger.error(f"Failed to close audit logger: {e}")
        return False