"""Query activities for Temporal workflows.

This module provides activity functions for querying workflow states and execution
information using Temporal's List API and search attributes. These activities can
be called from within Temporal workflows to retrieve state information.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import logging

from temporalio import activity
from temporalio.client import Client

from ..models.state_queries import (
    WorkflowStateQuery,
    QueryFilter,
    QueryOptions,
    QueryResult,
    QueryOperator,
    QueryBuilder
)
from ..models.core_models import WorkflowState
from ..config import AppConfig


# Global query client - will be initialized by the worker
_query_client: Optional[WorkflowStateQuery] = None


def initialize_query_client(temporal_client: Client) -> None:
    """Initialize the global query client.
    
    Args:
        temporal_client: Temporal client instance
    """
    global _query_client
    _query_client = WorkflowStateQuery(temporal_client)


def get_query_client() -> WorkflowStateQuery:
    """Get the initialized query client.
    
    Returns:
        Query client instance
        
    Raises:
        RuntimeError: If client is not initialized
    """
    if _query_client is None:
        raise RuntimeError("Query client not initialized. Call initialize_query_client first.")
    return _query_client


@activity.defn
async def query_workflows_by_status(
    status: Union[str, List[str]],
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query workflows by execution status.
    
    Args:
        status: Single status or list of statuses to filter by
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        result = await query_client.query_by_status(status, options)
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query workflows by status: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_workflows_by_progress(
    min_progress: int = 0,
    max_progress: int = 100,
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query workflows by progress percentage range.
    
    Args:
        min_progress: Minimum progress percentage (0-100)
        max_progress: Maximum progress percentage (0-100)
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        result = await query_client.query_by_progress_range(
            min_progress, max_progress, options
        )
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query workflows by progress: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_workflows_by_errors(
    min_errors: int = 1,
    max_errors: Optional[int] = None,
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query workflows by error count.
    
    Args:
        min_errors: Minimum number of errors
        max_errors: Maximum number of errors (optional)
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        result = await query_client.query_by_error_count(
            min_errors, max_errors, options
        )
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query workflows by errors: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_workflows_by_time_range(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    time_field: str = "StartTime",
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query workflows by time range.
    
    Args:
        start_time: Start time in ISO format (optional)
        end_time: End time in ISO format (optional)
        time_field: Time field to filter on (StartTime, CloseTime, etc.)
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        # Parse datetime strings
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        
        result = await query_client.query_by_time_range(
            start_dt, end_dt, time_field, options
        )
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query workflows by time range: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_workflows_by_user(
    user_id: Union[str, List[str]],
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query workflows by user ID.
    
    Args:
        user_id: Single user ID or list of user IDs
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        result = await query_client.query_by_user(user_id, options)
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query workflows by user: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_workflows_by_job_type(
    job_type: Union[str, List[str]],
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query workflows by job type.
    
    Args:
        job_type: Single job type or list of job types
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        result = await query_client.query_by_job_type(job_type, options)
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query workflows by job type: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_active_workflows(
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query currently active (running) workflows.
    
    Args:
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        result = await query_client.query_active_workflows(options)
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query active workflows: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_failed_workflows(
    since_hours: Optional[int] = None,
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query failed workflows.
    
    Args:
        since_hours: Only include failures from the last N hours (optional)
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        since = None
        if since_hours is not None:
            since = datetime.utcnow() - timedelta(hours=since_hours)
        
        result = await query_client.query_failed_workflows(since, options)
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query failed workflows: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def query_long_running_workflows(
    min_duration_hours: int = 24,
    page_size: int = 100,
    next_page_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query long-running workflows.
    
    Args:
        min_duration_hours: Minimum duration in hours
        page_size: Number of results per page
        next_page_token: Token for pagination
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token
        )
        
        result = await query_client.query_long_running_workflows(
            min_duration_hours, options
        )
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to query long-running workflows: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def get_workflow_details(
    workflow_id: str,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """Get detailed information about a specific workflow.
    
    Args:
        workflow_id: Workflow ID
        run_id: Optional run ID (uses latest if not provided)
        
    Returns:
        Workflow details dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        details = await query_client.get_workflow_details(workflow_id, run_id)
        
        if details:
            return {
                "success": True,
                "workflow": details
            }
        else:
            return {
                "success": False,
                "error": "Workflow not found",
                "workflow": None
            }
        
    except Exception as e:
        logger.error(f"Failed to get workflow details: {e}")
        return {
            "success": False,
            "error": str(e),
            "workflow": None
        }


