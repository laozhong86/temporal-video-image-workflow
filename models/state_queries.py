"""State query interfaces using Temporal's List API.

This module provides comprehensive query capabilities for retrieving workflow state
information using Temporal's List API and search attributes. It includes filtering,
pagination, and result formatting utilities.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from temporalio.client import Client, WorkflowExecution
from temporalio.service import WorkflowService
from temporalio.api.workflowservice.v1 import ListWorkflowExecutionsRequest
from temporalio.api.filter.v1 import WorkflowExecutionFilter
from temporalio.api.common.v1 import WorkflowExecution as WorkflowExecutionProto

from .core_models import WorkflowState, StepStatus
from .search_attributes import WorkflowSearchAttributes, SearchAttributeType


class QueryOperator(str, Enum):
    """Query operators for search attributes."""
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    IN = "IN"
    NOT_IN = "NOT IN"
    STARTS_WITH = "STARTS_WITH"
    BETWEEN = "BETWEEN"


@dataclass
class QueryFilter:
    """Filter for workflow queries."""
    attribute: str
    operator: QueryOperator
    value: Union[str, int, float, bool, List[Any]]
    value2: Optional[Union[str, int, float]] = None  # For BETWEEN operator
    
    def to_query_string(self) -> str:
        """Convert filter to Temporal query string format."""
        if self.operator == QueryOperator.BETWEEN:
            if self.value2 is None:
                raise ValueError("BETWEEN operator requires value2")
            return f"{self.attribute} BETWEEN {self._format_value(self.value)} AND {self._format_value(self.value2)}"
        elif self.operator in [QueryOperator.IN, QueryOperator.NOT_IN]:
            if not isinstance(self.value, list):
                raise ValueError(f"{self.operator} operator requires a list value")
            formatted_values = [self._format_value(v) for v in self.value]
            return f"{self.attribute} {self.operator.value} ({', '.join(formatted_values)})"
        else:
            return f"{self.attribute} {self.operator.value} {self._format_value(self.value)}"
    
    def _format_value(self, value: Any) -> str:
        """Format value for query string."""
        if isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, datetime):
            return f"'{value.isoformat()}'"
        else:
            return str(value)


@dataclass
class QueryOptions:
    """Options for workflow queries."""
    page_size: int = 100
    next_page_token: Optional[str] = None
    maximum_page_size: int = 1000
    order_by: Optional[str] = None  # e.g., "StartTime DESC"
    

@dataclass
class QueryResult:
    """Result of a workflow query."""
    executions: List[Dict[str, Any]] = field(default_factory=list)
    next_page_token: Optional[str] = None
    total_count: Optional[int] = None
    query_time_ms: int = 0
    

class WorkflowStateQuery:
    """Query interface for workflow states using Temporal's List API."""
    
    def __init__(self, client: Client):
        self.client = client
        self.logger = logging.getLogger(__name__)
        self.search_attrs = WorkflowSearchAttributes()
    
    async def query_by_status(
        self,
        status: Union[str, List[str]],
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query workflows by status.
        
        Args:
            status: Single status or list of statuses to filter by
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        if isinstance(status, str):
            status = [status]
        
        filter_obj = QueryFilter(
            attribute=self.search_attrs.get_key("workflow_status"),
            operator=QueryOperator.IN,
            value=status
        )
        
        return await self._execute_query([filter_obj], options)
    
    async def query_by_progress_range(
        self,
        min_progress: int = 0,
        max_progress: int = 100,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query workflows by progress percentage range.
        
        Args:
            min_progress: Minimum progress percentage (0-100)
            max_progress: Maximum progress percentage (0-100)
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        filter_obj = QueryFilter(
            attribute=self.search_attrs.get_key("progress_percentage"),
            operator=QueryOperator.BETWEEN,
            value=min_progress,
            value2=max_progress
        )
        
        return await self._execute_query([filter_obj], options)
    
    async def query_by_error_count(
        self,
        min_errors: int = 1,
        max_errors: Optional[int] = None,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query workflows by error count.
        
        Args:
            min_errors: Minimum number of errors
            max_errors: Maximum number of errors (optional)
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        if max_errors is not None:
            filter_obj = QueryFilter(
                attribute=self.search_attrs.get_key("error_count"),
                operator=QueryOperator.BETWEEN,
                value=min_errors,
                value2=max_errors
            )
        else:
            filter_obj = QueryFilter(
                attribute=self.search_attrs.get_key("error_count"),
                operator=QueryOperator.GREATER_THAN_OR_EQUAL,
                value=min_errors
            )
        
        return await self._execute_query([filter_obj], options)
    
    async def query_by_time_range(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        time_field: str = "StartTime",
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query workflows by time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            time_field: Time field to filter on (StartTime, CloseTime, etc.)
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        filters = []
        
        if start_time:
            filters.append(QueryFilter(
                attribute=time_field,
                operator=QueryOperator.GREATER_THAN_OR_EQUAL,
                value=start_time
            ))
        
        if end_time:
            filters.append(QueryFilter(
                attribute=time_field,
                operator=QueryOperator.LESS_THAN_OR_EQUAL,
                value=end_time
            ))
        
        return await self._execute_query(filters, options)
    
    async def query_by_user(
        self,
        user_id: Union[str, List[str]],
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query workflows by user ID.
        
        Args:
            user_id: Single user ID or list of user IDs
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        if isinstance(user_id, str):
            user_id = [user_id]
        
        filter_obj = QueryFilter(
            attribute=self.search_attrs.get_key("user_id"),
            operator=QueryOperator.IN,
            value=user_id
        )
        
        return await self._execute_query([filter_obj], options)
    
    async def query_by_job_type(
        self,
        job_type: Union[str, List[str]],
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query workflows by job type.
        
        Args:
            job_type: Single job type or list of job types
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        if isinstance(job_type, str):
            job_type = [job_type]
        
        filter_obj = QueryFilter(
            attribute=self.search_attrs.get_key("job_type"),
            operator=QueryOperator.IN,
            value=job_type
        )
        
        return await self._execute_query([filter_obj], options)
    
    async def query_active_workflows(
        self,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query currently active (running) workflows.
        
        Args:
            options: Query options for pagination and ordering
            
        Returns:
            Query result with active workflows
        """
        # Query for workflows that are not in terminal states
        filter_obj = QueryFilter(
            attribute="ExecutionStatus",
            operator=QueryOperator.IN,
            value=["Running", "ContinuedAsNew"]
        )
        
        return await self._execute_query([filter_obj], options)
    
    async def query_failed_workflows(
        self,
        since: Optional[datetime] = None,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query failed workflows.
        
        Args:
            since: Only include failures since this time
            options: Query options for pagination and ordering
            
        Returns:
            Query result with failed workflows
        """
        filters = [
            QueryFilter(
                attribute="ExecutionStatus",
                operator=QueryOperator.EQUALS,
                value="Failed"
            )
        ]
        
        if since:
            filters.append(QueryFilter(
                attribute="CloseTime",
                operator=QueryOperator.GREATER_THAN_OR_EQUAL,
                value=since
            ))
        
        return await self._execute_query(filters, options)
    
    async def query_long_running_workflows(
        self,
        min_duration_hours: int = 24,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query long-running workflows.
        
        Args:
            min_duration_hours: Minimum duration in hours
            options: Query options for pagination and ordering
            
        Returns:
            Query result with long-running workflows
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=min_duration_hours)
        
        filters = [
            QueryFilter(
                attribute="StartTime",
                operator=QueryOperator.LESS_THAN_OR_EQUAL,
                value=cutoff_time
            ),
            QueryFilter(
                attribute="ExecutionStatus",
                operator=QueryOperator.IN,
                value=["Running", "ContinuedAsNew"]
            )
        ]
        
        return await self._execute_query(filters, options)
    
    async def query_with_custom_filters(
        self,
        filters: List[QueryFilter],
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Query workflows with custom filters.
        
        Args:
            filters: List of custom filters to apply
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        return await self._execute_query(filters, options)
    
    async def _execute_query(
        self,
        filters: List[QueryFilter],
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Execute a query with the given filters and options.
        
        Args:
            filters: List of filters to apply
            options: Query options for pagination and ordering
            
        Returns:
            Query result with matching workflows
        """
        if options is None:
            options = QueryOptions()
        
        start_time = datetime.utcnow()
        
        try:
            # Build query string
            query_parts = [f.to_query_string() for f in filters]
            query = " AND ".join(query_parts) if query_parts else ""
            
            # Execute the query
            async for page in self.client.list_workflows(
                query=query,
                page_size=options.page_size,
                next_page_token=options.next_page_token
            ):
                executions = []
                for execution in page.executions:
                    exec_dict = await self._format_execution(execution)
                    executions.append(exec_dict)
                
                end_time = datetime.utcnow()
                query_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                return QueryResult(
                    executions=executions,
                    next_page_token=page.next_page_token,
                    query_time_ms=query_time_ms
                )
            
            # If no results
            end_time = datetime.utcnow()
            query_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return QueryResult(
                executions=[],
                query_time_ms=query_time_ms
            )
            
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            raise
    
    async def _format_execution(self, execution) -> Dict[str, Any]:
        """Format a workflow execution for the result.
        
        Args:
            execution: Temporal workflow execution object
            
        Returns:
            Formatted execution dictionary
        """
        try:
            # Extract basic execution info
            exec_dict = {
                "workflow_id": execution.id,
                "run_id": execution.run_id,
                "workflow_type": execution.workflow_type.name if execution.workflow_type else None,
                "status": execution.status.name if execution.status else None,
                "start_time": execution.start_time.isoformat() if execution.start_time else None,
                "close_time": execution.close_time.isoformat() if execution.close_time else None,
                "execution_time": None,
                "task_queue": execution.task_queue,
                "search_attributes": {}
            }
            
            # Calculate execution time if both start and close times are available
            if execution.start_time and execution.close_time:
                duration = execution.close_time - execution.start_time
                exec_dict["execution_time"] = int(duration.total_seconds())
            
            # Extract search attributes
            if hasattr(execution, 'search_attributes') and execution.search_attributes:
                for key, values in execution.search_attributes.indexed_fields.items():
                    if values.data:
                        # Decode the search attribute value
                        # This is a simplified decoding - in practice, you might need
                        # more sophisticated decoding based on the attribute type
                        try:
                            value = values.data[0].decode('utf-8')
                            exec_dict["search_attributes"][key] = value
                        except (UnicodeDecodeError, IndexError):
                            exec_dict["search_attributes"][key] = str(values.data)
            
            return exec_dict
            
        except Exception as e:
            self.logger.warning(f"Failed to format execution {execution.id}: {e}")
            return {
                "workflow_id": getattr(execution, 'id', 'unknown'),
                "run_id": getattr(execution, 'run_id', 'unknown'),
                "error": f"Failed to format: {str(e)}"
            }
    
    async def get_workflow_details(
        self,
        workflow_id: str,
        run_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific workflow.
        
        Args:
            workflow_id: Workflow ID
            run_id: Optional run ID (uses latest if not provided)
            
        Returns:
            Detailed workflow information or None if not found
        """
        try:
            handle = self.client.get_workflow_handle(
                workflow_id=workflow_id,
                run_id=run_id
            )
            
            # Get workflow description
            description = await handle.describe()
            
            # Format the result
            result = {
                "workflow_id": description.id,
                "run_id": description.run_id,
                "workflow_type": description.workflow_type.name,
                "status": description.status.name,
                "start_time": description.start_time.isoformat() if description.start_time else None,
                "close_time": description.close_time.isoformat() if description.close_time else None,
                "task_queue": description.task_queue,
                "search_attributes": {},
                "memo": {},
                "history_length": description.history_length
            }
            
            # Extract search attributes
            if description.search_attributes:
                for key, values in description.search_attributes.indexed_fields.items():
                    if values.data:
                        try:
                            value = values.data[0].decode('utf-8')
                            result["search_attributes"][key] = value
                        except (UnicodeDecodeError, IndexError):
                            result["search_attributes"][key] = str(values.data)
            
            # Extract memo
            if description.memo:
                for key, value in description.memo.fields.items():
                    try:
                        result["memo"][key] = value.decode('utf-8')
                    except UnicodeDecodeError:
                        result["memo"][key] = str(value)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get workflow details for {workflow_id}: {e}")
            return None
    
    async def count_workflows(
        self,
        filters: Optional[List[QueryFilter]] = None
    ) -> int:
        """Count workflows matching the given filters.
        
        Args:
            filters: Optional list of filters to apply
            
        Returns:
            Number of matching workflows
        """
        try:
            count = 0
            options = QueryOptions(page_size=1000)  # Use larger page size for counting
            
            while True:
                result = await self._execute_query(filters or [], options)
                count += len(result.executions)
                
                if not result.next_page_token:
                    break
                
                options.next_page_token = result.next_page_token
            
            return count
            
        except Exception as e:
            self.logger.error(f"Failed to count workflows: {e}")
            return 0


class QueryBuilder:
    """Builder class for constructing complex workflow queries."""
    
    def __init__(self):
        self.filters: List[QueryFilter] = []
        self.options = QueryOptions()
    
    def add_filter(
        self,
        attribute: str,
        operator: QueryOperator,
        value: Any,
        value2: Optional[Any] = None
    ) -> 'QueryBuilder':
        """Add a filter to the query.
        
        Args:
            attribute: Search attribute name
            operator: Query operator
            value: Filter value
            value2: Second value for BETWEEN operator
            
        Returns:
            Self for method chaining
        """
        self.filters.append(QueryFilter(
            attribute=attribute,
            operator=operator,
            value=value,
            value2=value2
        ))
        return self
    
    def with_status(self, status: Union[str, List[str]]) -> 'QueryBuilder':
        """Add status filter."""
        if isinstance(status, str):
            status = [status]
        return self.add_filter(
            "ExecutionStatus",
            QueryOperator.IN,
            status
        )
    
    def with_time_range(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        time_field: str = "StartTime"
    ) -> 'QueryBuilder':
        """Add time range filter."""
        if start_time:
            self.add_filter(time_field, QueryOperator.GREATER_THAN_OR_EQUAL, start_time)
        if end_time:
            self.add_filter(time_field, QueryOperator.LESS_THAN_OR_EQUAL, end_time)
        return self
    
    def with_pagination(
        self,
        page_size: int = 100,
        next_page_token: Optional[str] = None
    ) -> 'QueryBuilder':
        """Set pagination options."""
        self.options.page_size = page_size
        self.options.next_page_token = next_page_token
        return self
    
    def with_ordering(self, order_by: str) -> 'QueryBuilder':
        """Set ordering options."""
        self.options.order_by = order_by
        return self
    
    def build(self) -> Tuple[List[QueryFilter], QueryOptions]:
        """Build the query filters and options.
        
        Returns:
            Tuple of filters and options
        """
        return self.filters, self.options
    
    async def execute(self, query_client: WorkflowStateQuery) -> QueryResult:
        """Execute the built query.
        
        Args:
            query_client: Query client to execute with
            
        Returns:
            Query result
        """
        filters, options = self.build()
        return await query_client.query_with_custom_filters(filters, options)