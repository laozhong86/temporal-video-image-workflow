"""Audit logging system for PostgreSQL.

This module provides comprehensive audit logging capabilities for workflow state changes,
including database schema management, connection pooling, and query interfaces.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging

try:
    import asyncpg
    import asyncpg.pool
except ImportError:
    asyncpg = None
    logging.warning("asyncpg not installed. PostgreSQL audit logging will not be available.")

from .core_models import WorkflowState, WorkflowStep, StepStatus


class AuditEventType(str, Enum):
    """Types of audit events."""
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STATE_UPDATED = "state_updated"
    ERROR_RECORDED = "error_recorded"
    RETRY_ATTEMPTED = "retry_attempted"


@dataclass
class AuditLogEntry:
    """Audit log entry model."""
    id: Optional[int] = None
    workflow_id: str = ""
    run_id: str = ""
    event_type: AuditEventType = AuditEventType.STATE_UPDATED
    timestamp: datetime = None
    step_name: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    metadata: Dict[str, Any] = None
    error_message: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    duration_ms: Optional[int] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "temporal_audit"
    username: str = "temporal"
    password: str = "temporal"
    min_connections: int = 5
    max_connections: int = 20
    command_timeout: int = 30
    server_settings: Dict[str, str] = None
    
    def __post_init__(self):
        if self.server_settings is None:
            self.server_settings = {
                "application_name": "temporal_audit_logger",
                "timezone": "UTC"
            }
    
    @property
    def dsn(self) -> str:
        """Get database connection string."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class AuditLogger:
    """PostgreSQL audit logger with connection pooling and transaction management."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool: Optional[asyncpg.pool.Pool] = None
        self.logger = logging.getLogger(__name__)
        self._schema_initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection pool and schema."""
        if asyncpg is None:
            raise RuntimeError("asyncpg is required for PostgreSQL audit logging")
        
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.config.dsn,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                command_timeout=self.config.command_timeout,
                server_settings=self.config.server_settings
            )
            
            await self._ensure_schema()
            self._schema_initialized = True
            self.logger.info("Audit logger initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize audit logger: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self.logger.info("Audit logger closed")
    
    async def _ensure_schema(self) -> None:
        """Ensure audit log schema exists."""
        schema_sql = """
        -- Create audit logs table
        CREATE TABLE IF NOT EXISTS audit_logs (
            id BIGSERIAL PRIMARY KEY,
            workflow_id VARCHAR(255) NOT NULL,
            run_id VARCHAR(255) NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            step_name VARCHAR(100),
            old_status VARCHAR(50),
            new_status VARCHAR(50),
            metadata JSONB,
            error_message TEXT,
            user_id VARCHAR(255),
            session_id VARCHAR(255),
            duration_ms INTEGER
        );
        
        -- Create indexes for efficient querying
        CREATE INDEX IF NOT EXISTS idx_audit_logs_workflow_id ON audit_logs(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_run_id ON audit_logs(run_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_step_name ON audit_logs(step_name);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
        
        -- Create composite indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_audit_logs_workflow_timestamp 
            ON audit_logs(workflow_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_run_timestamp 
            ON audit_logs(run_id, timestamp DESC);
        
        -- Create retention policy function
        CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(retention_days INTEGER DEFAULT 90)
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM audit_logs 
            WHERE timestamp < NOW() - INTERVAL '1 day' * retention_days;
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)
    
    async def log_workflow_event(
        self,
        workflow_id: str,
        run_id: str,
        event_type: AuditEventType,
        step_name: Optional[str] = None,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> int:
        """Log a workflow event to the audit log.
        
        Returns:
            The ID of the created audit log entry.
        """
        if not self._schema_initialized:
            await self.initialize()
        
        entry = AuditLogEntry(
            workflow_id=workflow_id,
            run_id=run_id,
            event_type=event_type,
            step_name=step_name,
            old_status=old_status,
            new_status=new_status,
            metadata=metadata or {},
            error_message=error_message,
            user_id=user_id,
            session_id=session_id,
            duration_ms=duration_ms
        )
        
        return await self._insert_audit_entry(entry)
    
    async def log_state_change(
        self,
        workflow_state: WorkflowState,
        old_step: Optional[WorkflowStep] = None,
        new_step: Optional[WorkflowStep] = None,
        error_message: Optional[str] = None
    ) -> int:
        """Log a workflow state change.
        
        Returns:
            The ID of the created audit log entry.
        """
        # Determine event type
        if error_message:
            event_type = AuditEventType.ERROR_RECORDED
        elif new_step and old_step:
            if new_step.status == StepStatus.IN_PROGRESS:
                event_type = AuditEventType.STEP_STARTED
            elif new_step.status == StepStatus.COMPLETED:
                event_type = AuditEventType.STEP_COMPLETED
            elif new_step.status == StepStatus.FAILED:
                event_type = AuditEventType.STEP_FAILED
            else:
                event_type = AuditEventType.STATE_UPDATED
        else:
            event_type = AuditEventType.STATE_UPDATED
        
        # Prepare metadata
        metadata = {
            "progress_percentage": workflow_state.progress.percentage,
            "total_steps": len(workflow_state.progress.steps),
            "completed_steps": len([s for s in workflow_state.progress.steps.values() 
                                   if s.status == StepStatus.COMPLETED]),
            "job_type": workflow_state.job_input.job_type if workflow_state.job_input else None
        }
        
        if new_step:
            metadata["step_details"] = {
                "step_name": new_step.name,
                "start_time": new_step.start_time.isoformat() if new_step.start_time else None,
                "end_time": new_step.end_time.isoformat() if new_step.end_time else None,
                "retry_count": new_step.retry_count
            }
        
        # Calculate duration if both steps have timing info
        duration_ms = None
        if old_step and new_step and old_step.start_time and new_step.end_time:
            duration = new_step.end_time - old_step.start_time
            duration_ms = int(duration.total_seconds() * 1000)
        
        return await self.log_workflow_event(
            workflow_id=workflow_state.workflow_id,
            run_id=workflow_state.run_id,
            event_type=event_type,
            step_name=new_step.name if new_step else (old_step.name if old_step else None),
            old_status=old_step.status.value if old_step else None,
            new_status=new_step.status.value if new_step else None,
            metadata=metadata,
            error_message=error_message,
            user_id=workflow_state.job_input.user_id if workflow_state.job_input else None,
            duration_ms=duration_ms
        )
    
    async def _insert_audit_entry(self, entry: AuditLogEntry) -> int:
        """Insert audit entry into database."""
        sql = """
        INSERT INTO audit_logs (
            workflow_id, run_id, event_type, timestamp, step_name,
            old_status, new_status, metadata, error_message,
            user_id, session_id, duration_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING id
        """
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    sql,
                    entry.workflow_id,
                    entry.run_id,
                    entry.event_type.value,
                    entry.timestamp,
                    entry.step_name,
                    entry.old_status,
                    entry.new_status,
                    json.dumps(entry.metadata) if entry.metadata else None,
                    entry.error_message,
                    entry.user_id,
                    entry.session_id,
                    entry.duration_ms
                )
                return row['id']
    
    async def get_workflow_audit_history(
        self,
        workflow_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogEntry]:
        """Get audit history for a specific workflow."""
        sql = """
        SELECT * FROM audit_logs 
        WHERE workflow_id = $1 
        ORDER BY timestamp DESC 
        LIMIT $2 OFFSET $3
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, workflow_id, limit, offset)
            return [self._row_to_audit_entry(row) for row in rows]
    
    async def get_run_audit_history(
        self,
        run_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogEntry]:
        """Get audit history for a specific workflow run."""
        sql = """
        SELECT * FROM audit_logs 
        WHERE run_id = $1 
        ORDER BY timestamp DESC 
        LIMIT $2 OFFSET $3
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, run_id, limit, offset)
            return [self._row_to_audit_entry(row) for row in rows]
    
    async def get_audit_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None
    ) -> Dict[str, Any]:
        """Get audit summary statistics."""
        conditions = []
        params = []
        param_count = 0
        
        if start_time:
            param_count += 1
            conditions.append(f"timestamp >= ${param_count}")
            params.append(start_time)
        
        if end_time:
            param_count += 1
            conditions.append(f"timestamp <= ${param_count}")
            params.append(end_time)
        
        if event_types:
            param_count += 1
            conditions.append(f"event_type = ANY(${param_count})")
            params.append([et.value for et in event_types])
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        sql = f"""
        SELECT 
            COUNT(*) as total_events,
            COUNT(DISTINCT workflow_id) as unique_workflows,
            COUNT(DISTINCT run_id) as unique_runs,
            event_type,
            COUNT(*) as event_count
        FROM audit_logs 
        {where_clause}
        GROUP BY event_type
        ORDER BY event_count DESC
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            
            summary = {
                "total_events": 0,
                "unique_workflows": 0,
                "unique_runs": 0,
                "event_breakdown": {}
            }
            
            for row in rows:
                if summary["total_events"] == 0:  # First row
                    summary["total_events"] = row["total_events"]
                    summary["unique_workflows"] = row["unique_workflows"]
                    summary["unique_runs"] = row["unique_runs"]
                
                summary["event_breakdown"][row["event_type"]] = row["event_count"]
            
            return summary
    
    async def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """Clean up old audit logs based on retention policy.
        
        Returns:
            Number of deleted records.
        """
        sql = "SELECT cleanup_old_audit_logs($1)"
        
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(sql, retention_days)
            self.logger.info(f"Cleaned up {result} old audit log entries")
            return result
    
    def _row_to_audit_entry(self, row) -> AuditLogEntry:
        """Convert database row to AuditLogEntry."""
        return AuditLogEntry(
            id=row['id'],
            workflow_id=row['workflow_id'],
            run_id=row['run_id'],
            event_type=AuditEventType(row['event_type']),
            timestamp=row['timestamp'],
            step_name=row['step_name'],
            old_status=row['old_status'],
            new_status=row['new_status'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            error_message=row['error_message'],
            user_id=row['user_id'],
            session_id=row['session_id'],
            duration_ms=row['duration_ms']
        )


class AuditLoggerFactory:
    """Factory for creating audit logger instances."""
    
    _instance: Optional[AuditLogger] = None
    _config: Optional[DatabaseConfig] = None
    
    @classmethod
    def create_logger(cls, config: DatabaseConfig) -> AuditLogger:
        """Create or get existing audit logger instance."""
        if cls._instance is None or cls._config != config:
            cls._instance = AuditLogger(config)
            cls._config = config
        return cls._instance
    
    @classmethod
    def get_logger(cls) -> Optional[AuditLogger]:
        """Get existing audit logger instance."""
        return cls._instance
    
    @classmethod
    async def close_logger(cls) -> None:
        """Close existing audit logger instance."""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            cls._config = None