@activity.defn
async def count_workflows_by_status(
    status: Union[str, List[str]]
) -> Dict[str, Any]:
    """Count workflows by status.
    
    Args:
        status: Single status or list of statuses to count
        
    Returns:
        Count result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        
        if isinstance(status, str):
            status = [status]
        
        filters = [QueryFilter(
            attribute="ExecutionStatus",
            operator=QueryOperator.IN,
            value=status
        )]
        
        count = await query_client.count_workflows(filters)
        
        return {
            "success": True,
            "count": count,
            "status_filter": status
        }
        
    except Exception as e:
        logger.error(f"Failed to count workflows by status: {e}")
        return {
            "success": False,
            "error": str(e),
            "count": 0,
            "status_filter": status
        }


@activity.defn
async def build_custom_query(
    filters: List[Dict[str, Any]],
    page_size: int = 100,
    next_page_token: Optional[str] = None,
    order_by: Optional[str] = None
) -> Dict[str, Any]:
    """Build and execute a custom query with multiple filters.
    
    Args:
        filters: List of filter dictionaries with keys: attribute, operator, value, value2
        page_size: Number of results per page
        next_page_token: Token for pagination
        order_by: Optional ordering specification
        
    Returns:
        Query result dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        
        # Convert filter dictionaries to QueryFilter objects
        query_filters = []
        for f in filters:
            query_filters.append(QueryFilter(
                attribute=f["attribute"],
                operator=QueryOperator(f["operator"]),
                value=f["value"],
                value2=f.get("value2")
            ))
        
        options = QueryOptions(
            page_size=page_size,
            next_page_token=next_page_token,
            order_by=order_by
        )
        
        result = await query_client.query_with_custom_filters(query_filters, options)
        
        return {
            "success": True,
            "executions": result.executions,
            "next_page_token": result.next_page_token,
            "total_count": result.total_count,
            "query_time_ms": result.query_time_ms
        }
        
    except Exception as e:
        logger.error(f"Failed to execute custom query: {e}")
        return {
            "success": False,
            "error": str(e),
            "executions": [],
            "next_page_token": None,
            "total_count": 0,
            "query_time_ms": 0
        }


@activity.defn
async def get_workflow_statistics(
    time_range_hours: int = 24
) -> Dict[str, Any]:
    """Get workflow execution statistics for a time range.
    
    Args:
        time_range_hours: Time range in hours to analyze
        
    Returns:
        Statistics dictionary
    """
    logger = activity.logger
    
    try:
        query_client = get_query_client()
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_range_hours)
        
        # Query for different statuses
        statuses = ["Running", "Completed", "Failed", "Canceled", "Terminated"]
        stats = {
            "time_range": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "hours": time_range_hours
            },
            "counts_by_status": {},
            "total_workflows": 0
        }
        
        total_count = 0
        for status in statuses:
            filters = [
                QueryFilter(
                    attribute="ExecutionStatus",
                    operator=QueryOperator.EQUALS,
                    value=status
                ),
                QueryFilter(
                    attribute="StartTime",
                    operator=QueryOperator.GREATER_THAN_OR_EQUAL,
                    value=start_time
                ),
                QueryFilter(
                    attribute="StartTime",
                    operator=QueryOperator.LESS_THAN_OR_EQUAL,
                    value=end_time
                )
            ]
            
            count = await query_client.count_workflows(filters)
            stats["counts_by_status"][status] = count
            total_count += count
        
        stats["total_workflows"] = total_count
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflow statistics: {e}")
        return {
            "success": False,
            "error": str(e),
            "statistics": None
        }