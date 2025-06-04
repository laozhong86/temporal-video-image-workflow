#!/usr/bin/env python3
"""
Progress Query Client

A utility client for querying workflow progress from both Temporal directly
and via the REST API endpoints.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import aiohttp
from temporalio.client import Client
from temporalio.service import TLSConfig

from models.core_models import Progress, WorkflowState
from config.temporal_config import TEMPORAL_HOST, TEMPORAL_NAMESPACE


logger = logging.getLogger(__name__)


@dataclass
class ProgressQueryResult:
    """Result of a progress query."""
    workflow_id: str
    success: bool
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
    source: str = "unknown"  # 'temporal' or 'api'


class ProgressQueryClient:
    """Client for querying workflow progress."""
    
    def __init__(
        self,
        temporal_host: str = TEMPORAL_HOST,
        namespace: str = TEMPORAL_NAMESPACE,
        api_base_url: Optional[str] = None,
        tls_config: Optional[TLSConfig] = None
    ):
        self.temporal_host = temporal_host
        self.namespace = namespace
        self.api_base_url = api_base_url or "http://localhost:8000"
        self.tls_config = tls_config
        self._temporal_client: Optional[Client] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
    
    async def get_temporal_client(self) -> Client:
        """Get or create Temporal client."""
        if self._temporal_client is None:
            self._temporal_client = await Client.connect(
                self.temporal_host,
                namespace=self.namespace,
                tls=self.tls_config
            )
        return self._temporal_client
    
    async def get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._http_session is None:
            self._http_session = aiohttp.ClientSession()
        return self._http_session
    
    async def query_progress_direct(self, workflow_id: str) -> ProgressQueryResult:
        """Query progress directly from Temporal."""
        try:
            client = await self.get_temporal_client()
            workflow_handle = client.get_workflow_handle(workflow_id)
            
            # Query progress
            progress_result = await workflow_handle.query("get_progress")
            
            return ProgressQueryResult(
                workflow_id=workflow_id,
                success=True,
                progress=progress_result,
                timestamp=datetime.now().isoformat(),
                source="temporal"
            )
            
        except Exception as e:
            logger.error(f"Failed to query progress directly for {workflow_id}: {e}")
            return ProgressQueryResult(
                workflow_id=workflow_id,
                success=False,
                error=str(e),
                timestamp=datetime.now().isoformat(),
                source="temporal"
            )
    
    async def query_progress_api(self, workflow_id: str) -> ProgressQueryResult:
        """Query progress via REST API."""
        try:
            session = await self.get_http_session()
            url = f"{self.api_base_url}/workflows/{workflow_id}/progress"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return ProgressQueryResult(
                        workflow_id=workflow_id,
                        success=True,
                        progress=data.get("progress"),
                        timestamp=data.get("timestamp"),
                        source="api"
                    )
                else:
                    error_data = await response.json()
                    return ProgressQueryResult(
                        workflow_id=workflow_id,
                        success=False,
                        error=error_data.get("detail", f"HTTP {response.status}"),
                        timestamp=datetime.now().isoformat(),
                        source="api"
                    )
                    
        except Exception as e:
            logger.error(f"Failed to query progress via API for {workflow_id}: {e}")
            return ProgressQueryResult(
                workflow_id=workflow_id,
                success=False,
                error=str(e),
                timestamp=datetime.now().isoformat(),
                source="api"
            )
    
    async def query_detailed_status_api(self, workflow_id: str) -> ProgressQueryResult:
        """Query detailed status via REST API."""
        try:
            session = await self.get_http_session()
            url = f"{self.api_base_url}/workflows/{workflow_id}/detailed-status"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return ProgressQueryResult(
                        workflow_id=workflow_id,
                        success=True,
                        progress=data,
                        timestamp=data.get("timestamp"),
                        source="api"
                    )
                else:
                    error_data = await response.json()
                    return ProgressQueryResult(
                        workflow_id=workflow_id,
                        success=False,
                        error=error_data.get("detail", f"HTTP {response.status}"),
                        timestamp=datetime.now().isoformat(),
                        source="api"
                    )
                    
        except Exception as e:
            logger.error(f"Failed to query detailed status via API for {workflow_id}: {e}")
            return ProgressQueryResult(
                workflow_id=workflow_id,
                success=False,
                error=str(e),
                timestamp=datetime.now().isoformat(),
                source="api"
            )
    
    async def query_progress_with_fallback(self, workflow_id: str) -> ProgressQueryResult:
        """Query progress with fallback from direct to API."""
        # Try direct Temporal query first
        result = await self.query_progress_direct(workflow_id)
        
        if result.success:
            return result
        
        # Fallback to API query
        logger.info(f"Direct query failed for {workflow_id}, trying API fallback")
        return await self.query_progress_api(workflow_id)
    
    async def query_multiple_workflows(
        self, 
        workflow_ids: List[str],
        use_api: bool = False
    ) -> List[ProgressQueryResult]:
        """Query progress for multiple workflows concurrently."""
        if use_api:
            tasks = [self.query_progress_api(wf_id) for wf_id in workflow_ids]
        else:
            tasks = [self.query_progress_with_fallback(wf_id) for wf_id in workflow_ids]
        
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    async def monitor_progress(
        self, 
        workflow_id: str, 
        interval: float = 5.0,
        max_iterations: int = 100,
        use_api: bool = False
    ) -> List[ProgressQueryResult]:
        """Monitor workflow progress over time.
        
        Args:
            workflow_id: Workflow to monitor
            interval: Seconds between queries
            max_iterations: Maximum number of queries
            use_api: Whether to use API instead of direct queries
            
        Returns:
            List of progress results over time
        """
        results = []
        
        for i in range(max_iterations):
            if use_api:
                result = await self.query_progress_api(workflow_id)
            else:
                result = await self.query_progress_with_fallback(workflow_id)
            
            results.append(result)
            
            # Check if workflow is completed
            if result.success and result.progress:
                progress_data = result.progress
                if isinstance(progress_data, dict):
                    percent = progress_data.get("percent", 0)
                    status = progress_data.get("status", "")
                    
                    # Stop monitoring if completed or failed
                    if percent >= 100 or status in ["completed", "failed", "cancelled"]:
                        logger.info(f"Workflow {workflow_id} completed with status: {status}")
                        break
            
            # Wait before next query
            if i < max_iterations - 1:
                await asyncio.sleep(interval)
        
        return results
    
    def format_progress_result(self, result: ProgressQueryResult) -> str:
        """Format progress result for display."""
        if not result.success:
            return f"❌ {result.workflow_id}: Error - {result.error}"
        
        if not result.progress:
            return f"⚠️  {result.workflow_id}: No progress data available"
        
        progress = result.progress
        if isinstance(progress, dict):
            percent = progress.get("percent", 0)
            status = progress.get("status", "unknown")
            message = progress.get("message", "")
            
            status_emoji = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🚫"
            }.get(status, "❓")
            
            return f"{status_emoji} {result.workflow_id}: {percent}% - {status} - {message}"
        
        return f"📊 {result.workflow_id}: {progress}"
    
    async def close(self):
        """Close all connections."""
        if self._temporal_client:
            # Temporal Python client doesn't have a close method
        # It cleans itself up when no longer referenced
        pass
            self._temporal_client = None
        
        if self._http_session:
            await self._http_session.close()
            self._http_session = None


async def main():
    """Example usage of ProgressQueryClient."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python progress_client.py <workflow_id> [monitor]")
        return
    
    workflow_id = sys.argv[1]
    monitor_mode = len(sys.argv) > 2 and sys.argv[2] == "monitor"
    
    client = ProgressQueryClient()
    
    try:
        if monitor_mode:
            print(f"Monitoring progress for workflow: {workflow_id}")
            results = await client.monitor_progress(workflow_id, interval=2.0, max_iterations=30)
            
            print("\nProgress History:")
            for i, result in enumerate(results):
                print(f"[{i+1:2d}] {client.format_progress_result(result)}")
        else:
            print(f"Querying progress for workflow: {workflow_id}")
            
            # Try both direct and API methods
            direct_result = await client.query_progress_direct(workflow_id)
            api_result = await client.query_progress_api(workflow_id)
            
            print("\nDirect Temporal Query:")
            print(client.format_progress_result(direct_result))
            
            print("\nAPI Query:")
            print(client.format_progress_result(api_result))
            
            # Try detailed status
            detailed_result = await client.query_detailed_status_api(workflow_id)
            print("\nDetailed Status:")
            if detailed_result.success:
                import json
                print(json.dumps(detailed_result.progress, indent=2))
            else:
                print(f"Error: {detailed_result.error}")
    
    finally:
        # Temporal Python client doesn't have a close method
    # It cleans itself up when no longer referenced
    pass


if __name__ == "__main__":
    asyncio.run(main())