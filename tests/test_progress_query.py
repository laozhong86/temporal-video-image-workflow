#!/usr/bin/env python3
"""
Test Progress Query Interface

Tests for the progress query functionality including REST API endpoints
and direct Temporal queries.
"""

import asyncio
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.progress_client import ProgressQueryClient, ProgressQueryResult
from models.core_models import Progress, JobStatus, Step


class TestProgressQueryClient:
    """Test cases for ProgressQueryClient."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return ProgressQueryClient(
            temporal_host="localhost:7233",
            namespace="test",
            api_base_url="http://localhost:8000"
        )
    
    @pytest.fixture
    def mock_progress_data(self):
        """Mock progress data."""
        return {
            "step": "video_generation",
            "status": "running",
            "percent": 75,
            "message": "Generating video...",
            "asset_url": "https://example.com/temp.mp4",
            "updated_at": datetime.now().isoformat()
        }
    
    @pytest.mark.asyncio
    async def test_query_progress_direct_success(self, client, mock_progress_data):
        """Test successful direct progress query."""
        workflow_id = "test-workflow-123"
        
        # Mock Temporal client and workflow handle
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_handle.query.return_value = mock_progress_data
        mock_client.get_workflow_handle.return_value = mock_handle
        
        with patch.object(client, 'get_temporal_client', return_value=mock_client):
            result = await client.query_progress_direct(workflow_id)
        
        assert result.success is True
        assert result.workflow_id == workflow_id
        assert result.progress == mock_progress_data
        assert result.source == "temporal"
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_query_progress_direct_failure(self, client):
        """Test failed direct progress query."""
        workflow_id = "test-workflow-123"
        error_message = "Workflow not found"
        
        # Mock Temporal client to raise exception
        mock_client = AsyncMock()
        mock_client.get_workflow_handle.side_effect = Exception(error_message)
        
        with patch.object(client, 'get_temporal_client', return_value=mock_client):
            result = await client.query_progress_direct(workflow_id)
        
        assert result.success is False
        assert result.workflow_id == workflow_id
        assert result.error == error_message
        assert result.source == "temporal"
        assert result.progress is None
    
    @pytest.mark.asyncio
    async def test_query_progress_api_success(self, client, mock_progress_data):
        """Test successful API progress query."""
        workflow_id = "test-workflow-123"
        api_response = {
            "workflow_id": workflow_id,
            "workflow_status": "RUNNING",
            "progress": mock_progress_data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Mock HTTP session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = api_response
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch.object(client, 'get_http_session', return_value=mock_session):
            result = await client.query_progress_api(workflow_id)
        
        assert result.success is True
        assert result.workflow_id == workflow_id
        assert result.progress == mock_progress_data
        assert result.source == "api"
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_query_progress_api_failure(self, client):
        """Test failed API progress query."""
        workflow_id = "test-workflow-123"
        error_detail = "Workflow not found"
        
        # Mock HTTP session with error response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.json.return_value = {"detail": error_detail}
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        with patch.object(client, 'get_http_session', return_value=mock_session):
            result = await client.query_progress_api(workflow_id)
        
        assert result.success is False
        assert result.workflow_id == workflow_id
        assert result.error == error_detail
        assert result.source == "api"
        assert result.progress is None
    
    @pytest.mark.asyncio
    async def test_query_progress_with_fallback(self, client, mock_progress_data):
        """Test progress query with fallback from direct to API."""
        workflow_id = "test-workflow-123"
        
        # Mock direct query to fail
        direct_result = ProgressQueryResult(
            workflow_id=workflow_id,
            success=False,
            error="Direct query failed",
            source="temporal"
        )
        
        # Mock API query to succeed
        api_result = ProgressQueryResult(
            workflow_id=workflow_id,
            success=True,
            progress=mock_progress_data,
            source="api"
        )
        
        with patch.object(client, 'query_progress_direct', return_value=direct_result), \
             patch.object(client, 'query_progress_api', return_value=api_result):
            
            result = await client.query_progress_with_fallback(workflow_id)
        
        assert result.success is True
        assert result.source == "api"
        assert result.progress == mock_progress_data
    
    @pytest.mark.asyncio
    async def test_query_multiple_workflows(self, client, mock_progress_data):
        """Test querying multiple workflows."""
        workflow_ids = ["wf-1", "wf-2", "wf-3"]
        
        # Mock successful results for all workflows
        mock_results = [
            ProgressQueryResult(
                workflow_id=wf_id,
                success=True,
                progress=mock_progress_data,
                source="temporal"
            )
            for wf_id in workflow_ids
        ]
        
        with patch.object(client, 'query_progress_with_fallback', side_effect=mock_results):
            results = await client.query_multiple_workflows(workflow_ids)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.workflow_id == workflow_ids[i]
            assert result.success is True
    
    def test_format_progress_result(self, client, mock_progress_data):
        """Test formatting progress results for display."""
        # Test successful result
        success_result = ProgressQueryResult(
            workflow_id="test-wf",
            success=True,
            progress=mock_progress_data,
            source="temporal"
        )
        
        formatted = client.format_progress_result(success_result)
        assert "test-wf" in formatted
        assert "75%" in formatted
        assert "running" in formatted
        
        # Test failed result
        error_result = ProgressQueryResult(
            workflow_id="test-wf",
            success=False,
            error="Connection failed",
            source="temporal"
        )
        
        formatted = client.format_progress_result(error_result)
        assert "❌" in formatted
        assert "Connection failed" in formatted
    
    @pytest.mark.asyncio
    async def test_monitor_progress_completion(self, client, mock_progress_data):
        """Test monitoring progress until completion."""
        workflow_id = "test-workflow-123"
        
        # Create progress sequence: running -> completed
        progress_sequence = [
            {**mock_progress_data, "percent": 50, "status": "running"},
            {**mock_progress_data, "percent": 75, "status": "running"},
            {**mock_progress_data, "percent": 100, "status": "completed"}
        ]
        
        results = []
        for progress in progress_sequence:
            results.append(ProgressQueryResult(
                workflow_id=workflow_id,
                success=True,
                progress=progress,
                source="temporal"
            ))
        
        with patch.object(client, 'query_progress_with_fallback', side_effect=results):
            monitor_results = await client.monitor_progress(
                workflow_id, 
                interval=0.1,  # Fast interval for testing
                max_iterations=10
            )
        
        # Should stop at completion (3 results)
        assert len(monitor_results) == 3
        assert monitor_results[-1].progress["status"] == "completed"
        assert monitor_results[-1].progress["percent"] == 100


class TestProgressModels:
    """Test cases for progress-related models."""
    
    def test_progress_model_validation(self):
        """Test Progress model validation."""
        # Valid progress
        progress = Progress(
            step=Step.VIDEO_GENERATION,
            status=JobStatus.RUNNING,
            percent=50,
            message="Processing..."
        )
        
        assert progress.step == Step.VIDEO_GENERATION
        assert progress.status == JobStatus.RUNNING
        assert progress.percent == 50
        
        # Test JSON serialization
        json_data = progress.to_json()
        assert "step" in json_data
        assert "status" in json_data
        assert "percent" in json_data
        
        # Test deserialization
        restored = Progress.from_json(json_data)
        assert restored.step == progress.step
        assert restored.status == progress.status
        assert restored.percent == progress.percent
    
    def test_progress_status_consistency(self):
        """Test progress status consistency validation."""
        # Completed status should have 100% progress
        with pytest.raises(ValueError):
            Progress(
                step=Step.VIDEO_GENERATION,
                status=JobStatus.COMPLETED,
                percent=50  # Should be 100 for completed
            )
        
        # Failed status should have error message
        with pytest.raises(ValueError):
            Progress(
                step=Step.VIDEO_GENERATION,
                status=JobStatus.FAILED,
                percent=50,
                error_message=None  # Should have error message
            )


async def run_integration_test():
    """Run integration test with actual API server (if available)."""
    print("Running integration test...")
    
    client = ProgressQueryClient()
    
    try:
        # Test health check via API
        import aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("http://localhost:8000/health") as response:
                    if response.status == 200:
                        print("✅ API server is running")
                        
                        # Test with a dummy workflow ID
                        result = await client.query_progress_api("test-workflow-123")
                        if result.success:
                            print("✅ Progress query succeeded")
                        else:
                            print(f"⚠️  Progress query failed (expected): {result.error}")
                    else:
                        print(f"❌ API server health check failed: {response.status}")
            except Exception as e:
                print(f"⚠️  API server not available: {e}")
    
    finally:
        # Temporal Python client doesn't have a close method
    # It cleans itself up when no longer referenced
    pass


if __name__ == "__main__":
    # Run integration test
    asyncio.run(run_integration_test())
    
    # Run unit tests with pytest
    print("\nTo run unit tests, use: pytest test_progress_query.py -v")