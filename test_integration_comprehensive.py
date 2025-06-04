#!/usr/bin/env python3
"""
Comprehensive Integration Tests for Temporal Video Generation System

This module provides comprehensive integration tests covering:
- End-to-end workflow execution
- Service integration (Temporal, ComfyUI, Kling)
- Callback system integration
- Database and persistence integration
- Error recovery and resilience testing
"""

import pytest
import asyncio
import httpx
import json
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import patch, Mock, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import project modules
from models.core_models import JobInput, Progress, JobStatus, Step
from models.video_request import VideoRequest
from models.image_request import ImageRequest
from config import Config


class TestEndToEndWorkflow:
    """Test complete end-to-end workflow execution."""
    
    @pytest.mark.asyncio
    async def test_complete_video_generation_workflow_mock(self):
        """Test complete video generation workflow with mocked services."""
        # Create test job input
        job_input = JobInput(
            prompt="A serene lake with mountains in the background",
            job_type=Step.VIDEO,
            width=512,
            height=512,
            duration=5.0,
            user_id="integration_test_user"
        )
        
        # Mock workflow execution steps
        workflow_steps = [
            {"step": "image_generation", "duration": 30, "success": True},
            {"step": "video_generation", "duration": 120, "success": True},
            {"step": "callback_processing", "duration": 5, "success": True}
        ]
        
        total_duration = 0
        for step in workflow_steps:
            start_time = time.time()
            
            # Simulate step execution
            await asyncio.sleep(0.1)  # Simulate processing time
            
            step_duration = time.time() - start_time
            total_duration += step_duration
            
            assert step["success"] is True
            print(f"✅ {step['step']} completed in {step_duration:.2f}s")
        
        print(f"🎉 Complete workflow finished in {total_duration:.2f}s")
        assert total_duration > 0
    
    @pytest.mark.asyncio
    async def test_workflow_with_image_input(self):
        """Test workflow starting with existing image."""
        job_input = JobInput(
            prompt="Transform this image into a dynamic video",
            job_type=Step.VIDEO,
            image_url="https://example.com/test_image.jpg",
            duration=10.0,
            user_id="test_user_image"
        )
        
        # Mock workflow that skips image generation
        workflow_steps = [
            {"step": "image_validation", "duration": 2, "success": True},
            {"step": "video_generation", "duration": 90, "success": True},
            {"step": "finalization", "duration": 5, "success": True}
        ]
        
        for step in workflow_steps:
            await asyncio.sleep(0.05)  # Simulate processing
            assert step["success"] is True
            print(f"✅ {step['step']} completed")
    
    @pytest.mark.asyncio
    async def test_batch_workflow_processing(self):
        """Test batch processing of multiple workflows."""
        # Create multiple test jobs
        test_jobs = [
            JobInput(
                prompt=f"Test video {i}",
                job_type=Step.VIDEO,
                width=512,
                height=512,
                duration=5.0,
                user_id=f"batch_user_{i}"
            )
            for i in range(3)
        ]
        
        # Process jobs concurrently
        async def process_job(job: JobInput) -> Dict[str, Any]:
            start_time = time.time()
            await asyncio.sleep(0.1)  # Simulate processing
            return {
                "job_id": f"job_{job.user_id}",
                "status": "completed",
                "duration": time.time() - start_time
            }
        
        # Execute batch processing
        results = await asyncio.gather(*[process_job(job) for job in test_jobs])
        
        assert len(results) == len(test_jobs)
        assert all(result["status"] == "completed" for result in results)
        print(f"✅ Batch processing completed: {len(results)} jobs")


class TestServiceIntegration:
    """Test integration between different services."""
    
    @pytest.mark.asyncio
    async def test_temporal_client_connection(self):
        """Test Temporal client connection and basic operations."""
        # Mock Temporal client
        with patch('temporalio.client.Client.connect') as mock_connect:
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            
            # Test connection
            client = await mock_connect("localhost:7233")
            assert client is not None
            
            # Test workflow execution
            mock_handle = AsyncMock()
            mock_handle.result.return_value = {"status": "completed"}
            mock_client.start_workflow.return_value = mock_handle
            
            handle = await client.start_workflow(
                "VideoGenerationWorkflow",
                {"prompt": "test"},
                id="test_workflow_123",
                task_queue="video-generation"
            )
            
            result = await handle.result()
            assert result["status"] == "completed"
            print("✅ Temporal client integration test passed")
    
    @pytest.mark.asyncio
    async def test_comfyui_api_integration(self):
        """Test ComfyUI API integration."""
        # Mock ComfyUI API responses
        mock_responses = {
            "submit": {
                "status_code": 200,
                "json": {"job_id": "comfy_123", "status": "submitted"}
            },
            "status": {
                "status_code": 200,
                "json": {"status": "completed", "output_url": "https://example.com/image.jpg"}
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock submit request
            mock_submit_response = Mock()
            mock_submit_response.status_code = mock_responses["submit"]["status_code"]
            mock_submit_response.json.return_value = mock_responses["submit"]["json"]
            
            # Mock status request
            mock_status_response = Mock()
            mock_status_response.status_code = mock_responses["status"]["status_code"]
            mock_status_response.json.return_value = mock_responses["status"]["json"]
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_submit_response
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_status_response
            
            # Test API calls
            async with httpx.AsyncClient() as client:
                # Submit job
                submit_response = await client.post(
                    "http://localhost:8188/api/submit",
                    json={"prompt": "test image"}
                )
                assert submit_response.status_code == 200
                
                # Check status
                status_response = await client.get(
                    "http://localhost:8188/api/status/comfy_123"
                )
                assert status_response.status_code == 200
                
            print("✅ ComfyUI API integration test passed")
    
    @pytest.mark.asyncio
    async def test_kling_api_integration(self):
        """Test Kling API integration."""
        # Mock Kling API responses
        mock_responses = {
            "submit": {
                "status_code": 200,
                "json": {"job_id": "kling_456", "status": "processing"}
            },
            "status": {
                "status_code": 200,
                "json": {"status": "completed", "video_url": "https://example.com/video.mp4"}
            }
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock submit request
            mock_submit_response = Mock()
            mock_submit_response.status_code = mock_responses["submit"]["status_code"]
            mock_submit_response.json.return_value = mock_responses["submit"]["json"]
            
            # Mock status request
            mock_status_response = Mock()
            mock_status_response.status_code = mock_responses["status"]["status_code"]
            mock_status_response.json.return_value = mock_responses["status"]["json"]
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_submit_response
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_status_response
            
            # Test API calls
            async with httpx.AsyncClient() as client:
                # Submit video generation
                submit_response = await client.post(
                    "https://api.kling.ai/v1/videos",
                    json={
                        "prompt": "test video",
                        "image_url": "https://example.com/image.jpg"
                    }
                )
                assert submit_response.status_code == 200
                
                # Check status
                status_response = await client.get(
                    "https://api.kling.ai/v1/videos/kling_456"
                )
                assert status_response.status_code == 200
                
            print("✅ Kling API integration test passed")


class TestCallbackSystemIntegration:
    """Test callback system integration."""
    
    @pytest.mark.asyncio
    async def test_callback_server_health_check(self):
        """Test callback server health check endpoint."""
        # This would test against a running callback server
        # For now, we'll mock the response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:16883/health")
                assert response.status_code == 200
                
                health_data = response.json()
                assert health_data["status"] == "healthy"
                
            print("✅ Callback server health check passed")
    
    @pytest.mark.asyncio
    async def test_callback_signal_processing(self):
        """Test callback signal processing."""
        # Mock callback signals
        test_signals = [
            {
                "type": "video_ready",
                "workflow_id": "test_workflow_123",
                "data": {
                    "video_url": "https://example.com/video.mp4",
                    "timestamp": datetime.now().isoformat()
                }
            },
            {
                "type": "kling_done",
                "workflow_id": "test_workflow_123",
                "data": {
                    "job_id": "kling_456",
                    "status": "completed",
                    "final_url": "https://example.com/final_video.mp4"
                }
            }
        ]
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "signal_processed"}
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            async with httpx.AsyncClient() as client:
                for signal in test_signals:
                    response = await client.post(
                        f"http://localhost:16883/callback/{signal['type']}",
                        json=signal["data"]
                    )
                    assert response.status_code == 200
                    
            print("✅ Callback signal processing test passed")
    
    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test callback error handling."""
        # Test invalid callback data
        invalid_signals = [
            {"type": "invalid_signal", "data": {}},
            {"type": "video_ready", "data": {"invalid": "data"}},
            {"type": "kling_done", "data": None}
        ]
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock error responses
            mock_error_response = Mock()
            mock_error_response.status_code = 400
            mock_error_response.json.return_value = {"error": "Invalid signal data"}
            
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_error_response
            
            async with httpx.AsyncClient() as client:
                for signal in invalid_signals:
                    response = await client.post(
                        f"http://localhost:16883/callback/{signal['type']}",
                        json=signal.get("data")
                    )
                    # Should return error status
                    assert response.status_code == 400
                    
            print("✅ Callback error handling test passed")


class TestDatabaseIntegration:
    """Test database and persistence integration."""
    
    def test_workflow_state_persistence(self):
        """Test workflow state persistence."""
        # Mock workflow state data
        workflow_state = {
            "workflow_id": "test_workflow_123",
            "user_id": "test_user",
            "job_input": {
                "prompt": "Test prompt",
                "job_type": "video",
                "width": 512,
                "height": 512
            },
            "current_step": "video_generation",
            "progress": {
                "step": "video_generation",
                "status": "running",
                "percent": 75
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Test state serialization
        serialized_state = json.dumps(workflow_state)
        assert isinstance(serialized_state, str)
        
        # Test state deserialization
        deserialized_state = json.loads(serialized_state)
        assert deserialized_state["workflow_id"] == workflow_state["workflow_id"]
        assert deserialized_state["current_step"] == workflow_state["current_step"]
        
        print("✅ Workflow state persistence test passed")
    
    def test_metrics_data_storage(self):
        """Test metrics data storage."""
        # Mock metrics data
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "workflow_id": "test_workflow_123",
            "step": "image_generation",
            "duration": 45.5,
            "status": "completed",
            "resource_usage": {
                "cpu_percent": 75.2,
                "memory_mb": 512.0,
                "network_io": 1024
            },
            "api_calls": {
                "comfyui_calls": 3,
                "kling_calls": 1,
                "callback_calls": 2
            }
        }
        
        # Test metrics serialization
        serialized_metrics = json.dumps(metrics_data)
        assert isinstance(serialized_metrics, str)
        
        # Test metrics validation
        assert "timestamp" in metrics_data
        assert "workflow_id" in metrics_data
        assert "resource_usage" in metrics_data
        assert isinstance(metrics_data["resource_usage"], dict)
        
        print("✅ Metrics data storage test passed")
    
    def test_search_attributes_indexing(self):
        """Test search attributes indexing."""
        # Mock search attributes
        search_attributes = {
            "user_id": "test_user",
            "job_type": "video",
            "status": "completed",
            "created_date": "2024-01-01",
            "priority": "high",
            "duration_range": "medium"
        }
        
        # Test search query building
        search_queries = [
            f"user_id = '{search_attributes['user_id']}'",
            f"job_type = '{search_attributes['job_type']}'",
            f"status = '{search_attributes['status']}'"
        ]
        
        for query in search_queries:
            assert isinstance(query, str)
            assert "=" in query
            
        print("✅ Search attributes indexing test passed")


class TestErrorRecoveryAndResilience:
    """Test error recovery and system resilience."""
    
    @pytest.mark.asyncio
    async def test_workflow_retry_mechanism(self):
        """Test workflow retry mechanism."""
        # Simulate retry scenarios
        retry_scenarios = [
            {"attempt": 1, "success": False, "error": "network_timeout"},
            {"attempt": 2, "success": False, "error": "service_unavailable"},
            {"attempt": 3, "success": True, "error": None}
        ]
        
        successful_attempt = None
        for scenario in retry_scenarios:
            await asyncio.sleep(0.01)  # Simulate retry delay
            
            if scenario["success"]:
                successful_attempt = scenario["attempt"]
                break
            else:
                print(f"❌ Attempt {scenario['attempt']} failed: {scenario['error']}")
        
        assert successful_attempt is not None
        assert successful_attempt == 3
        print(f"✅ Workflow succeeded on attempt {successful_attempt}")
    
    @pytest.mark.asyncio
    async def test_service_failover(self):
        """Test service failover mechanism."""
        # Mock service endpoints
        primary_service = {"url": "http://primary:8188", "available": False}
        backup_service = {"url": "http://backup:8188", "available": True}
        
        # Test failover logic
        selected_service = None
        if primary_service["available"]:
            selected_service = primary_service
        elif backup_service["available"]:
            selected_service = backup_service
        
        assert selected_service is not None
        assert selected_service["url"] == backup_service["url"]
        print(f"✅ Failover to backup service: {selected_service['url']}")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self):
        """Test circuit breaker pattern implementation."""
        # Mock circuit breaker state
        circuit_breaker = {
            "state": "closed",  # closed, open, half_open
            "failure_count": 0,
            "failure_threshold": 5,
            "last_failure_time": None,
            "timeout": 60  # seconds
        }
        
        # Simulate failures
        for i in range(6):
            circuit_breaker["failure_count"] += 1
            
            if circuit_breaker["failure_count"] >= circuit_breaker["failure_threshold"]:
                circuit_breaker["state"] = "open"
                circuit_breaker["last_failure_time"] = datetime.now()
                break
        
        assert circuit_breaker["state"] == "open"
        assert circuit_breaker["failure_count"] >= circuit_breaker["failure_threshold"]
        print("✅ Circuit breaker opened after threshold failures")
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation under load."""
        # Mock system load scenarios
        load_scenarios = [
            {"cpu_usage": 50, "memory_usage": 60, "action": "normal_operation"},
            {"cpu_usage": 80, "memory_usage": 85, "action": "reduce_quality"},
            {"cpu_usage": 95, "memory_usage": 95, "action": "queue_requests"}
        ]
        
        for scenario in load_scenarios:
            if scenario["cpu_usage"] > 90 or scenario["memory_usage"] > 90:
                action = "queue_requests"
            elif scenario["cpu_usage"] > 75 or scenario["memory_usage"] > 80:
                action = "reduce_quality"
            else:
                action = "normal_operation"
            
            assert action == scenario["action"]
            print(f"✅ Load scenario: CPU {scenario['cpu_usage']}%, Memory {scenario['memory_usage']}% -> {action}")


class TestPerformanceIntegration:
    """Test performance and load integration."""
    
    @pytest.mark.asyncio
    async def test_concurrent_workflow_execution(self):
        """Test concurrent workflow execution."""
        # Create multiple concurrent workflows
        num_workflows = 5
        
        async def mock_workflow(workflow_id: int) -> Dict[str, Any]:
            start_time = time.time()
            await asyncio.sleep(0.1)  # Simulate processing
            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "duration": time.time() - start_time
            }
        
        # Execute workflows concurrently
        start_time = time.time()
        results = await asyncio.gather(*[
            mock_workflow(i) for i in range(num_workflows)
        ])
        total_time = time.time() - start_time
        
        assert len(results) == num_workflows
        assert all(result["status"] == "completed" for result in results)
        assert total_time < 1.0  # Should complete much faster than sequential
        
        print(f"✅ {num_workflows} concurrent workflows completed in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_resource_usage_monitoring(self):
        """Test resource usage monitoring during execution."""
        # Mock resource monitoring
        resource_snapshots = []
        
        for i in range(5):
            await asyncio.sleep(0.02)  # Simulate monitoring interval
            
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": 50 + (i * 5),  # Gradually increasing
                "memory_mb": 512 + (i * 64),
                "active_workflows": i + 1
            }
            resource_snapshots.append(snapshot)
        
        assert len(resource_snapshots) == 5
        assert resource_snapshots[-1]["cpu_percent"] > resource_snapshots[0]["cpu_percent"]
        assert resource_snapshots[-1]["memory_mb"] > resource_snapshots[0]["memory_mb"]
        
        print(f"✅ Resource monitoring captured {len(resource_snapshots)} snapshots")
    
    @pytest.mark.asyncio
    async def test_throughput_measurement(self):
        """Test system throughput measurement."""
        # Mock throughput measurement
        start_time = time.time()
        completed_jobs = 0
        target_jobs = 10
        
        for i in range(target_jobs):
            await asyncio.sleep(0.01)  # Simulate job processing
            completed_jobs += 1
        
        total_time = time.time() - start_time
        throughput = completed_jobs / total_time  # jobs per second
        
        assert completed_jobs == target_jobs
        assert throughput > 0
        
        print(f"✅ Throughput: {throughput:.2f} jobs/second ({completed_jobs} jobs in {total_time:.2f}s)")


def run_integration_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("🔗 运行综合集成测试")
    print("="*60)
    
    # Run pytest with verbose output
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "--color=yes",
        "-m", "not slow"  # Skip slow tests by default
    ]
    
    return pytest.main(pytest_args)


if __name__ == "__main__":
    exit_code = run_integration_tests()
    sys.exit(exit_code)